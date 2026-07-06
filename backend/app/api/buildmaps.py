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
    ManualBuildMapIn,
    MarkUsedIn,
    PlacementOut,
)
from app.solver.packer import VERSION as SKYLINE_VERSION
from app.solver.packer import solve
from app.solver.packer_spiral import BEAM_VERSION
from app.solver.packer_spiral import VERSION as SPIRAL_VERSION
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
    seed_points: list = []
    if method in ("spiral", "beam"):
        params["mode"] = "beam" if method == "beam" else "spiral"
        placements, report, seed_points = solve_spiral(walls, negs, stones, params)
        params["solver_version"] = BEAM_VERSION if method == "beam" else SPIRAL_VERSION
    else:
        placements, report = solve(walls, negs, stones, params)
        params["solver_version"] = SKYLINE_VERSION
    # Snapshot the wall shapes + seed points into the build map so its view can
    # draw them even if the plan changes later.
    params["walls"] = walls
    params["negatives"] = negs
    params["seed_points"] = seed_points

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
    for i, p in enumerate(placements):
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
                seq=i,
                cut=p["cut"],
            )
        )
    db.commit()
    db.refresh(bm)
    return bm


@router.post("/projects/{project_id}/buildmaps/manual", response_model=BuildMapSummary)
def create_manual_buildmap(
    project_id: uuid.UUID, payload: ManualBuildMapIn, db: Session = Depends(get_db)
):
    """Create a build map from an explicit, hand-authored placement list."""
    from app.geometry import polygon_area_cm2

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    by_code = {
        s.code: s
        for s in db.scalars(select(Stone).where(Stone.project_id == project_id)).all()
    }
    net = max(
        0.0,
        sum(polygon_area_cm2(w) for w in payload.walls)
        - sum(polygon_area_cm2(n) for n in payload.negatives),
    )
    placed = sum(p.w_cm * p.h_cm for p in payload.placements)
    report = {
        "coverage_pct": round(100.0 * placed / net, 1) if net > 0 else 0.0,
        "stones_used": len(payload.placements),
        "stones_available": len(by_code),
        "courses": 0,
        "cut_count": sum(1 for p in payload.placements if p.cut),
        "cut_total_cm": 0.0,
        "gap_count": 0,
        "gap_total_cm": 0.0,
        "joint_min_cm": 0.0,
        "joint_max_cm": 0.0,
        "joint_mean_cm": 0.0,
    }
    bm = BuildMap(
        project_id=project_id,
        name=payload.name,
        seed=0,
        params={
            "method": "claude",
            "walls": payload.walls,
            "negatives": payload.negatives,
            "seed_points": [],
        },
        share_key=secrets.token_urlsafe(8),
        report=report,
    )
    db.add(bm)
    db.flush()
    skipped = 0
    seq = 0
    for p in payload.placements:
        stone = by_code.get(p.code)
        if stone is None:
            skipped += 1
            continue
        db.add(
            Placement(
                build_map_id=bm.id,
                stone_id=stone.id,
                x_cm=p.x_cm,
                y_cm=p.y_cm,
                w_cm=p.w_cm,
                h_cm=p.h_cm,
                rotation_deg=p.rotation_deg,
                course_index=0,
                seq=seq,
                cut=p.cut,
            )
        )
        seq += 1
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
        .order_by(Placement.seq)
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
