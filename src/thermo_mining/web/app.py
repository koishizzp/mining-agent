from fastapi import FastAPI

from .routes_api_fs import router as fs_router
from .routes_api_plan import router as plan_router


def create_app() -> FastAPI:
    app = FastAPI(title="Thermo Mining Control Plane")
    app.include_router(fs_router)
    app.include_router(plan_router)
    return app
