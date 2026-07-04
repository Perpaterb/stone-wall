import uuid

from pydantic import BaseModel, ConfigDict


class PlanShapeIn(BaseModel):
    kind: str  # wall | negative
    polygon: list[list[float]]
    z_order: int = 0


class PlanShapeOut(PlanShapeIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class PlanIn(BaseModel):
    shapes: list[PlanShapeIn]


class PlanOut(BaseModel):
    shapes: list[PlanShapeOut]
