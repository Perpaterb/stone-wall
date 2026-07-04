import uuid

from pydantic import BaseModel

from app.schemas.stone import StoneRead


class PhotoResult(BaseModel):
    source_photo_id: uuid.UUID
    warped_url: str
    px_per_cm: float
    span_x_cm: float
    span_y_cm: float
    detected: int
    stones: list[StoneRead]  # status 'pending' until confirmed


class PhotoInfo(BaseModel):
    id: uuid.UUID
    warped_url: str
    px_per_cm: float
    span_x_cm: float
    span_y_cm: float
