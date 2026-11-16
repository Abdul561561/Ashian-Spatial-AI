import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class FloorPlan(Base):
    """Represents an architectural floor plan document."""
    __tablename__ = "floor_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(50), unique=True, nullable=False, index=True)
    image_file = Column(String(255), nullable=False)
    mask_file = Column(String(255), nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    channels = Column(Integer, default=3)
    total_pixels = Column(Integer, nullable=False)
    aspect_ratio = Column(Float, nullable=False)
    indoor_pixels = Column(Integer, default=0)
    indoor_percentage = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    # Relationships
    rooms = relationship("Room", back_populates="floor_plan", cascade="all, delete-orphan")
    doors = relationship("Door", back_populates="floor_plan", cascade="all, delete-orphan")
    windows = relationship("Window", back_populates="floor_plan", cascade="all, delete-orphan")
    walls = relationship("Wall", back_populates="floor_plan", cascade="all, delete-orphan")
    connections = relationship("RoomConnection", back_populates="floor_plan", cascade="all, delete-orphan")
    metadata_record = relationship("ExtractionMetadata", back_populates="floor_plan", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FloorPlan(id={self.id}, plan_id='{self.plan_id}', dims={self.width}x{self.height})>"


class Room(Base):
    """Represents an individual extracted room or indoor functional space."""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    room_index = Column(Integer, nullable=False)
    room_name = Column(String(100), nullable=False)
    room_type = Column(String(100), nullable=False, index=True)
    raw_class = Column(String(50), nullable=False)
    semantic_class = Column(String(50), default="Primary Room")
    spatial_category = Column(String(50), default="Habitable Room")
    is_habitable_room = Column(Boolean, default=True)
    inferred_type = Column(String(100), default="Unspecified")
    window_count = Column(Integer, default=0)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    centroid_x = Column(Integer, nullable=False)
    centroid_y = Column(Integer, nullable=False)
    pixel_area = Column(Integer, nullable=False)
    aspect_ratio = Column(Float, nullable=False)
    solidity = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)

    floor_plan = relationship("FloorPlan", back_populates="rooms")

    def __repr__(self):
        return f"<Room(id={self.id}, plan={self.floor_plan_id}, name='{self.room_name}', type='{self.room_type}', area={self.pixel_area}px)>"


class Door(Base):
    """Represents a door or opening connecting spaces."""
    __tablename__ = "doors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    door_index = Column(Integer, nullable=False)
    door_name = Column(String(100), nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    centroid_x = Column(Integer, nullable=False)
    centroid_y = Column(Integer, nullable=False)
    pixel_area = Column(Integer, nullable=False)
    orientation = Column(String(20), default="horizontal")
    is_entrance = Column(Boolean, default=False)
    connected_room_indices = Column(String(100), default="")

    floor_plan = relationship("FloorPlan", back_populates="doors")

    def __repr__(self):
        return f"<Door(id={self.id}, plan={self.floor_plan_id}, name='{self.door_name}', is_entrance={self.is_entrance})>"


class Window(Base):
    """Represents an exterior window opening."""
    __tablename__ = "windows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    window_index = Column(Integer, nullable=False)
    window_name = Column(String(100), nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    centroid_x = Column(Integer, nullable=False)
    centroid_y = Column(Integer, nullable=False)
    pixel_area = Column(Integer, nullable=False)
    orientation = Column(String(20), default="horizontal")
    connected_room_index = Column(Integer, nullable=True)

    floor_plan = relationship("FloorPlan", back_populates="windows")

    def __repr__(self):
        return f"<Window(id={self.id}, plan={self.floor_plan_id}, name='{self.window_name}')>"


class Wall(Base):
    """Represents structural wall elements."""
    __tablename__ = "walls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    wall_index = Column(Integer, nullable=False)
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_w = Column(Integer, nullable=False)
    bbox_h = Column(Integer, nullable=False)
    pixel_area = Column(Integer, nullable=False)

    floor_plan = relationship("FloorPlan", back_populates="walls")

    def __repr__(self):
        return f"<Wall(id={self.id}, plan={self.floor_plan_id}, index={self.wall_index}, area={self.pixel_area}px)>"


class RoomConnection(Base):
    """Represents a topological physical passage between two rooms via a door."""
    __tablename__ = "room_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    door_id = Column(Integer, nullable=True)
    door_index = Column(Integer, nullable=False)
    room_1_index = Column(Integer, nullable=False)
    room_2_index = Column(Integer, nullable=False)
    room_1_name = Column(String(100), nullable=False)
    room_2_name = Column(String(100), nullable=False)
    distance_px = Column(Float, nullable=False)

    floor_plan = relationship("FloorPlan", back_populates="connections")

    def __repr__(self):
        return f"<RoomConnection(plan={self.floor_plan_id}, {self.room_1_name} <-> {self.room_2_name}, dist={self.distance_px}px)>"


class ExtractionMetadata(Base):
    """Stores extraction audit metrics, validation status, confidence, and dataset limitations."""
    __tablename__ = "extraction_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    num_rooms = Column(Integer, nullable=False)
    total_detected_regions = Column(Integer, default=0)
    num_habitable_rooms = Column(Integer, default=0)
    num_service_rooms = Column(Integer, default=0)
    num_balconies = Column(Integer, default=0)
    num_corridors = Column(Integer, default=0)
    room_count_breakdown = Column(String(255), default="")
    num_doors = Column(Integer, nullable=False)
    num_windows = Column(Integer, nullable=False)
    num_walls = Column(Integer, nullable=False)
    num_connections = Column(Integer, nullable=False)
    total_room_area_px = Column(Integer, nullable=False)
    room_indoor_coverage_pct = Column(Float, nullable=False)
    connectivity_ratio_pct = Column(Float, nullable=False)
    extraction_confidence_score = Column(Float, nullable=False)
    validation_status = Column(String(50), nullable=False)
    limitations = Column(Text, nullable=False)
    extracted_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    floor_plan = relationship("FloorPlan", back_populates="metadata_record")

    def __repr__(self):
        return f"<ExtractionMetadata(plan={self.floor_plan_id}, confidence={self.extraction_confidence_score}%, status='{self.validation_status}')>"
