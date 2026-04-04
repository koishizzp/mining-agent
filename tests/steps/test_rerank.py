from thermo_mining.reporting import build_summary_markdown, write_report_outputs
from thermo_mining.steps.rerank import assign_tier, combine_stage_scores


def test_assign_tier_uses_expected_thresholds():
    assert assign_tier(0.82) == "Tier 1"
    assert assign_tier(0.60) == "Tier 2"
    assert assign_tier(0.20) == "Tier 3"


def test_combine_stage_scores_merges_multiple_sources():
    combined = combine_stage_scores(
        thermo_rows=[{"protein_id": "p1", "thermo_score": 0.9}, {"protein_id": "p2", "thermo_score": 0.4}],
        protrek_rows=[{"protein_id": "p1", "protrek_score": 0.8}, {"protein_id": "p2", "protrek_score": 0.7}],
        foldseek_rows=[{"protein_id": "p1", "foldseek_score": 0.6}],
        hot_spring_ids={"p1"},
    )

    assert combined[0]["protein_id"] == "p1"
    assert combined[0]["tier"] == "Tier 1"
    assert combined[1]["tier"] in {"Tier 2", "Tier 3"}


def test_combine_stage_scores_merges_seed_provenance_without_changing_formula():
    combined = combine_stage_scores(
        thermo_rows=[{"protein_id": "p1", "thermo_score": 0.9}],
        protrek_rows=[{"protein_id": "p1", "protrek_score": 0.8}],
        foldseek_rows=[{"protein_id": "p1", "foldseek_score": 0.6}],
        hot_spring_ids={"p1"},
        seed_rows=[
            {
                "target_id": "p1",
                "seed_ids": "cas1;cas2",
                "seed_channels": "both",
                "best_sequence_score": 0.91,
                "best_structure_score": 0.84,
            }
        ],
    )

    assert combined[0]["seed_ids"] == "cas1;cas2"
    assert combined[0]["seed_channels"] == "both"
    assert combined[0]["best_sequence_score"] == 0.91
    assert combined[0]["best_structure_score"] == 0.84
    assert combined[0]["final_score"] == 0.795


def test_build_summary_markdown_reports_counts():
    markdown_text = build_summary_markdown(
        run_name="run_001",
        tier_counts={"Tier 1": 3, "Tier 2": 5, "Tier 3": 10},
        top_candidate_ids=["p1", "p2", "p3"],
    )

    assert "run_001" in markdown_text
    assert "Tier 1" in markdown_text
    assert "p1" in markdown_text


def test_write_report_outputs_writes_ranked_artifacts(tmp_path):
    combined_rows = [
        {
            "protein_id": "p1",
            "thermo_score": 0.9,
            "protrek_score": 0.8,
            "foldseek_score": 0.6,
            "origin_bonus": 0.05,
            "final_score": 0.82,
            "tier": "Tier 1",
        },
        {
            "protein_id": "p2",
            "thermo_score": 0.4,
            "protrek_score": 0.7,
            "foldseek_score": 0.0,
            "origin_bonus": 0.0,
            "final_score": 0.39,
            "tier": "Tier 3",
        },
    ]

    outputs = write_report_outputs(tmp_path, "run_001", combined_rows)

    assert outputs["top_100_tsv"].exists()
    assert outputs["top_1000_tsv"].exists()
    assert outputs["summary_md"].exists()
    assert "p1" in outputs["summary_md"].read_text(encoding="utf-8")


def test_write_report_outputs_writes_seed_columns_and_empty_headers(tmp_path):
    outputs = write_report_outputs(tmp_path, "run_001", [])

    top_100_text = outputs["top_100_tsv"].read_text(encoding="utf-8")
    assert top_100_text.startswith(
        "protein_id\tseed_ids\tseed_channels\tbest_sequence_score\tbest_structure_score\tthermo_score"
    )
    assert "Tier 1: 0" in outputs["summary_md"].read_text(encoding="utf-8")
