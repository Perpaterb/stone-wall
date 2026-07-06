import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BuildMapCreate(BaseModel):
    name: str | None = None
    seed: int | None = None
    method: str = "spiral"  # spiral | skyline
    seeds: int = 4
    stagger_min_cm: float = 6.0
    through_stone_prob: float = 0.08


class BuildMapSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    seed: int
    report: dict | None
    share_key: str
    created_at: datetime


class PlacementOut(BaseModel):
    stone_id: uuid.UUID
    code: str
    x_cm: float
    y_cm: float
    w_cm: float
    h_cm: float
    rotation_deg: float
    course_index: int
    cut: dict | None
    status: str
    crop_path: str | None
    polygon: list[list[float]]


class BuildMapDetail(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    seed: int
    params: dict
    report: dict | None
    share_key: str
    created_at: datetime
    placements: list[PlacementOut]


class MarkUsedIn(BaseModel):
    used: bool
    marked_by: str | None = None


class ManualPlacement(BaseModel):
    code: str
    x_cm: float
    y_cm: float
    w_cm: float
    h_cm: float
    rotation_deg: float = 0.0
    cut: dict | None = None


class ManualBuildMapIn(BaseModel):
    name: str = "Claude's attempt"
    walls: list[list[list[float]]]
    negatives: list[list[list[float]]] = []
    placements: list[ManualPlacement]
