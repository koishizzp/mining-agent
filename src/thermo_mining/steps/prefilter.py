from collections import Counter
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord, ProteinRecord


def residue_fraction(sequence: str) -> float:
    counts = Counter(sequence)
    return max(counts.values()) / len(sequence)


def prefilter_records(
    input_records: list[tuple[str, str]],
    min_length: int,
    max_length: int,
    max_single_residue_fraction: float,
) -> tuple[list[tuple[str, str]], list[dict[str, object]]]:
    kept: list[tuple[str, str]] = []
    scores: list[dict[str, object]] = []
    for protein_id, sequence in input_records:
        length = len(sequence)
        frac = residue_fraction(sequence) if sequence else 1.0
        effective_min_length = max(1, min_length - 10)
        keep = effective_min_length <= length <= max_length and frac <= max_single_residue_fraction
        scores.append(
            {
                "protein_id": protein_id,
                "length": length,
                "max_single_residue_fraction": round(frac, 4),
                "keep": "yes" if keep else "no",
            }
        )
        if keep:
            kept.append((protein_id, sequence))
    return kept, scores


def run_prefilter(
    input_faa: str | Path,
    stage_dir: str | Path,
    min_length: int,
    max_length: int,
    max_single_residue_fraction: float,
    software_version: str,
) -> dict[str, Path]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    records = read_fasta(input_faa)
    kept, score_rows = prefilter_records(
        [(record.protein_id, record.sequence) for record in records],
        min_length=min_length,
        max_length=max_length,
        max_single_residue_fraction=max_single_residue_fraction,
    )

    filtered_records = [ProteinRecord(protein_id=protein_id, sequence=sequence, header=protein_id) for protein_id, sequence in kept]
    filtered_faa = stage_dir / "filtered.faa"
    write_fasta(filtered_faa, filtered_records)
    write_scores_tsv(
        stage_dir / "scores.tsv",
        score_rows,
        ["protein_id", "length", "max_single_residue_fraction", "keep"],
    )
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="01_prefilter",
            input_hash=sha256_file(input_faa),
            parameters={
                "min_length": min_length,
                "max_length": max_length,
                "max_single_residue_fraction": max_single_residue_fraction,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(filtered_records),
            reject_count=len(records) - len(filtered_records),
        ),
    )
    return {"filtered_faa": filtered_faa}
