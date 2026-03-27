import csv
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def build_protrek_index_command(
    python_bin: str,
    script_path: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    input_faa: str | Path,
    output_dir: str | Path,
    batch_size: int,
) -> list[str]:
    return [
        python_bin,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--weights-dir",
        str(weights_dir),
        "--input-faa",
        str(input_faa),
        "--output-dir",
        str(output_dir),
        "--batch-size",
        str(batch_size),
    ]


def build_protrek_query_command(
    python_bin: str,
    script_path: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    index_dir: str | Path,
    query_texts: list[str],
    output_tsv: str | Path,
    top_k: int,
) -> list[str]:
    cmd = [
        python_bin,
        str(script_path),
        "--repo-root",
        str(repo_root),
        "--weights-dir",
        str(weights_dir),
        "--index-dir",
        str(index_dir),
        "--output-tsv",
        str(output_tsv),
        "--top-k",
        str(top_k),
    ]
    for query_text in query_texts:
        cmd.extend(["--query-text", query_text])
    return cmd


def collapse_query_scores(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    best: dict[str, float] = {}
    for row in rows:
        protein_id = str(row["protein_id"])
        score = float(row["protrek_score"])
        best[protein_id] = max(best.get(protein_id, 0.0), score)
    return [{"protein_id": protein_id, "protrek_score": score} for protein_id, score in sorted(best.items())]


def run_protrek_stage(
    input_faa: str | Path,
    stage_dir: str | Path,
    python_bin: str,
    index_script: str | Path,
    query_script: str | Path,
    repo_root: str | Path,
    weights_dir: str | Path,
    query_texts: list[str],
    batch_size: int,
    top_k: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[str]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    index_dir = stage_dir / "index"
    raw_query_tsv = stage_dir / "protrek_raw.tsv"

    index_cmd = build_protrek_index_command(python_bin, index_script, repo_root, weights_dir, input_faa, index_dir, batch_size)
    query_cmd = build_protrek_query_command(python_bin, query_script, repo_root, weights_dir, index_dir, query_texts, raw_query_tsv, top_k)
    if dry_run:
        return {"index_cmd": index_cmd, "query_cmd": query_cmd}

    subprocess.run(index_cmd, check=True)
    subprocess.run(query_cmd, check=True)

    raw_rows: list[dict[str, object]] = []
    with raw_query_tsv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            raw_rows.append(
                {
                    "protein_id": row["protein_id"],
                    "query_text": row["query_text"],
                    "protrek_score": float(row["protrek_score"]),
                }
            )

    collapsed = collapse_query_scores(raw_rows)
    write_scores_tsv(stage_dir / "scores.tsv", collapsed, ["protein_id", "protrek_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="04_protrek_recall",
            input_hash=sha256_file(input_faa),
            parameters={"query_texts": query_texts, "top_k": top_k, "batch_size": batch_size},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(collapsed),
            reject_count=0,
        ),
    )
    return {"protrek_scores_tsv": stage_dir / "scores.tsv"}
