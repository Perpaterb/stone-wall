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


class ConfirmStonesIn(BaseModel):
    ordered_ids: list[uuid.UUID]  # kept stones, in reading order
    deleted_ids: list[uuid.UUID] = []  # false positives to drop


class StoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    width_cm: float
    height_cm: float
    area_cm2: float
    angle_deg: float
    status: str
    polygon: list[list[float]]
    label: str | None
    notes: str
    storage_location: str | None
    crop_path: str | None
    source_photo_id: uuid.UUID | None
    sheet_x_cm: float | None
    sheet_y_cm: float | None
