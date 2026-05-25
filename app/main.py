from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import commute, health, todo, weather


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)

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

    return app


app = create_app()
