from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from thermo_mining.control_plane.fastq_pairing import detect_fastq_pairs, scan_input_bundles
from thermo_mining.control_plane.fs_service import list_path_entries, search_path_entries

router = APIRouter(prefix="/api/fs", tags=["fs"])


class PairFastqRequest(BaseModel):
    paths: list[str]


class ScanBundlesRequest(BaseModel):
    root: str
    output_root: str


def _raise_fs_http_error(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (NotADirectoryError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/list")
def fs_list(path: str = Query(...)) -> list[dict[str, object]]:
    try:
        return [row.model_dump() for row in list_path_entries(path)]
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        _raise_fs_http_error(exc)


@router.get("/search")
def fs_search(root: str, q: str) -> list[dict[str, object]]:
    try:
        return [row.model_dump() for row in search_path_entries(root, q)]
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        _raise_fs_http_error(exc)


@router.post("/pair-fastq")
def pair_fastq(payload: PairFastqRequest) -> list[dict[str, object]]:
    return [row.model_dump() for row in detect_fastq_pairs([Path(item) for item in payload.paths])]


@router.post("/scan-bundles")
def scan_bundles(payload: ScanBundlesRequest) -> list[dict[str, object]]:
    try:
        return [row.model_dump() for row in scan_input_bundles(payload.root, payload.output_root)]
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        _raise_fs_http_error(exc)
