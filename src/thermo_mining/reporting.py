from collections import Counter
from pathlib import Path

from .io_utils import write_scores_tsv


REPORT_FIELDNAMES = [
    "protein_id",
    "seed_ids",
    "seed_channels",
    "best_sequence_score",
    "best_structure_score",
    "thermo_score",
    "protrek_score",
    "foldseek_score",
    "origin_bonus",
    "final_score",
    "tier",
]


def build_summary_markdown(run_name: str, tier_counts: dict[str, int], top_candidate_ids: list[str]) -> str:
    lines = [
        f"# Thermo Mining Summary: {run_name}",
        "",
        "## Tier Counts",
        f"- Tier 1: {tier_counts.get('Tier 1', 0)}",
        f"- Tier 2: {tier_counts.get('Tier 2', 0)}",
        f"- Tier 3: {tier_counts.get('Tier 3', 0)}",
        "",
        "## Top Candidates",
    ]
    for protein_id in top_candidate_ids:
        lines.append(f"- {protein_id}")
    lines.append("")
    return "\n".join(lines)


def write_report_outputs(stage_dir: str | Path, run_name: str, combined_rows: list[dict[str, object]]) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    top_100_tsv = stage_dir / "top_100.tsv"
    top_1000_tsv = stage_dir / "top_1000.tsv"
    summary_md = stage_dir / "summary.md"

    write_scores_tsv(top_100_tsv, combined_rows[:100], REPORT_FIELDNAMES)
    write_scores_tsv(top_1000_tsv, combined_rows[:1000], REPORT_FIELDNAMES)

    tier_counts = dict(Counter(str(row["tier"]) for row in combined_rows))
    top_candidate_ids = [str(row["protein_id"]) for row in combined_rows[:10]]
    summary_md.write_text(
        build_summary_markdown(run_name=run_name, tier_counts=tier_counts, top_candidate_ids=top_candidate_ids),
        encoding="utf-8",
    )

    return {
        "top_100_tsv": top_100_tsv,
        "top_1000_tsv": top_1000_tsv,
        "summary_md": summary_md,
    }
