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
