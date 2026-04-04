def assign_tier(final_score: float) -> str:
    if final_score >= 0.75:
        return "Tier 1"
    if final_score >= 0.55:
        return "Tier 2"
    return "Tier 3"


def combine_stage_scores(
    thermo_rows: list[dict[str, object]],
    protrek_rows: list[dict[str, object]],
    foldseek_rows: list[dict[str, object]],
    hot_spring_ids: set[str],
    seed_rows: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    thermo_map = {row["protein_id"]: float(row["thermo_score"]) for row in thermo_rows}
    protrek_map = {row["protein_id"]: float(row["protrek_score"]) for row in protrek_rows}
    foldseek_map = {row["protein_id"]: float(row["foldseek_score"]) for row in foldseek_rows}
    seed_map = {
        str(row["target_id"]): {
            "seed_ids": str(row["seed_ids"]),
            "seed_channels": str(row["seed_channels"]),
            "best_sequence_score": float(row["best_sequence_score"]),
            "best_structure_score": float(row["best_structure_score"]),
        }
        for row in (seed_rows or [])
    }
    all_ids = sorted(set(thermo_map) | set(protrek_map) | set(foldseek_map))

    combined: list[dict[str, object]] = []
    for protein_id in all_ids:
        seed_support = seed_map.get(
            protein_id,
            {
                "seed_ids": "",
                "seed_channels": "",
                "best_sequence_score": 0.0,
                "best_structure_score": 0.0,
            },
        )
        thermo_score = thermo_map.get(protein_id, 0.0)
        protrek_score = protrek_map.get(protein_id, 0.0)
        foldseek_score = foldseek_map.get(protein_id, 0.0)
        origin_bonus = 0.05 if protein_id in hot_spring_ids else 0.0
        final_score = round(
            thermo_score * 0.35 + protrek_score * 0.35 + foldseek_score * 0.25 + origin_bonus,
            4,
        )
        combined.append(
            {
                "protein_id": protein_id,
                "seed_ids": seed_support["seed_ids"],
                "seed_channels": seed_support["seed_channels"],
                "best_sequence_score": seed_support["best_sequence_score"],
                "best_structure_score": seed_support["best_structure_score"],
                "thermo_score": thermo_score,
                "protrek_score": protrek_score,
                "foldseek_score": foldseek_score,
                "origin_bonus": origin_bonus,
                "final_score": final_score,
                "tier": assign_tier(final_score),
            }
        )
    return sorted(combined, key=lambda row: row["final_score"], reverse=True)
