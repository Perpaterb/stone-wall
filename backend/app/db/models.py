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
