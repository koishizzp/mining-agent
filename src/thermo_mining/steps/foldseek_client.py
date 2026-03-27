from pathlib import Path
from time import perf_counter

import requests

from ..io_utils import write_done_json, write_scores_tsv
from ..models import DoneRecord


def summarize_foldseek_hits(rows: list[dict[str, object]]) -> float:
    if not rows:
        return 0.0
    return max(float(row.get("tmscore", 0.0)) for row in rows)


class FoldseekClient:
    def __init__(self, base_url: str, timeout_seconds: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_structure(self, pdb_path: str, database: str, topk: int, min_tmscore: float) -> dict[str, object]:
        response = requests.post(
            f"{self.base_url}/search_structure",
            json={
                "pdb_path": pdb_path,
                "database": database,
                "topk": topk,
                "min_tmscore": min_tmscore,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()


def run_foldseek_stage(
    structure_manifest: list[dict[str, str]],
    stage_dir: str | Path,
    base_url: str,
    database: str,
    topk: int,
    min_tmscore: float,
    software_version: str,
) -> dict[str, Path]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    client = FoldseekClient(base_url=base_url)

    rows: list[dict[str, object]] = []
    for entry in structure_manifest:
        payload = client.search_structure(entry["pdb_path"], database, topk, min_tmscore)
        hits = payload.get("results", [])
        rows.append(
            {
                "protein_id": entry["protein_id"],
                "foldseek_score": round(summarize_foldseek_hits(hits), 4),
            }
        )

    write_scores_tsv(stage_dir / "scores.tsv", rows, ["protein_id", "foldseek_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="05_foldseek_confirm",
            input_hash="structure-manifest",
            parameters={"database": database, "topk": topk, "min_tmscore": min_tmscore},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"foldseek_scores_tsv": stage_dir / "scores.tsv"}
