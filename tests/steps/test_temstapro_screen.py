from thermo_mining.steps.temstapro_screen import build_temstapro_command, derive_thermo_score, select_thermo_hits


def test_build_temstapro_command_contains_required_arguments(tmp_path):
    cmd = build_temstapro_command(
        temstapro_bin="temstapro",
        input_faa=tmp_path / "cluster_rep.faa",
        model_dir=tmp_path / "ProtTrans",
        cache_dir=tmp_path / "cache",
        output_tsv=tmp_path / "temstapro.tsv",
    )

    assert cmd[:2] == ["temstapro", "-f"]
    assert "--mean-output" in cmd


def test_derive_thermo_score_prefers_highest_numeric_signal():
    row = {"protein_id": "p1", "raw_40": "0.31", "raw_50": "0.79", "prediction": "thermophilic"}
    assert derive_thermo_score(row) == 0.79


def test_select_thermo_hits_respects_fraction_and_min_score():
    rows = [
        {"protein_id": "p1", "thermo_score": 0.95},
        {"protein_id": "p2", "thermo_score": 0.84},
        {"protein_id": "p3", "thermo_score": 0.30},
    ]

    kept = select_thermo_hits(rows, top_fraction=0.34, min_score=0.8)

    assert [row["protein_id"] for row in kept] == ["p1", "p2"]
