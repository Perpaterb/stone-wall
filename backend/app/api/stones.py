import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import Project, Stone
from app.db.session import get_db
from app.schemas.stone import GenerateDummyIn, StoneRead, StoneUpdate
from app.stones.dummy import generate_dummy_stone_dicts

router = APIRouter(tags=["stones"])


@router.post("/projects/{project_id}/stones/generate-dummy")
def generate_dummy(
    project_id: uuid.UUID, payload: GenerateDummyIn, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    dicts = generate_dummy_stone_dicts(
        count=payload.count,
        seed=payload.seed,
        mean_w=payload.mean_w,
        mean_h=payload.mean_h,
        spread=payload.spread,
    )
    counter = project.stone_counter
    for d in dicts:
        counter += 1
        db.add(
            Stone(
                project_id=project_id,
                code=f"S{counter:04d}",
                width_cm=d["width_cm"],
                height_cm=d["height_cm"],
                area_cm2=d["area_cm2"],
                polygon=d["polygon"],
                status="available",
            )
        )
    project.stone_counter = counter
    db.commit()

    total = db.scalar(
        select(func.count()).select_from(Stone).where(Stone.project_id == project_id)
    )
    return {"created": len(dicts), "total": total}


@router.get("/projects/{project_id}/stones", response_model=list[StoneRead])
def list_stones(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(
        select(Stone).where(Stone.project_id == project_id).order_by(Stone.code)
    ).all()


@router.delete("/projects/{project_id}/stones")
def clear_stones(project_id: uuid.UUID, db: Session = Depends(get_db)):
    result = db.execute(delete(Stone).where(Stone.project_id == project_id))
    project = db.get(Project, project_id)
    if project is not None:
        project.stone_counter = 0  # dummy workflow: reset so re-gen starts at S0001
    db.commit()
    return {"deleted": result.rowcount}


@router.patch("/stones/{stone_id}", response_model=StoneRead)
def update_stone(
    stone_id: uuid.UUID, payload: StoneUpdate, db: Session = Depends(get_db)
):
    stone = db.get(Stone, stone_id)
    if stone is None:
        raise HTTPException(status_code=404, detail="Stone not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stone, field, value)
    db.commit()
    db.refresh(stone)
    return stone
