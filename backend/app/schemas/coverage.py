from pydantic import BaseModel


class Coverage(BaseModel):
    wall_area_cm2: float
    negative_area_cm2: float
    net_wall_area_cm2: float
    stone_area_cm2: float
    stone_count: int
    coverage_ratio: float  # stone_area / net_wall_area, 0 when there is no wall
