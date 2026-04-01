import csv
import math
import os
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord, ProteinRecord


def _path_text(value: str | Path) -> str:
    return value.as_posix() if isinstance(value, Path) else str(value)


def build_temstapro_command(
    temstapro_bin: str,
    input_faa: str | Path,
    model_dir: str | Path,
    cache_dir: str | Path,
    output_tsv: str | Path,
    conda_bin: str | None = None,
    conda_env_name: str | None = None,
) -> list[str]:
    cmd: list[str] = []
    if conda_bin and conda_env_name:
        cmd.extend([conda_bin, "run", "-n", conda_env_name])
    cmd.extend(
        [
            temstapro_bin,
            "-f",
            _path_text(input_faa),
            "-d",
            _path_text(model_dir),
            "-e",
            _path_text(cache_dir),
            "--mean-output",
            _path_text(output_tsv),
        ]
    )
    return cmd


def derive_thermo_score(row: dict[str, str]) -> float:
    numeric_values: list[float] = []
    for key, value in row.items():
        if key in {"protein_id", "prediction"}:
            continue
        try:
            numeric_values.append(float(value))
        except ValueError:
            continue
    return max(numeric_values) if numeric_values else 0.0


def select_thermo_hits(rows: list[dict[str, object]], top_fraction: float, min_score: float) -> list[dict[str, object]]:
    ranked = sorted(rows, key=lambda row: float(row["thermo_score"]), reverse=True)
    keep_count = max(1, math.ceil(len(ranked) * top_fraction))
    kept = ranked[:keep_count]
    for row in ranked[keep_count:]:
        if float(row["thermo_score"]) >= min_score:
            kept.append(row)
    return kept


def run_temstapro_screen(
    input_faa: str | Path,
    stage_dir: str | Path,
    temstapro_bin: str,
    model_dir: str | Path,
    cache_dir: str | Path,
    top_fraction: float,
    min_score: float,
    software_version: str,
    conda_bin: str | None = None,
    conda_env_name: str | None = None,
    repo_root: str | Path | None = None,
    hf_home: str | Path | None = None,
    transformers_offline: bool = False,
    dry_run: bool = False,
) -> dict[str, Path] | list[str]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_output = stage_dir / "temstapro_raw.tsv"
    cmd = build_temstapro_command(
        temstapro_bin=temstapro_bin,
        input_faa=input_faa,
        model_dir=model_dir,
        cache_dir=cache_dir,
        output_tsv=raw_output,
        conda_bin=conda_bin,
        conda_env_name=conda_env_name,
    )
    if dry_run:
        return cmd

    env = os.environ.copy()
    if hf_home is not None:
        env["HF_HOME"] = _path_text(hf_home)
    if transformers_offline:
        env["TRANSFORMERS_OFFLINE"] = "1"

    subprocess.run(cmd, check=True, cwd=Path(repo_root) if repo_root is not None else None, env=env)

    parsed_rows: list[dict[str, object]] = []
    with raw_output.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            parsed_rows.append(
                {
                    "protein_id": row["protein_id"],
                    "prediction": row.get("prediction", ""),
                    "thermo_score": round(derive_thermo_score(row), 4),
                }
            )

    kept = select_thermo_hits(parsed_rows, top_fraction=top_fraction, min_score=min_score)
    keep_ids = {row["protein_id"] for row in kept}
    source_records = read_fasta(input_faa)
    kept_records = [ProteinRecord(record.protein_id, record.sequence, record.header) for record in source_records if record.protein_id in keep_ids]
    thermo_hits_faa = stage_dir / "thermo_hits.faa"
    write_fasta(thermo_hits_faa, kept_records)
    write_scores_tsv(stage_dir / "scores.tsv", parsed_rows, ["protein_id", "prediction", "thermo_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="03_thermo_screen",
            input_hash=sha256_file(input_faa),
            parameters={"top_fraction": top_fraction, "min_score": min_score},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(kept_records),
            reject_count=len(source_records) - len(kept_records),
        ),
    )
    return {"thermo_hits_faa": thermo_hits_faa, "thermo_scores_tsv": stage_dir / "scores.tsv"}
