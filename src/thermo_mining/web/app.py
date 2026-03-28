from fastapi import FastAPI

from .routes_api_chat import router as chat_router
from .routes_api_fs import router as fs_router
from .routes_api_plan import router as plan_router
from .routes_api_runs import router as runs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Thermo Mining Control Plane")
    app.include_router(fs_router)
    app.include_router(plan_router)
    app.include_router(runs_router)
    app.include_router(chat_router)
    return app
