import re
import json
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd

from src.ai_assistant.openrouter_client import OpenRouterClient
from src.ai_assistant.sql_validator import SQLValidator
from src.database.db_manager import DatabaseManager

class SpatialQueryEngine:
    """Translates natural language questions to validated read-only SQL, executes queries, and synthesizes evidence-backed answers."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        llm_client: Optional[OpenRouterClient] = None,
        validator: Optional[SQLValidator] = None,
    ):
        self.db = db_manager
        self.llm = llm_client if llm_client else OpenRouterClient()
        self.validator = validator if validator else SQLValidator()
        self.schema_str = self.db.get_db_schema_string()

    def answer_question(
        self,
        question: str,
        active_plan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End-to-end question answering pipeline:
        1. Natural language question understanding & SQL generation.
        2. Strict SQL validation (read-only, whitelisted tables).
        3. Read-only database query execution.
        4. Evidence-backed answer synthesis (strictly grounded in retrieved rows, zero hallucinations).
        """
        question_clean = question.strip()
        if not question_clean:
            return {
                "success": False,
                "error": "Question is empty.",
                "answer": "Please ask a question regarding the floor plan or architectural database.",
                "generated_sql": "",
                "records": [],
                "columns": [],
                "confidence": "UNSUPPORTED",
            }

        # Step 0: Security & Prompt Injection Guardrail
        q_lower = question_clean.lower()
        destructive_keywords = ["drop table", "delete from", "truncate table", "alter table", "update ", "insert into", "drop database"]
        if any(dk in q_lower for dk in destructive_keywords):
            return {
                "success": False,
                "question": question_clean,
                "active_plan_id": active_plan_id,
                "generated_sql": "-- [BLOCKED: Destructive SQL keyword detected]",
                "records": [],
                "columns": [],
                "record_count": 0,
                "error": "Security Notice: Destructive SQL operations are not permitted.",
                "answer": "Security Notice: Queries attempting database modifications (DROP, DELETE, UPDATE, INSERT, ALTER) are strictly blocked. Ashian Spatial AI operates in read-only mode.",
                "confidence": "BLOCKED_SECURITY",
                "generation_method": "SECURITY_GUARDRAIL",
                "model_used": "spatial-security-shield",
            }

        # Step 0b: Out-of-Domain Guardrail & Unsupported Question Detection
        unsupported_keywords = [
            "architect", "designer", "who designed", "who built", "construction cost", "cost", "dollar",
            "budget", "price", "how much did", "who owns", "owner", "client", "contractor",
            "year built", "when was", "materials", "concrete", "steel", "hvac",
            "elevator", "escalator", "plumbing system", "tenant", "zoning", "market value", "valuation"
        ]
        for kw in unsupported_keywords:
            if kw in q_lower:
                return {
                    "success": True,
                    "question": question_clean,
                    "active_plan_id": active_plan_id,
                    "generated_sql": "-- [DECLINED: Attribute not present in architectural dataset]",
                    "records": [],
                    "columns": [],
                    "record_count": 0,
                    "answer": (
                        f"Unsupported Question Declined: The requested attribute ('{kw}') is not present in the architectural dataset. "
                        "Ashian Spatial AI provides computer vision spatial analytics (rooms, doors, windows, walls, pixel areas, and indoor navigation paths)."
                    ),
                    "confidence": "UNSUPPORTED_QUESTION",
                    "generation_method": "DOMAIN_GUARDRAIL",
                    "model_used": "spatial-guardrail",
                }

        # Step 1: Generate SQL Query
        generated_sql, gen_method, model_used = self._generate_sql(question_clean, active_plan_id)

        # Step 2: Validate SQL Query
        is_valid, sanitized_sql = self.validator.validate_sql(generated_sql)
        if not is_valid:
            # If the LLM failed validation on a legitimate question (e.g. truncated SQL syntax), try rule-based fallback recovery
            if gen_method == "LLM" and not any(kw in question_clean.upper() for kw in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "PRAGMA"]):
                fallback_sql = self._fallback_rule_based_sql(question_clean, active_plan_id)
                is_fb_val, sanitized_fb_sql = self.validator.validate_sql(fallback_sql)
                if is_fb_val:
                    sanitized_sql = sanitized_fb_sql
                    is_valid = True
                    gen_method = "RULE_BASED_RECOVERY"

            if not is_valid:
                return {
                    "success": False,
                    "question": question_clean,
                    "generated_sql": generated_sql,
                    "error": sanitized_sql, # Contains security explanation
                    "answer": f"Query blocked by Spatial AI Security Policy: {sanitized_sql}",
                    "records": [],
                    "columns": [],
                    "confidence": "BLOCKED_SECURITY",
                    "model_used": model_used,
                }

        # Step 3: Execute Read-Only SQL Query
        records = []
        columns = []
        execution_error = None
        try:
            records, columns = self.db.execute_read_only_sql(sanitized_sql)
        except Exception as e:
            execution_error = str(e)
            # If LLM generated an invalid SQL query, retry with robust rule-based generator
            if gen_method == "LLM":
                fallback_sql = self._fallback_rule_based_sql(question_clean, active_plan_id)
                is_fb_val, sanitized_fb_sql = self.validator.validate_sql(fallback_sql)
                if is_fb_val:
                    try:
                        records, columns = self.db.execute_read_only_sql(sanitized_fb_sql)
                        sanitized_sql = sanitized_fb_sql
                        gen_method = "RULE_BASED_RECOVERY"
                        execution_error = None
                    except Exception as fb_err:
                        execution_error = f"Primary LLM query error: {execution_error} | Fallback query error: {fb_err}"

        if execution_error is not None:
            return {
                "success": False,
                "question": question_clean,
                "generated_sql": sanitized_sql,
                "error": execution_error,
                "answer": f"Database execution error: {execution_error}",
                "records": [],
                "columns": [],
                "confidence": "EXECUTION_ERROR",
                "model_used": model_used,
            }

        # Step 4: Synthesize Evidence-Backed Answer
        answer = self._synthesize_answer(question_clean, sanitized_sql, records, columns, active_plan_id)

        # Determine confidence classification
        if len(records) > 0:
            confidence = "VERIFIED_DATABASE"
        elif "metric" in question_clean.lower() or "meter" in question_clean.lower() or "sqm" in question_clean.lower():
            confidence = "SCALE_UNAVAILABLE"
        else:
            confidence = "NO_RECORDS_FOUND"

        return {
            "success": True,
            "question": question_clean,
            "active_plan_id": active_plan_id,
            "generated_sql": sanitized_sql,
            "records": records,
            "columns": columns,
            "record_count": len(records),
            "answer": answer,
            "confidence": confidence,
            "generation_method": gen_method,
            "model_used": model_used,
        }

    def _generate_sql(self, question: str, active_plan_id: Optional[str]) -> Tuple[str, str, Optional[str]]:
        """Generates SQL using LLM, with fallback to rule-based pattern matching."""
        # 1. Try LLM Generation if configured
        if self.llm.is_configured():
            prompt = self._build_sql_prompt(question, active_plan_id)
            messages = [
                {"role": "system", "content": "You are a professional SQLite spatial database engineer. Generate ONLY a single read-only SELECT query matching the user's question. Return nothing else: no commentary, no markdown ticks."},
                {"role": "user", "content": prompt},
            ]
            resp = self.llm.generate_chat_completion(messages, temperature=0.0, max_tokens=250)
            if resp["success"] and resp["content"]:
                candidate_sql = self._clean_llm_sql(resp["content"])
                return candidate_sql, "LLM", resp["model_used"]

        # 2. Rule-Based Fallback Engine (Reliable, fast, offline)
        fallback_sql = self._fallback_rule_based_sql(question, active_plan_id)
        return fallback_sql, "RULE_BASED_FALLBACK", "local-rule-engine"

    def _build_sql_prompt(self, question: str, active_plan_id: Optional[str]) -> str:
        """Constructs prompt for SQL generation."""
        context_str = f"Current active floor plan ID: '{active_plan_id}'." if active_plan_id else "No single active floor plan specified."

        return f"""
SQLite Database Schema:
{self.schema_str}

Important Guidelines:
1. Generate ONLY a valid SQLite SELECT query. Do not use write operations.
2. {context_str}
3. If the user refers to 'this floor plan' or 'the floor plan' without specifying an ID, use plan_id = '{active_plan_id or '1'}'.
4. To match floor plans by ID: JOIN floor_plans fp ON ... WHERE fp.plan_id = '1' (or appropriate ID).
5. For room connectivity: ALWAYS query table `room_connections rc JOIN floor_plans fp ON rc.floor_plan_id = fp.id WHERE fp.plan_id = '...' AND (rc.room_1_index = X OR rc.room_2_index = X)`.
6. For room area: `pixel_area` is in pixels. (Raw dataset does not have square meters; do not claim square meters).
7. Return ONLY the raw SQL SELECT query. Do not output conversational text or markdown code fences.

User Question: {question}
"""

    def _clean_llm_sql(self, text: str) -> str:
        """Strips markdown fences and extracts raw SQL."""
        text = text.strip()
        text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _synthesize_answer(
        self,
        question: str,
        sql: str,
        records: List[Dict[str, Any]],
        columns: List[str],
        active_plan_id: Optional[str]
    ) -> str:
        """Synthesizes factual, evidence-backed answer strictly from retrieved database records."""
        # Check scale calibration question
        q_lower = question.lower()
        if any(term in q_lower for term in ["square meter", "sqm", "m2", "scale", "meters"]):
            room_detail = ""
            if records:
                r0 = records[0]
                if "pixel_area" in r0:
                    r_name = r0.get("room_name", "the requested room")
                    room_detail = f" In Floor Plan {active_plan_id or '1'}, {r_name} has an area of **{r0['pixel_area']:,} pixels**."
            return (
                f"Floor Plan {active_plan_id or '1'} measurements are calculated and reported in pixels because the source architectural dataset does not include physical scale calibration.{room_detail}\n\n"
                "In strict compliance with zero-hallucination protocols, physical metric units (square meters) are not fabricated."
            )

        if not records:
            return (
                f"No records matching your question were found in the spatial database. "
                "Please verify that the specified room or floor plan ID exists."
            )

        # If LLM is available, use it to generate an evidence-backed natural language summary
        if self.llm.is_configured():
            prompt = f"""
User Question: {question}
Executed SQL: {sql}
Retrieved Database Records ({len(records)} total):
{json.dumps(records[:25], indent=2, default=str)}

Instructions:
1. Provide a concise, professional, direct answer grounded STRICTLY in the retrieved records.
2. Format answers using readable paragraphs and bullet points where helpful.
3. Remove technical annotations like [Heuristic] from room names.
4. NEVER invent room names, doors, or measurements not present in the data.
5. All measurements are in pixels (px). Never convert to square meters unless a scale is provided.
6. If the data is empty or missing, clearly state that.
"""
            messages = [
                {"role": "system", "content": "You are Ashian Spatial AI Assistant. You answer architectural questions strictly grounded in actual database query records. Never hallucinate."},
                {"role": "user", "content": prompt},
            ]
            resp = self.llm.generate_chat_completion(messages, temperature=0.1, max_tokens=400)
            if resp["success"] and resp["content"]:
                return resp["content"].strip()

        # Deterministic fallback answer generator
        return self._format_deterministic_answer(question, records, columns)

    def _format_deterministic_answer(self, question: str, records: List[Dict[str, Any]], columns: List[str]) -> str:
        """Formats records into a clean, human-friendly natural language summary."""
        count = len(records)
        q = question.lower()

        # 1. Custom formatter for room counting with clean bullet points
        if count == 1 and ("num_habitable_rooms" in columns or "room_count_breakdown" in columns):
            rec = records[0]
            pid = rec.get("plan_id", "1")
            n_tot = rec.get("num_rooms", rec.get("total_detected_regions", count))
            n_hab = rec.get("num_habitable_rooms", 0)
            n_serv = rec.get("num_service_rooms", 0)
            n_balc = rec.get("num_balconies", 0)
            n_corr = rec.get("num_corridors", 0)
            
            lines = [f"Floor Plan {pid} contains {n_tot} detected spatial regions:"]
            lines.append(f"- {n_hab} habitable regions")
            if n_serv > 0:
                lines.append(f"- {n_serv} service region{'s' if n_serv != 1 else ''}")
            if n_balc > 0:
                lines.append(f"- {n_balc} balcony segment{'s' if n_balc != 1 else ''}")
            if n_corr > 0:
                lines.append(f"- {n_corr} corridor{'s' if n_corr != 1 else ''}")
            lines.append("\nThese figures are based on the available segmentation annotations.")
            return "\n".join(lines)

        # 2. Custom formatter for largest / smallest room
        if "pixel_area" in columns and "room_name" in columns:
            rec = records[0]
            r_name = rec.get("room_name", "Room")
            r_type = str(rec.get("room_type", "")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
            p_area = rec.get("pixel_area", 0)
            if "largest" in q or "biggest" in q or "max" in q:
                return f"The largest room is **{r_name}** ({r_type}) with an area of **{p_area:,} pixels**."
            elif "smallest" in q or "min" in q:
                return f"The smallest room is **{r_name}** ({r_type}) with an area of **{p_area:,} pixels**."
            elif count == 1:
                return f"**{r_name}** ({r_type}) has an area of **{p_area:,} pixels**."

        # 3. Custom formatter for room connections
        if "room_1_name" in columns and "room_2_name" in columns:
            if count == 0:
                return "No door connections were found matching this query in the spatial database."
            lines = [f"Found **{count} connection(s)**:"]
            for r in records[:10]:
                d_idx = r.get("door_index", 0)
                r1 = r.get("room_1_name", "")
                r2 = r.get("room_2_name", "")
                dist = r.get("distance_px", 0)
                d_str = f"Door {d_idx}" if d_idx and d_idx != 0 else "Open Archway"
                lines.append(f"- **{r1}** connects to **{r2}** via {d_str} (~{int(dist)} px)")
            if count > 10:
                lines.append(f"... and {count - 10} more connections.")
            return "\n".join(lines)

        # 4. Custom formatter for average rooms query
        if count == 1 and "average_rooms_per_plan" in records[0]:
            rec = records[0]
            avg_rooms = rec["average_rooms_per_plan"]
            total_plans = rec.get("total_plans", len(records))
            min_r = rec.get("min_rooms", "N/A")
            max_r = rec.get("max_rooms", "N/A")
            return f"Across the {total_plans} floor plans in the database, the average number of rooms is **{avg_rooms} rooms per plan** (ranging from {min_r} to {max_r} rooms)."

        # 5. Custom formatter for 'which plans have more than N doors'
        if "plan_id" in columns and "num_doors" in columns:
            plan_list = [f"Plan {r['plan_id']} ({r['num_doors']} doors, {r.get('num_rooms', '?')} rooms)" for r in records]
            return f"There are **{count} floor plans** in the database with more than the specified doors:\n" + "\n".join(f"- {p}" for p in plan_list)

        # 6. Custom formatter for 'rooms with no windows'
        if "window_count" in columns:
            clean_rooms = []
            for r in records:
                clean_t = str(r['room_type']).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
                clean_rooms.append(f"**{r['room_name']}** ({clean_t}, area: {r['pixel_area']:,} px)")
            return f"Found **{count} room(s)** without detected exterior windows:\n" + "\n".join(f"- {rm}" for rm in clean_rooms)

        # 7. Generic single record
        if count == 1:
            rec = records[0]
            items = []
            for k, v in rec.items():
                clean_val = str(v).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
                items.append(f"**{k}**: {clean_val}")
            return f"Retrieved record: {', '.join(items)}."
        
        # 8. Multiple records
        summary_lines = [f"Retrieved {count} records:"]
        for i, r in enumerate(records[:8], start=1):
            key_vals = []
            for k, v in list(r.items())[:4]:
                clean_v = str(v).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
                key_vals.append(f"{k}={clean_v}")
            summary_lines.append(f"{i}. {', '.join(key_vals)}")
        if count > 8:
            summary_lines.append(f"... and {count - 8} more records.")
        return "\n".join(summary_lines)

    def _fallback_rule_based_sql(self, question: str, active_plan_id: Optional[str]) -> str:
        """Robust rule-based SQL generator for common queries."""
        q = question.lower()
        plan_id = active_plan_id or "1"
        
        # Check if another plan_id is mentioned in question (e.g. "plan 2", "plan 10", "floor plan 3")
        plan_match = re.search(r"\b(?:plan|floor plan)\s+(\d+)\b", q)
        if plan_match:
            plan_id = plan_match.group(1)

        # 1. Cross-plan door thresholds (e.g. "which plans have more than 3 doors?")
        door_gt_match = re.search(r"\bmore than\s+(\d+)\s+doors?\b", q)
        if door_gt_match or ("which plan" in q and "door" in q):
            min_doors = int(door_gt_match.group(1)) if door_gt_match else 3
            return f"SELECT fp.plan_id, em.num_doors, em.num_rooms FROM floor_plans fp JOIN extraction_metadata em ON fp.id = em.floor_plan_id WHERE em.num_doors > {min_doors} ORDER BY em.num_doors DESC;"

        # 2. Cross-plan room averages (e.g. "what is the average number of rooms across all plans?")
        if "average" in q or "mean" in q:
            if "room" in q:
                return "SELECT round(avg(em.num_rooms), 2) as average_rooms_per_plan, min(em.num_rooms) as min_rooms, max(em.num_rooms) as max_rooms, count(fp.id) as total_plans FROM floor_plans fp JOIN extraction_metadata em ON fp.id = em.floor_plan_id;"
            if "door" in q:
                return "SELECT round(avg(em.num_doors), 2) as average_doors_per_plan, count(fp.id) as total_plans FROM floor_plans fp JOIN extraction_metadata em ON fp.id = em.floor_plan_id;"

        # 3. Rooms without windows (e.g. "which room in plan 4 has no windows?")
        if "no window" in q or "without window" in q or "zero window" in q:
            return f"SELECT r.room_name, r.room_type, r.window_count, r.pixel_area FROM rooms r JOIN floor_plans fp ON r.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' AND r.window_count = 0 ORDER BY r.room_index ASC;"

        # 4. Total room area
        if "total room area" in q or "total area" in q or "sum of area" in q or "all room area" in q:
            return f"SELECT fp.plan_id, em.total_room_area_px, em.num_rooms FROM floor_plans fp JOIN extraction_metadata em ON fp.id = em.floor_plan_id WHERE fp.plan_id = '{plan_id}' LIMIT 1;"

        # 5. Connections / connectivity (put before generic 'what rooms')
        if "connect" in q or "adjacent" in q or "neighbor" in q or "touch" in q:
            rm_all = re.findall(r"\broom\s*(\d+)\b", q)
            if len(rm_all) >= 2:
                r1, r2 = int(rm_all[0]), int(rm_all[1])
                return f"SELECT rc.door_index, rc.room_1_name, rc.room_2_name, rc.distance_px FROM room_connections rc JOIN floor_plans fp ON rc.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' AND ((rc.room_1_index = {r1} AND rc.room_2_index = {r2}) OR (rc.room_1_index = {r2} AND rc.room_2_index = {r1})) LIMIT 10;"
            elif len(rm_all) == 1:
                rid = int(rm_all[0])
                return f"SELECT rc.door_index, rc.room_1_name, rc.room_2_name, rc.distance_px FROM room_connections rc JOIN floor_plans fp ON rc.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' AND (rc.room_1_index = {rid} OR rc.room_2_index = {rid}) LIMIT 50;"
            return f"SELECT rc.door_index, rc.room_1_name, rc.room_2_name, rc.distance_px FROM room_connections rc JOIN floor_plans fp ON rc.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' LIMIT 50;"

        # 6. Total / count rooms
        if "how many room" in q or "count room" in q or "number of room" in q:
            return f"SELECT fp.plan_id, em.num_rooms, em.total_detected_regions, em.num_habitable_rooms, em.num_service_rooms, em.num_balconies, em.num_corridors, em.room_count_breakdown, em.total_room_area_px FROM floor_plans fp JOIN extraction_metadata em ON fp.id = em.floor_plan_id WHERE fp.plan_id = '{plan_id}' LIMIT 10;"

        # 7. Largest room
        if "largest room" in q or "biggest room" in q or "max area" in q:
            return f"SELECT r.room_name, r.room_type, r.pixel_area, r.centroid_x, r.centroid_y FROM rooms r JOIN floor_plans fp ON r.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' ORDER BY r.pixel_area DESC LIMIT 1;"

        # 8. Smallest room
        if "smallest room" in q or "minimum area" in q:
            return f"SELECT r.room_name, r.room_type, r.pixel_area, r.centroid_x, r.centroid_y FROM rooms r JOIN floor_plans fp ON r.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' ORDER BY r.pixel_area ASC LIMIT 1;"

        # 9. Doors
        if "door" in q:
            return f"SELECT d.door_index, d.door_name, d.orientation, d.is_entrance, d.connected_room_indices FROM doors d JOIN floor_plans fp ON d.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' ORDER BY d.door_index ASC LIMIT 50;"

        # 10. Windows
        if "window" in q:
            return f"SELECT w.window_index, w.window_name, w.orientation, w.pixel_area FROM windows w JOIN floor_plans fp ON w.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' ORDER BY w.window_index ASC LIMIT 50;"

        # 11. List all rooms
        if "all room" in q or "list room" in q or "what rooms" in q:
            return f"SELECT r.room_index, r.room_name, r.room_type, r.pixel_area, r.confidence FROM rooms r JOIN floor_plans fp ON r.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' ORDER BY r.room_index ASC LIMIT 50;"

        # 12. Extraction confidence / metadata
        if "confidence" in q or "validation" in q or "metadata" in q or "status" in q:
            return f"SELECT em.num_rooms, em.num_doors, em.num_windows, em.extraction_confidence_score, em.validation_status, em.limitations FROM extraction_metadata em JOIN floor_plans fp ON em.floor_plan_id = fp.id WHERE fp.plan_id = '{plan_id}' LIMIT 1;"

        # 13. Default summary of plan
        return f"SELECT fp.plan_id, fp.width, fp.height, em.num_rooms, em.num_doors, em.num_windows, em.extraction_confidence_score FROM floor_plans fp LEFT JOIN extraction_metadata em ON fp.id = em.floor_plan_id WHERE fp.plan_id = '{plan_id}' LIMIT 1;"
