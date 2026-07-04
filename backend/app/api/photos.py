import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.cv.pipeline import CataloguerError, process_photo
from app.db.models import Project, SourcePhoto, Stone
from app.db.session import get_db
from app.schemas.photo import PhotoInfo, PhotoResult

router = APIRouter(tags=["photos"])


@router.get("/photos/{photo_id}", response_model=PhotoInfo)
def get_photo(photo_id: uuid.UUID, db: Session = Depends(get_db)):
    photo = db.get(SourcePhoto, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")
    return PhotoInfo(
        id=photo.id,
        warped_url=f"/api/images/{photo.image_path}",
        px_per_cm=photo.px_per_cm,
        span_x_cm=photo.span_x_cm,
        span_y_cm=photo.span_y_cm,
    )


def _save(rel_path: str, data: bytes) -> None:
    abs_path = os.path.join(settings.image_dir, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(data)


@router.post("/projects/{project_id}/photos", response_model=PhotoResult)
async def upload_photo(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    span_x_cm: float = Form(100.0),
    span_y_cm: float = Form(100.0),
    storage_location: str = Form(""),
    min_side_cm: float = Form(8.0),
    max_side_cm: float = Form(45.0),
    px_per_cm: float = Form(4.0),
    threshold_mode: str = Form("otsu"),
    invert: bool = Form(False),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Empty upload")
    try:
        result = process_photo(
            data,
            span_x_cm,
            span_y_cm,
            px_per_cm=px_per_cm,
            min_side_cm=min_side_cm,
            max_side_cm=max_side_cm,
            threshold_mode=threshold_mode,
            invert=invert,
        )
    except CataloguerError as e:
        raise HTTPException(status_code=422, detail=str(e))

    photo_id = uuid.uuid4()
    warped_rel = f"{project_id}/photos/{photo_id}.jpg"
    _save(warped_rel, result["warped_jpg"])

    photo = SourcePhoto(
        id=photo_id,
        project_id=project_id,
        image_path=warped_rel,
        px_per_cm=result["px_per_cm"],
        span_x_cm=span_x_cm,
        span_y_cm=span_y_cm,
        storage_location=storage_location or None,
    )
    db.add(photo)

    stones: list[Stone] = []
    for cand in result["candidates"]:
        stone_id = uuid.uuid4()
        crop_rel = f"{project_id}/crops/{stone_id}.png"
        _save(crop_rel, cand["crop_png"])
        stone = Stone(
            id=stone_id,
            code="",  # assigned on confirm
            project_id=project_id,
            source_photo_id=photo_id,
            width_cm=cand["width_cm"],
            height_cm=cand["height_cm"],
            angle_deg=cand["angle_deg"],
            area_cm2=cand["area_cm2"],
            polygon=cand["polygon"],
            sheet_x_cm=cand["sheet_x_cm"],
            sheet_y_cm=cand["sheet_y_cm"],
            storage_location=storage_location or None,
            status="pending",
            crop_path=crop_rel,
        )
        db.add(stone)
        stones.append(stone)

    db.commit()
    for s in stones:
        db.refresh(s)

    return PhotoResult(
        source_photo_id=photo_id,
        warped_url=f"/api/images/{warped_rel}",
        px_per_cm=result["px_per_cm"],
        span_x_cm=span_x_cm,
        span_y_cm=span_y_cm,
        detected=len(stones),
        stones=stones,
    )
