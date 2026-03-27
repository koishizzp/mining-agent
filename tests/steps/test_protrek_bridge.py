from thermo_mining.steps.protrek_bridge import (
    build_protrek_index_command,
    build_protrek_query_command,
    collapse_query_scores,
)


def test_build_protrek_index_command_uses_repo_and_weights(tmp_path):
    cmd = build_protrek_index_command(
        python_bin="/opt/protrek/bin/python",
        script_path=tmp_path / "scripts" / "protrek_build_index.py",
        repo_root="/srv/ProTrek",
        weights_dir="/srv/ProTrek/weights/ProTrek_650M",
        input_faa=tmp_path / "thermo_hits.faa",
        output_dir=tmp_path / "index",
        batch_size=8,
    )

    assert cmd[0] == "/opt/protrek/bin/python"
    assert "--repo-root" in cmd
    assert "--weights-dir" in cmd


def test_build_protrek_query_command_repeats_query_text_flags(tmp_path):
    cmd = build_protrek_query_command(
        python_bin="/opt/protrek/bin/python",
        script_path=tmp_path / "scripts" / "protrek_query.py",
        repo_root="/srv/ProTrek",
        weights_dir="/srv/ProTrek/weights/ProTrek_650M",
        index_dir=tmp_path / "index",
        query_texts=["thermostable enzyme", "heat-stable protein"],
        output_tsv=tmp_path / "scores.tsv",
        top_k=50,
    )

    assert cmd.count("--query-text") == 2
    assert "--top-k" in cmd


def test_collapse_query_scores_keeps_best_hit_per_protein():
    rows = [
        {"protein_id": "p1", "query_text": "thermostable enzyme", "protrek_score": 0.72},
        {"protein_id": "p1", "query_text": "heat-stable protein", "protrek_score": 0.81},
        {"protein_id": "p2", "query_text": "thermostable enzyme", "protrek_score": 0.65},
    ]

    collapsed = collapse_query_scores(rows)

    assert collapsed == [
        {"protein_id": "p1", "protrek_score": 0.81},
        {"protein_id": "p2", "protrek_score": 0.65},
    ]
