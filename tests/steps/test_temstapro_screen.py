from pathlib import Path

from thermo_mining.steps.temstapro_screen import (
    build_temstapro_command,
    derive_thermo_score,
    run_temstapro_screen,
    select_thermo_hits,
)


def test_build_temstapro_command_contains_required_arguments(tmp_path):
    cmd = build_temstapro_command(
        conda_bin="/opt/miniconda/bin/conda",
        conda_env_name="temstapro_env_CPU",
        temstapro_bin="temstapro",
        input_faa=tmp_path / "cluster_rep.faa",
        model_dir=tmp_path / "ProtTrans",
        cache_dir=tmp_path / "cache",
        output_tsv=tmp_path / "temstapro.tsv",
    )

    assert cmd[:4] == ["/opt/miniconda/bin/conda", "run", "-n", "temstapro_env_CPU"]
    assert cmd[4:6] == ["temstapro", "-f"]
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


def test_run_temstapro_screen_passes_repo_root_and_env_overlay(tmp_path, monkeypatch):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">p1\nAAAA\n", encoding="utf-8")
    stage_dir = tmp_path / "stage"
    recorded: dict[str, object] = {}

    def fake_run(cmd, check, cwd, env):
        recorded["cmd"] = cmd
        recorded["check"] = check
        recorded["cwd"] = cwd
        recorded["env"] = env
        (stage_dir / "temstapro_raw.tsv").write_text(
            "protein_id\tprediction\traw_50\np1\tthermophilic\t0.8\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.temstapro_screen.subprocess.run", fake_run)

    result = run_temstapro_screen(
        input_faa=input_faa,
        stage_dir=stage_dir,
        conda_bin="/opt/miniconda/bin/conda",
        conda_env_name="temstapro_env_CPU",
        temstapro_bin="/srv/TemStaPro-main/temstapro",
        repo_root=Path("/srv/TemStaPro-main"),
        model_dir=Path("/srv/TemStaPro-main/models"),
        cache_dir=Path("/srv/TemStaPro-main/cache"),
        hf_home=Path("/srv/.cache/huggingface"),
        transformers_offline=True,
        top_fraction=1.0,
        min_score=0.5,
        software_version="test",
    )

    assert result["thermo_hits_faa"] == stage_dir / "thermo_hits.faa"
    assert recorded["check"] is True
    assert recorded["cwd"] == Path("/srv/TemStaPro-main")
    assert recorded["env"]["HF_HOME"] == "/srv/.cache/huggingface"
    assert recorded["env"]["TRANSFORMERS_OFFLINE"] == "1"
