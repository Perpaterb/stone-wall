import uuid

from pydantic import BaseModel, ConfigDict


class GenerateDummyIn(BaseModel):
    count: int = 200
    seed: int = 1
    mean_w: float = 30.0
    mean_h: float = 13.0
    spread: float = 6.0


class StoneUpdate(BaseModel):
    status: str | None = None  # available | hold_unless_needed | used
    notes: str | None = None
    label: str | None = None
    storage_location: str | None = None


class StoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    width_cm: float
    height_cm: float
    area_cm2: float
    status: str
    polygon: list[list[float]]
    label: str | None
    notes: str
    storage_location: str | None
