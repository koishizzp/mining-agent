import csv
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import sha256_file, write_done_json, write_scores_tsv
from ..models import DoneRecord


def build_easy_linclust_command(
    mmseqs_bin: str,
    input_faa: str | Path,
    output_prefix: str | Path,
    tmp_dir: str | Path,
    min_seq_id: float,
    coverage: float,
    threads: int,
) -> list[str]:
    return [
        mmseqs_bin,
        "easy-linclust",
        str(input_faa),
        str(output_prefix),
        str(tmp_dir),
        "--min-seq-id",
        f"{min_seq_id:.2f}",
        "-c",
        f"{coverage:.2f}",
        "--cov-mode",
        "1",
        "--threads",
        str(threads),
    ]


def parse_cluster_membership(cluster_tsv: str | Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(cluster_tsv).open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for rep, member in reader:
            rows.append({"cluster_rep": rep, "member_id": member})
    return rows


def run_mmseqs_cluster(
    input_faa: str | Path,
    stage_dir: str | Path,
    mmseqs_bin: str,
    min_seq_id: float,
    coverage: float,
    threads: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | list[str]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    output_prefix = stage_dir / "cluster"
    tmp_dir = stage_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_easy_linclust_command(
        mmseqs_bin=mmseqs_bin,
        input_faa=input_faa,
        output_prefix=output_prefix,
        tmp_dir=tmp_dir,
        min_seq_id=min_seq_id,
        coverage=coverage,
        threads=threads,
    )
    if dry_run:
        return cmd

    subprocess.run(cmd, check=True)

    cluster_tsv = stage_dir / "cluster_cluster.tsv"
    rep_faa = stage_dir / "cluster_rep_seq.fasta"
    rows = parse_cluster_membership(cluster_tsv)
    write_scores_tsv(stage_dir / "scores.tsv", rows, ["cluster_rep", "member_id"])

    reps = {row["cluster_rep"] for row in rows}
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="02_cluster",
            input_hash=sha256_file(input_faa),
            parameters={
                "min_seq_id": min_seq_id,
                "coverage": coverage,
                "threads": threads,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(reps),
            reject_count=max(0, len(rows) - len(reps)),
        ),
    )
    return {"cluster_rep_faa": rep_faa, "cluster_membership_tsv": cluster_tsv}
