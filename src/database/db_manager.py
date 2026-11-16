import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.config import DATABASE_URL, DEFAULT_DB_PATH
from src.database.models import (
    Base, FloorPlan, Room, Door, Window, Wall, RoomConnection, ExtractionMetadata
)

class DatabaseManager:
    """Manages SQLite database connections, schema lifecycle, insertions, and safe read-only queries."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url if db_url else DATABASE_URL
        self.engine = create_engine(self.db_url, echo=False)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.init_db()

    def init_db(self) -> None:
        """Creates all database tables if they do not exist."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Returns a new SQLAlchemy session."""
        return self.SessionFactory()

    def save_extraction_result(
        self,
        metadata_dict: Dict[str, Any],
        extraction_data: Dict[str, Any]
    ) -> int:
        """
        Persists a fully extracted floor plan document and all child entities into SQLite.
        Returns the database id of the floor plan.
        """
        plan_id_str = str(metadata_dict["plan_id"])

        with self.get_session() as session:
            # Check if already exists; if so, delete old record to re-insert freshly
            existing = session.query(FloorPlan).filter_by(plan_id=plan_id_str).first()
            if existing:
                session.delete(existing)
                session.flush()

            # 1. Floor Plan Record
            inspection = extraction_data.get("inspection", {})
            floor_plan = FloorPlan(
                plan_id=plan_id_str,
                image_file=metadata_dict["image_file"],
                mask_file=metadata_dict["mask_file"],
                width=metadata_dict["width"],
                height=metadata_dict["height"],
                channels=metadata_dict.get("channels", 3),
                total_pixels=metadata_dict["total_pixels"],
                aspect_ratio=metadata_dict["aspect_ratio"],
                indoor_pixels=inspection.get("indoor_pixels", 0),
                indoor_percentage=inspection.get("indoor_percentage", 0.0),
            )
            session.add(floor_plan)
            session.flush()

            fp_id = floor_plan.id

            # 2. Rooms
            room_objs = []
            for r in extraction_data.get("rooms", []):
                room_obj = Room(
                    floor_plan_id=fp_id,
                    room_index=r["room_index"],
                    room_name=r["room_name"],
                    room_type=r["room_type"],
                    raw_class=r["raw_class"],
                    semantic_class=r.get("semantic_class", "Primary Room"),
                    spatial_category=r.get("spatial_category", "Habitable Room"),
                    is_habitable_room=r.get("is_habitable_room", True),
                    inferred_type=r.get("inferred_type", r["room_type"]),
                    window_count=r.get("window_count", 0),
                    bbox_x=r["bbox_x"],
                    bbox_y=r["bbox_y"],
                    bbox_w=r["bbox_w"],
                    bbox_h=r["bbox_h"],
                    centroid_x=r["centroid_x"],
                    centroid_y=r["centroid_y"],
                    pixel_area=r["pixel_area"],
                    aspect_ratio=r["aspect_ratio"],
                    solidity=r["solidity"],
                    confidence=r["confidence"],
                )
                room_objs.append(room_obj)
            session.add_all(room_objs)

            # 3. Doors
            door_objs = []
            for d in extraction_data.get("doors", []):
                connected_str = ",".join(str(x) for x in d.get("connected_rooms", []))
                door_obj = Door(
                    floor_plan_id=fp_id,
                    door_index=d["door_index"],
                    door_name=d["door_name"],
                    bbox_x=d["bbox_x"],
                    bbox_y=d["bbox_y"],
                    bbox_w=d["bbox_w"],
                    bbox_h=d["bbox_h"],
                    centroid_x=d["centroid_x"],
                    centroid_y=d["centroid_y"],
                    pixel_area=d["pixel_area"],
                    orientation=d["orientation"],
                    is_entrance=d.get("is_entrance", False),
                    connected_room_indices=connected_str,
                )
                door_objs.append(door_obj)
            session.add_all(door_objs)

            # 4. Windows
            win_objs = []
            for w in extraction_data.get("windows", []):
                win_obj = Window(
                    floor_plan_id=fp_id,
                    window_index=w["window_index"],
                    window_name=w["window_name"],
                    bbox_x=w["bbox_x"],
                    bbox_y=w["bbox_y"],
                    bbox_w=w["bbox_w"],
                    bbox_h=w["bbox_h"],
                    centroid_x=w["centroid_x"],
                    centroid_y=w["centroid_y"],
                    pixel_area=w["pixel_area"],
                    orientation=w["orientation"],
                    connected_room_index=w.get("connected_room_index"),
                )
                win_objs.append(win_obj)
            session.add_all(win_objs)

            # 5. Walls
            wall_objs = []
            for wl in extraction_data.get("walls", []):
                wall_obj = Wall(
                    floor_plan_id=fp_id,
                    wall_index=wl["wall_index"],
                    bbox_x=wl["bbox_x"],
                    bbox_y=wl["bbox_y"],
                    bbox_w=wl["bbox_w"],
                    bbox_h=wl["bbox_h"],
                    pixel_area=wl["pixel_area"],
                )
                wall_objs.append(wall_obj)
            session.add_all(wall_objs)

            # 6. Room Connections
            conn_objs = []
            for c in extraction_data.get("connections", []):
                conn_obj = RoomConnection(
                    floor_plan_id=fp_id,
                    door_index=c["door_index"],
                    room_1_index=c["room_1_index"],
                    room_2_index=c["room_2_index"],
                    room_1_name=c["room_1_name"],
                    room_2_name=c["room_2_name"],
                    distance_px=c["distance_px"],
                )
                conn_objs.append(conn_obj)
            session.add_all(conn_objs)

            # 7. Extraction Metadata & Validation
            val = extraction_data.get("validation", {})
            limitations_str = " | ".join(val.get("limitations", []))
            meta_obj = ExtractionMetadata(
                floor_plan_id=fp_id,
                num_rooms=val.get("num_rooms", len(room_objs)),
                total_detected_regions=val.get("total_detected_regions", len(room_objs)),
                num_habitable_rooms=val.get("num_habitable_rooms", 0),
                num_service_rooms=val.get("num_service_rooms", 0),
                num_balconies=val.get("num_balconies", 0),
                num_corridors=val.get("num_corridors", 0),
                room_count_breakdown=val.get("room_count_breakdown", ""),
                num_doors=val.get("num_doors", len(door_objs)),
                num_windows=val.get("num_windows", len(win_objs)),
                num_walls=val.get("num_walls", len(wall_objs)),
                num_connections=val.get("num_connections", len(conn_objs)),
                total_room_area_px=val.get("total_room_area_px", sum(r["pixel_area"] for r in extraction_data.get("rooms", []))),
                room_indoor_coverage_pct=val.get("room_indoor_coverage_pct", 0.0),
                connectivity_ratio_pct=val.get("connectivity_ratio_pct", 0.0),
                extraction_confidence_score=val.get("extraction_confidence_score", 0.0),
                validation_status=val.get("validation_status", "UNKNOWN"),
                limitations=limitations_str,
            )
            session.add(meta_obj)

            session.commit()
            return fp_id

    def get_all_floor_plans(self) -> pd.DataFrame:
        """Retrieves summary DataFrame of all floor plans in the database."""
        query = """
        SELECT 
            fp.id, 
            fp.plan_id, 
            fp.image_file, 
            fp.width, 
            fp.height, 
            fp.aspect_ratio,
            em.num_rooms, 
            em.total_detected_regions,
            em.num_habitable_rooms,
            em.num_service_rooms,
            em.num_balconies,
            em.num_corridors,
            em.room_count_breakdown,
            em.num_doors, 
            em.num_windows, 
            em.num_connections,
            em.extraction_confidence_score, 
            em.validation_status
        FROM floor_plans fp
        LEFT JOIN extraction_metadata em ON fp.id = em.floor_plan_id
        ORDER BY CAST(fp.plan_id AS INTEGER) ASC;
        """
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn)

    def get_floor_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete records for a specific floor plan."""
        with self.get_session() as session:
            fp = session.query(FloorPlan).filter_by(plan_id=str(plan_id)).first()
            if not fp:
                return None

            return {
                "id": fp.id,
                "plan_id": fp.plan_id,
                "image_file": fp.image_file,
                "mask_file": fp.mask_file,
                "width": fp.width,
                "height": fp.height,
                "aspect_ratio": fp.aspect_ratio,
                "indoor_pixels": fp.indoor_pixels,
                "indoor_percentage": fp.indoor_percentage,
                "created_at": fp.created_at,
            }

    def get_rooms_df(self, plan_id: str) -> pd.DataFrame:
        """Retrieves rooms for a floor plan as a pandas DataFrame."""
        query = """
        SELECT 
            r.room_index, 
            r.room_name, 
            r.room_type, 
            r.raw_class,
            r.semantic_class,
            r.spatial_category,
            r.is_habitable_room,
            r.inferred_type,
            r.window_count,
            r.pixel_area, 
            r.aspect_ratio,
            r.solidity,
            r.confidence,
            r.centroid_x, 
            r.centroid_y,
            r.bbox_x, 
            r.bbox_y, 
            r.bbox_w, 
            r.bbox_h
        FROM rooms r
        JOIN floor_plans fp ON r.floor_plan_id = fp.id
        WHERE fp.plan_id = :plan_id
        ORDER BY r.room_index ASC;
        """
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"plan_id": str(plan_id)})

    def get_doors_df(self, plan_id: str) -> pd.DataFrame:
        """Retrieves doors for a floor plan as a pandas DataFrame."""
        query = """
        SELECT 
            d.door_index, 
            d.door_name, 
            d.pixel_area, 
            d.orientation, 
            d.is_entrance, 
            d.connected_room_indices,
            d.centroid_x, 
            d.centroid_y,
            d.bbox_x, 
            d.bbox_y, 
            d.bbox_w, 
            d.bbox_h
        FROM doors d
        JOIN floor_plans fp ON d.floor_plan_id = fp.id
        WHERE fp.plan_id = :plan_id
        ORDER BY d.door_index ASC;
        """
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"plan_id": str(plan_id)})

    def get_windows_df(self, plan_id: str) -> pd.DataFrame:
        """Retrieves windows for a floor plan as a pandas DataFrame."""
        query = """
        SELECT 
            w.window_index, 
            w.window_name, 
            w.pixel_area, 
            w.orientation,
            w.connected_room_index,
            w.centroid_x, 
            w.centroid_y,
            w.bbox_x, 
            w.bbox_y, 
            w.bbox_w, 
            w.bbox_h
        FROM windows w
        JOIN floor_plans fp ON w.floor_plan_id = fp.id
        WHERE fp.plan_id = :plan_id
        ORDER BY w.window_index ASC;
        """
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"plan_id": str(plan_id)})

    def get_connections_df(self, plan_id: str) -> pd.DataFrame:
        """Retrieves topological room connections for a floor plan."""
        query = """
        SELECT 
            rc.door_index, 
            rc.room_1_index, 
            rc.room_1_name, 
            rc.room_2_index, 
            rc.room_2_name, 
            rc.distance_px
        FROM room_connections rc
        JOIN floor_plans fp ON rc.floor_plan_id = fp.id
        WHERE fp.plan_id = :plan_id
        ORDER BY rc.door_index ASC;
        """
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"plan_id": str(plan_id)})

    def get_metadata(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves extraction metadata and validation report for a floor plan."""
        query = """
        SELECT em.*
        FROM extraction_metadata em
        JOIN floor_plans fp ON em.floor_plan_id = fp.id
        WHERE fp.plan_id = :plan_id;
        """
        with self.engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params={"plan_id": str(plan_id)})
            if df.empty:
                return None
            return df.iloc[0].to_dict()

    def execute_read_only_sql(self, sql_query: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Executes a validated read-only SQL query against SQLite.
        Returns:
            (records_as_list_of_dicts, column_names)
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_query))
            columns = list(result.keys())
            rows = result.fetchall()
            records = [dict(zip(columns, row)) for row in rows]
            return records, columns

    def get_db_schema_string(self) -> str:
        """Returns SQLite schema representation for LLM context."""
        return """
TABLE floor_plans (
    id INTEGER PRIMARY KEY,
    plan_id TEXT UNIQUE, -- e.g. '1', '2', '10'
    image_file TEXT,
    mask_file TEXT,
    width INTEGER,
    height INTEGER,
    total_pixels INTEGER,
    aspect_ratio FLOAT,
    indoor_pixels INTEGER,
    indoor_percentage FLOAT
);

TABLE rooms (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    room_index INTEGER, -- e.g. 1, 2, 3
    room_name TEXT, -- e.g. 'Room 1', 'Room 2'
    room_type TEXT, -- 'Living Room', 'Master Bedroom', 'Bedroom', 'Kitchen / Dining', 'Bathroom / WC', 'Balcony / Terrace', 'Hallway / Corridor', 'Utility / Study Room'
    raw_class TEXT,
    bbox_x INTEGER, bbox_y INTEGER, bbox_w INTEGER, bbox_h INTEGER,
    centroid_x INTEGER, centroid_y INTEGER,
    pixel_area INTEGER, -- Area in pixels (raw dataset has no scale calibration)
    aspect_ratio FLOAT,
    solidity FLOAT,
    confidence FLOAT
);

TABLE doors (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    door_index INTEGER,
    door_name TEXT, -- 'Door 1'
    bbox_x INTEGER, bbox_y INTEGER, bbox_w INTEGER, bbox_h INTEGER,
    centroid_x INTEGER, centroid_y INTEGER,
    pixel_area INTEGER,
    orientation TEXT, -- 'horizontal' or 'vertical'
    is_entrance BOOLEAN, -- 1 if main entrance opening to outside, else 0
    connected_room_indices TEXT -- Comma-separated room indices touching this door (e.g. '1,4')
);

TABLE windows (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    window_index INTEGER,
    window_name TEXT,
    bbox_x INTEGER, bbox_y INTEGER, bbox_w INTEGER, bbox_h INTEGER,
    centroid_x INTEGER, centroid_y INTEGER,
    pixel_area INTEGER,
    orientation TEXT
);

TABLE walls (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    wall_index INTEGER,
    bbox_x INTEGER, bbox_y INTEGER, bbox_w INTEGER, bbox_h INTEGER,
    pixel_area INTEGER
);

TABLE room_connections (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    door_index INTEGER,
    room_1_index INTEGER,
    room_2_index INTEGER,
    room_1_name TEXT,
    room_2_name TEXT,
    distance_px FLOAT -- Euclidean distance in pixels between room centroids
);

TABLE extraction_metadata (
    id INTEGER PRIMARY KEY,
    floor_plan_id INTEGER REFERENCES floor_plans(id),
    num_rooms INTEGER,
    num_doors INTEGER,
    num_windows INTEGER,
    num_walls INTEGER,
    num_connections INTEGER,
    total_room_area_px INTEGER,
    room_indoor_coverage_pct FLOAT,
    connectivity_ratio_pct FLOAT,
    extraction_confidence_score FLOAT,
    validation_status TEXT, -- 'VALIDATED', 'WARNING', 'DEFICIENT'
    limitations TEXT
);
"""
