from thermo_mining.reporting import build_summary_markdown
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


def test_build_summary_markdown_reports_counts():
    markdown_text = build_summary_markdown(
        run_name="run_001",
        tier_counts={"Tier 1": 3, "Tier 2": 5, "Tier 3": 10},
        top_candidate_ids=["p1", "p2", "p3"],
    )

    assert "run_001" in markdown_text
    assert "Tier 1" in markdown_text
    assert "p1" in markdown_text
