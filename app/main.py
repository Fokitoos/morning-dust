import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import calendar, commute, health, todo, weather
from app.services.commute_scheduler import run_daily_commute_refresh
from app.services.commute_service import get_commute_service

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_daily_commute_refresh(get_commute_service()))
    try:
        yield
    finally:
        task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
    app.include_router(todo.router, prefix="/api/todo", tags=["todo"])
    app.include_router(commute.router, prefix="/api/commute", tags=["commute"])
    app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def _index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
