"""FastAPI Application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from community_service_desk import __version__
from community_service_desk.api import api_router
from community_service_desk.config import get_settings
from community_service_desk.database import create_all_tables
from community_service_desk.web import web_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure upload directory exists
    settings = get_settings()
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    # Attempt table creation if database is connected
    try:
        create_all_tables()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Community Service Desk",
    description=(
        "A lightweight, production-minded ticketing and support system for community organizations, "
        "schools, associations, and internal support teams. Preserves structured resolution knowledge "
        "to assist future support."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Mount static assets
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount API and Web UI routes
app.include_router(api_router)
app.include_router(web_router)
