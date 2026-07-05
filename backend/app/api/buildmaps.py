import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BuildMap, PlanShape, Placement, Project, Stone, UsageEvent
from app.db.session import get_db
from app.schemas.buildmap import (
    BuildMapCreate,
    BuildMapDetail,
    BuildMapSummary,
    MarkUsedIn,
    PlacementOut,
)
from app.solver.packer import solve
from app.solver.packer_spiral import solve_spiral

router = APIRouter(tags=["buildmaps"])


@router.post("/projects/{project_id}/buildmaps", response_model=BuildMapSummary)
def create_buildmap(
    project_id: uuid.UUID, payload: BuildMapCreate, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    shapes = db.scalars(
        select(PlanShape).where(PlanShape.project_id == project_id)
    ).all()
    walls = [s.polygon for s in shapes if s.kind == "wall"]
    negs = [s.polygon for s in shapes if s.kind == "negative"]
    if not walls:
        raise HTTPException(status_code=400, detail="Draw at least one wall first")

    stone_rows = db.scalars(
        select(Stone).where(
            Stone.project_id == project_id, Stone.status == "available"
        )
    ).all()
    if not stone_rows:
        raise HTTPException(status_code=400, detail="No available stones")

    stones = [
        {
            "id": s.id,
            "code": s.code,
            "width_cm": s.width_cm,
            "height_cm": s.height_cm,
            "polygon": s.polygon,
        }
        for s in stone_rows
    ]

    seed = payload.seed if payload.seed is not None else 1
    method = payload.method or "spiral"
    params = {
        "seed": seed,
        "method": method,
        "seeds": payload.seeds,
        "grout_min_cm": project.grout_min_cm,
        "grout_max_cm": project.grout_max_cm,
        "stagger_min_cm": payload.stagger_min_cm,
        "through_stone_prob": payload.through_stone_prob,
    }
    if method == "spiral":
        placements, report = solve_spiral(walls, negs, stones, params)
    else:
        placements, report = solve(walls, negs, stones, params)
    # Snapshot the wall shapes into the build map so its view can draw the wall
    # even if the plan changes later.
    params["walls"] = walls
    params["negatives"] = negs

    bm = BuildMap(
        project_id=project_id,
        name=payload.name or "Build map",
        seed=seed,
        params=params,
        share_key=secrets.token_urlsafe(8),
        report=report,
    )
    db.add(bm)
    db.flush()
    for p in placements:
        db.add(
            Placement(
                build_map_id=bm.id,
                stone_id=p["stone_id"],
                x_cm=p["x_cm"],
                y_cm=p["y_cm"],
                w_cm=p["w_cm"],
                h_cm=p["h_cm"],
                rotation_deg=p["rotation_deg"],
                course_index=p["course_index"],
                cut=p["cut"],
            )
        )
    db.commit()
    db.refresh(bm)
    return bm


@router.get("/projects/{project_id}/buildmaps", response_model=list[BuildMapSummary])
def list_buildmaps(project_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.scalars(
        select(BuildMap)
        .where(BuildMap.project_id == project_id)
        .order_by(BuildMap.created_at.desc())
    ).all()


@router.get("/buildmaps/{build_map_id}", response_model=BuildMapDetail)
def get_buildmap(build_map_id: uuid.UUID, db: Session = Depends(get_db)):
    bm = db.get(BuildMap, build_map_id)
    if bm is None:
        raise HTTPException(status_code=404, detail="Build map not found")
    rows = db.execute(
        select(
            Placement, Stone.code, Stone.status, Stone.crop_path, Stone.polygon
        )
        .join(Stone, Stone.id == Placement.stone_id)
        .where(Placement.build_map_id == build_map_id)
        .order_by(Placement.course_index)
    ).all()
    placements = [
        PlacementOut(
            stone_id=pl.stone_id,
            code=code,
            x_cm=pl.x_cm,
            y_cm=pl.y_cm,
            w_cm=pl.w_cm,
            h_cm=pl.h_cm,
            rotation_deg=pl.rotation_deg,
            course_index=pl.course_index,
            cut=pl.cut,
            status=status,
            crop_path=crop_path,
            polygon=polygon,
        )
        for pl, code, status, crop_path, polygon in rows
    ]
    return BuildMapDetail(
        id=bm.id,
        project_id=bm.project_id,
        name=bm.name,
        seed=bm.seed,
        params=bm.params or {},
        report=bm.report,
        share_key=bm.share_key,
        created_at=bm.created_at,
        placements=placements,
    )


@router.post("/buildmaps/{build_map_id}/placements/{stone_id}/used")
def mark_used(
    build_map_id: uuid.UUID,
    stone_id: uuid.UUID,
    payload: MarkUsedIn,
    db: Session = Depends(get_db),
):
    bm = db.get(BuildMap, build_map_id)
    if bm is None:
        raise HTTPException(status_code=404, detail="Build map not found")
    stone = db.get(Stone, stone_id)
    if stone is None:
        raise HTTPException(status_code=404, detail="Stone not found")
    # Used state is authoritative on the stone (a physically used stone is gone
    # from every future solve). The event log records who/when.
    stone.status = "used" if payload.used else "available"
    db.add(
        UsageEvent(
            build_map_id=build_map_id,
            stone_id=stone_id,
            used=payload.used,
            marked_by=payload.marked_by,
        )
    )
    db.commit()
    return {"stone_id": str(stone_id), "status": stone.status}


@router.delete("/buildmaps/{build_map_id}")
def delete_buildmap(build_map_id: uuid.UUID, db: Session = Depends(get_db)):
    bm = db.get(BuildMap, build_map_id)
    if bm is None:
        raise HTTPException(status_code=404, detail="Build map not found")
    db.delete(bm)
    db.commit()
    return {"deleted": True}
