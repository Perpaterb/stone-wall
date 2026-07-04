import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, default="dummy")  # dummy | real
    grout_min_cm: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    grout_max_cm: Mapped[float] = mapped_column(Float, nullable=False, default=3.0)
    dummy_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stone_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PlanShape(Base):
    __tablename__ = "plan_shapes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)  # wall | negative
    polygon: Mapped[list] = mapped_column(JSONB, nullable=False)  # [[x_cm, y_cm], ...]
    z_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Stone(Base):
    __tablename__ = "stones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String, nullable=False)  # e.g. S0001
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    width_cm: Mapped[float] = mapped_column(Float, nullable=False)  # longer side
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)  # shorter side
    angle_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    area_cm2: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    polygon: Mapped[list] = mapped_column(JSONB, nullable=False)  # local frame, cm
    sheet_x_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    sheet_y_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")
    storage_location: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="available"
    )  # available | hold_unless_needed | used
    crop_path: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BuildMap(Base):
    __tablename__ = "build_maps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False, default="Build map")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    share_key: Mapped[str] = mapped_column(String, nullable=False)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Placement(Base):
    __tablename__ = "placements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    build_map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("build_maps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stones.id", ondelete="CASCADE"), nullable=False
    )
    x_cm: Mapped[float] = mapped_column(Float, nullable=False)  # top-left on the wall
    y_cm: Mapped[float] = mapped_column(Float, nullable=False)
    w_cm: Mapped[float] = mapped_column(Float, nullable=False)  # placed horizontal size
    h_cm: Mapped[float] = mapped_column(Float, nullable=False)  # placed vertical size
    rotation_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    course_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cut: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    grout_edges: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
