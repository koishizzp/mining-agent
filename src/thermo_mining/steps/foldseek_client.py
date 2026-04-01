import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import write_done_json, write_scores_tsv
from ..models import DoneRecord


def _path_text(value: str | Path) -> str:
    if isinstance(value, Path):
        return str(value) if value.drive else value.as_posix()
    return str(value)


def build_foldseek_easy_search_command(
    foldseek_bin: str,
    query_pdb: str | Path,
    database_path: str | Path,
    output_tsv: str | Path,
    tmp_dir: str | Path,
    topk: int,
) -> list[str]:
    return [
        foldseek_bin,
        "easy-search",
        _path_text(query_pdb),
        _path_text(database_path),
        _path_text(output_tsv),
        _path_text(tmp_dir),
        "--format-output",
        "query,target,alntmscore",
        "--max-seqs",
        str(topk),
    ]


def summarize_foldseek_hits(rows: list[dict[str, object]], min_tmscore: float) -> float:
    passing = [float(row["alntmscore"]) for row in rows if float(row["alntmscore"]) >= min_tmscore]
    return max(passing) if passing else 0.0


def run_foldseek_stage(
    structure_manifest: list[dict[str, str]],
    stage_dir: str | Path,
    foldseek_bin: str,
    database_path: str | Path,
    topk: int,
    min_tmscore: float,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[list[str]]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    raw_dir = stage_dir / "raw"
    tmp_root = stage_dir / "tmp"
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    tmp_root.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    rows: list[dict[str, object]] = []
    for entry in structure_manifest:
        output_tsv = raw_dir / f"{entry['protein_id']}.tsv"
        tmp_dir = tmp_root / entry["protein_id"]
        cmd = build_foldseek_easy_search_command(
            foldseek_bin=foldseek_bin,
            query_pdb=entry["pdb_path"],
            database_path=database_path,
            output_tsv=output_tsv,
            tmp_dir=tmp_dir,
            topk=topk,
        )
        commands.append(cmd)
        if dry_run:
            continue
        subprocess.run(cmd, check=True)

        parsed_rows: list[dict[str, object]] = []
        for line in output_tsv.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            query, target, alntmscore = line.split("\t")
            parsed_rows.append({"query": query, "target": target, "alntmscore": float(alntmscore)})
        rows.append(
            {
                "protein_id": entry["protein_id"],
                "foldseek_score": round(summarize_foldseek_hits(parsed_rows, min_tmscore=min_tmscore), 4),
            }
        )

    if dry_run:
        return {"commands": commands}

    write_scores_tsv(stage_dir / "scores.tsv", rows, ["protein_id", "foldseek_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="06_foldseek_confirm",
            input_hash="structure-manifest",
            parameters={"topk": topk, "min_tmscore": min_tmscore, "database_path": _path_text(database_path)},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"foldseek_scores_tsv": stage_dir / "scores.tsv"}
