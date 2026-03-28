from pathlib import Path

from fastapi import APIRouter, Query

from thermo_mining.control_plane.fastq_pairing import detect_fastq_pairs, scan_input_bundles
from thermo_mining.control_plane.fs_service import list_path_entries, search_path_entries

router = APIRouter(prefix="/api/fs", tags=["fs"])


@router.get("/list")
def fs_list(path: str = Query(...)) -> list[dict[str, object]]:
    return [row.model_dump() for row in list_path_entries(path)]


@router.get("/search")
def fs_search(root: str, q: str) -> list[dict[str, object]]:
    return [row.model_dump() for row in search_path_entries(root, q)]


@router.post("/pair-fastq")
def pair_fastq(payload: dict[str, list[str]]) -> list[dict[str, object]]:
    return [row.model_dump() for row in detect_fastq_pairs([Path(item) for item in payload["paths"]])]


@router.post("/scan-bundles")
def scan_bundles(payload: dict[str, str]) -> list[dict[str, object]]:
    return [row.model_dump() for row in scan_input_bundles(payload["root"], payload["output_root"])]
