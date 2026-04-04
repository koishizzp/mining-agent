import csv
import hashlib
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord


def _combined_input_hash(*paths: str | Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()


def _read_hits(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def run_seed_recall_merge_stage(
    cluster_rep_faa: str | Path,
    sequence_hits_tsv: str | Path,
    structure_hits_tsv: str | Path,
    stage_dir: str | Path,
    software_version: str,
) -> dict[str, object]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    target_records = {record.protein_id: record for record in read_fasta(cluster_rep_faa)}
    merged: dict[str, dict[str, object]] = {}

    for row in _read_hits(sequence_hits_tsv):
        entry = merged.setdefault(
            row["target_id"],
            {
                "target_id": row["target_id"],
                "seed_ids": set(),
                "seed_channels": set(),
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        entry["seed_ids"].add(row["seed_id"])
        entry["seed_channels"].add("sequence")
        entry["best_sequence_score"] = max(float(entry["best_sequence_score"]), float(row["sequence_score"]))

    for row in _read_hits(structure_hits_tsv):
        entry = merged.setdefault(
            row["target_id"],
            {
                "target_id": row["target_id"],
                "seed_ids": set(),
                "seed_channels": set(),
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        entry["seed_ids"].add(row["seed_id"])
        entry["seed_channels"].add("structure")
        entry["best_structure_score"] = max(float(entry["best_structure_score"]), float(row["structure_score"]))

    manifest_rows: list[dict[str, object]] = []
    retained_records = []
    for target_id in sorted(merged):
        if target_id not in target_records:
            raise RuntimeError(f"seed recall merge referenced unknown target '{target_id}'")

        channels = set(entry for entry in merged[target_id]["seed_channels"] if isinstance(entry, str))
        if channels == {"sequence", "structure"}:
            channel_label = "both"
        elif channels == {"sequence"}:
            channel_label = "sequence"
        else:
            channel_label = "structure"

        manifest_rows.append(
            {
                "target_id": target_id,
                "seed_ids": ";".join(sorted(str(seed_id) for seed_id in merged[target_id]["seed_ids"])),
                "seed_channels": channel_label,
                "best_sequence_score": round(float(merged[target_id]["best_sequence_score"]), 4),
                "best_structure_score": round(float(merged[target_id]["best_structure_score"]), 4),
            }
        )
        retained_records.append(target_records[target_id])

    seed_manifest_tsv = stage_dir / "seed_manifest.tsv"
    seeded_targets_faa = stage_dir / "seeded_targets.faa"
    write_scores_tsv(
        seed_manifest_tsv,
        manifest_rows,
        ["target_id", "seed_ids", "seed_channels", "best_sequence_score", "best_structure_score"],
    )
    write_fasta(seeded_targets_faa, retained_records)
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="05_seed_recall_merge",
            input_hash=_combined_input_hash(cluster_rep_faa, sequence_hits_tsv, structure_hits_tsv),
            parameters={},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(manifest_rows),
            reject_count=0,
        ),
    )

    return {
        "seed_manifest_tsv": seed_manifest_tsv,
        "seeded_targets_faa": seeded_targets_faa,
        "seed_rows": manifest_rows,
    }
