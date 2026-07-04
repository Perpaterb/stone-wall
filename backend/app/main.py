from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import projects
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # M0: create tables directly. Proper Alembic migrations arrive in M1 once the
    # schema grows beyond the single projects table.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Sandstone Wall Builder API", lifespan=lifespan)

app.include_router(projects.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
