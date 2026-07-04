import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import buildmaps, photos, plan, projects, stones
from app.config import settings
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables directly. Alembic migrations are deferred until a schema ALTER
    # is needed (additive tables are handled fine by create_all).
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.image_dir, exist_ok=True)
    yield


app = FastAPI(title="Sandstone Wall Builder API", lifespan=lifespan)

app.include_router(projects.router, prefix="/api")
app.include_router(plan.router, prefix="/api")
app.include_router(stones.router, prefix="/api")
app.include_router(buildmaps.router, prefix="/api")
app.include_router(photos.router, prefix="/api")

os.makedirs(settings.image_dir, exist_ok=True)
app.mount("/api/images", StaticFiles(directory=settings.image_dir), name="images")


@app.get("/api/health")
def health():
    return {"status": "ok"}
