import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    kind: str = "dummy"  # dummy | real
    grout_min_cm: float = 1.0
    grout_max_cm: float = 3.0
    dummy_params: dict | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    grout_min_cm: float
    grout_max_cm: float
    dummy_params: dict | None
    stone_counter: int
    created_at: datetime
