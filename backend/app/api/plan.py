import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.db.models import PlanShape, Project, Stone
from app.db.session import get_db
from app.geometry import polygon_area_cm2
from app.schemas.coverage import Coverage
from app.schemas.plan import PlanIn, PlanOut

router = APIRouter(prefix="/projects/{project_id}", tags=["plan"])


def _require_project(project_id: uuid.UUID, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _load_shapes(project_id: uuid.UUID, db: Session) -> list[PlanShape]:
    return list(
        db.scalars(
            select(PlanShape)
            .where(PlanShape.project_id == project_id)
            .order_by(PlanShape.z_order)
        ).all()
    )


@router.get("/plan", response_model=PlanOut)
def get_plan(project_id: uuid.UUID, db: Session = Depends(get_db)):
    _require_project(project_id, db)
    return {"shapes": _load_shapes(project_id, db)}


@router.put("/plan", response_model=PlanOut)
def put_plan(project_id: uuid.UUID, payload: PlanIn, db: Session = Depends(get_db)):
    _require_project(project_id, db)
    # Full replace: the editor sends the complete set of shapes on save.
    db.execute(delete(PlanShape).where(PlanShape.project_id == project_id))
    for i, s in enumerate(payload.shapes):
        db.add(
            PlanShape(
                project_id=project_id,
                kind=s.kind,
                polygon=s.polygon,
                z_order=s.z_order or i,
            )
        )
    db.commit()
    return {"shapes": _load_shapes(project_id, db)}


@router.get("/coverage", response_model=Coverage)
def get_coverage(project_id: uuid.UUID, db: Session = Depends(get_db)):
    _require_project(project_id, db)
    shapes = _load_shapes(project_id, db)
    wall = sum(polygon_area_cm2(s.polygon) for s in shapes if s.kind == "wall")
    neg = sum(polygon_area_cm2(s.polygon) for s in shapes if s.kind == "negative")
    net = max(0.0, wall - neg)
    # Available stones (dummy from M2, real from M3). Used/held stones excluded.
    stone_area = (
        db.scalar(
            select(func.coalesce(func.sum(Stone.area_cm2), 0.0)).where(
                Stone.project_id == project_id, Stone.status == "available"
            )
        )
        or 0.0
    )
    stone_count = (
        db.scalar(
            select(func.count())
            .select_from(Stone)
            .where(Stone.project_id == project_id, Stone.status == "available")
        )
        or 0
    )
    ratio = stone_area / net if net > 0 else 0.0
    return Coverage(
        wall_area_cm2=wall,
        negative_area_cm2=neg,
        net_wall_area_cm2=net,
        stone_area_cm2=stone_area,
        stone_count=stone_count,
        coverage_ratio=ratio,
    )
