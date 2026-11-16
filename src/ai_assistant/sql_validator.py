import re
from typing import List, Set, Tuple

class SQLSecurityException(Exception):
    """Raised when an SQL query violates read-only security constraints."""
    pass

class SQLValidator:
    """Strictly validates SQL queries to ensure read-only execution against allowed schema tables."""

    ALLOWED_TABLES: Set[str] = {
        "floor_plans",
        "rooms",
        "doors",
        "windows",
        "walls",
        "room_connections",
        "extraction_metadata",
    }

    DISALLOWED_KEYWORDS: List[str] = [
        r"\bINSERT\b",
        r"\bUPDATE\b",
        r"\bDELETE\b",
        r"\bDROP\b",
        r"\bALTER\b",
        r"\bCREATE\b",
        r"\bTRUNCATE\b",
        r"\bREPLACE\b",
        r"\bPRAGMA\b",
        r"\bATTACH\b",
        r"\bDETACH\b",
        r"\bVACUUM\b",
        r"\bGRANT\b",
        r"\bREVOKE\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r"\bINTO\b",
        r"\bLOAD_EXTENSION\b",
    ]

    def validate_sql(self, sql: str) -> Tuple[bool, str]:
        """
        Validates that SQL is strictly read-only and targets only allowed tables.
        Returns:
            (is_valid, sanitized_sql_or_error_message)
        """
        if not sql or not isinstance(sql, str):
            return False, "Empty SQL query."

        clean_sql = sql.strip()

        # Remove markdown code blocks if present
        if clean_sql.startswith("```"):
            clean_sql = re.sub(r"^```(?:sql)?\s*", "", clean_sql, flags=re.IGNORECASE)
            clean_sql = re.sub(r"\s*```$", "", clean_sql)
            clean_sql = clean_sql.strip()

        # Strip trailing semicolon
        clean_sql = clean_sql.rstrip(";").strip()

        # Check for multiple statements (semicolon injection)
        if ";" in clean_sql:
            return False, "Security Violation: Multiple SQL statements are strictly forbidden."

        # Must start with SELECT or WITH
        first_word = clean_sql.split()[0].upper() if clean_sql.split() else ""
        if first_word not in ("SELECT", "WITH"):
            return False, f"Security Violation: Query must begin with SELECT (found '{first_word}')."

        # Check for destructive/disallowed keywords
        for pattern in self.DISALLOWED_KEYWORDS:
            if re.search(pattern, clean_sql, re.IGNORECASE):
                matched = re.search(pattern, clean_sql, re.IGNORECASE).group()
                return False, f"Security Violation: Disallowed SQL keyword '{matched}' detected."

        # Check table references
        # Extract table candidates following FROM or JOIN
        table_matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_0-9]+)", clean_sql, re.IGNORECASE)
        for tbl in table_matches:
            tbl_lower = tbl.lower()
            if tbl_lower not in self.ALLOWED_TABLES:
                return False, f"Security Violation: Access to table '{tbl}' is forbidden. Allowed tables: {', '.join(sorted(self.ALLOWED_TABLES))}."

        # Ensure a reasonable LIMIT exists
        if not re.search(r"\bLIMIT\s+\d+\b", clean_sql, re.IGNORECASE):
            clean_sql += " LIMIT 100"

        return True, clean_sql
