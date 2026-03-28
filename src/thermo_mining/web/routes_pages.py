from importlib.resources import files

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    del request
    return HTMLResponse(files("thermo_mining.web").joinpath("templates", "index.html").read_text(encoding="utf-8"))
