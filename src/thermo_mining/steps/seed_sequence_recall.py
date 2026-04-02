import csv
import hashlib
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def _path_text(value: str | Path) -> str:
    if isinstance(value, Path):
        return str(value) if value.drive else value.as_posix()
    return str(value)


def _combined_input_hash(*paths: str | Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()


def build_seed_sequence_search_command(
    mmseqs_bin: str,
    seed_faa: str | Path,
    target_faa: str | Path,
    output_tsv: str | Path,
    tmp_dir: str | Path,
    min_seq_id: float,
    coverage: float,
    topk_per_seed: int,
    threads: int,
) -> list[str]:
    return [
        mmseqs_bin,
        "easy-search",
        _path_text(seed_faa),
        _path_text(target_faa),
        _path_text(output_tsv),
        _path_text(tmp_dir),
        "--format-output",
        "query,target,pident",
        "--min-seq-id",
        f"{min_seq_id:.2f}",
        "-c",
        f"{coverage:.2f}",
        "--cov-mode",
        "1",
        "--max-seqs",
        str(topk_per_seed),
        "--threads",
        str(threads),
    ]


def run_seed_sequence_recall_stage(
    seed_faa: str | Path,
    target_faa: str | Path,
    stage_dir: str | Path,
    mmseqs_bin: str,
    min_seq_id: float,
    coverage: float,
    topk_per_seed: int,
    threads: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[str]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_tsv = stage_dir / "raw.tsv"
    tmp_dir = stage_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_seed_sequence_search_command(
        mmseqs_bin=mmseqs_bin,
        seed_faa=seed_faa,
        target_faa=target_faa,
        output_tsv=raw_tsv,
        tmp_dir=tmp_dir,
        min_seq_id=min_seq_id,
        coverage=coverage,
        topk_per_seed=topk_per_seed,
        threads=threads,
    )
    if dry_run:
        return {"command": cmd}

    subprocess.run(cmd, check=True)

    rows: list[dict[str, object]] = []
    with raw_tsv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for row in reader:
            if not row:
                continue
            query, target, pident = row[0], row[1], row[2]
            rows.append(
                {
                    "target_id": target,
                    "seed_id": query,
                    "sequence_score": round(float(pident) / 100.0, 4),
                }
            )

    sequence_hits_tsv = stage_dir / "sequence_hits.tsv"
    write_scores_tsv(sequence_hits_tsv, rows, ["target_id", "seed_id", "sequence_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="03_seed_sequence_recall",
            input_hash=_combined_input_hash(seed_faa, target_faa),
            parameters={
                "min_seq_id": min_seq_id,
                "coverage": coverage,
                "topk_per_seed": topk_per_seed,
                "threads": threads,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=0,
        ),
    )
    return {"sequence_hits_tsv": sequence_hits_tsv, "raw_tsv": raw_tsv}
