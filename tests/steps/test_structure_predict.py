import json
from pathlib import Path

import pytest

from thermo_mining.steps.structure_predict import build_colabfold_command, run_structure_predict_stage


def test_build_colabfold_command_uses_expected_runtime_flags(tmp_path):
    cmd = build_colabfold_command(
        colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
        data_dir=Path("/srv/.cache/colabfold"),
        query_faa=tmp_path / "p1.faa",
        output_dir=tmp_path / "raw" / "p1",
        msa_mode="single_sequence",
        num_models=1,
        num_recycle=2,
    )

    assert cmd == [
        "/opt/colabfold/bin/colabfold_batch",
        "--data",
        "/srv/.cache/colabfold",
        "--msa-mode",
        "single_sequence",
        "--num-models",
        "1",
        "--num-recycle",
        "2",
        str(tmp_path / "p1.faa"),
        str(tmp_path / "raw" / "p1"),
    ]


def test_run_structure_predict_stage_writes_normalized_pdbs_and_manifest(tmp_path, monkeypatch):
    input_faa = tmp_path / "thermo_hits.faa"
    input_faa.write_text(">p1 desc\nMSTNPKPQRK\n>p2\nAAAAAA\n", encoding="utf-8")
    recorded: list[list[str]] = []

    def fake_run(cmd, check):
        recorded.append(cmd)
        query_faa = Path(cmd[-2])
        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{query_faa.stem}_unrelaxed_rank_001_model_1.pdb").write_text(
            f"MODEL {query_faa.stem}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.structure_predict.subprocess.run", fake_run)

    result = run_structure_predict_stage(
        input_faa=input_faa,
        stage_dir=tmp_path / "05_structure",
        colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
        colabfold_data_dir=Path("/srv/.cache/colabfold"),
        msa_mode="single_sequence",
        num_models=1,
        num_recycle=1,
        software_version="test",
    )

    manifest = result["structure_manifest"]
    manifest_path = result["structure_manifest_json"]
    assert [entry["protein_id"] for entry in manifest] == ["p1", "p2"]
    assert manifest_path == tmp_path / "05_structure" / "structure_manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert (tmp_path / "05_structure" / "structures" / "p1.pdb").exists()
    assert (tmp_path / "05_structure" / "structures" / "p2.pdb").exists()
    assert (tmp_path / "05_structure" / "queries" / "p1.faa").read_text(encoding="utf-8") == ">p1 desc\nMSTNPKPQRK\n"
    assert (tmp_path / "05_structure" / "queries" / "p2.faa").read_text(encoding="utf-8") == ">p2\nAAAAAA\n"
    done = json.loads((tmp_path / "05_structure" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "05_structure_predict"
    assert done["retain_count"] == 2
    assert done["reject_count"] == 0
    assert len(recorded) == 2


def test_run_structure_predict_stage_fails_when_pdb_choice_is_ambiguous(tmp_path, monkeypatch):
    input_faa = tmp_path / "thermo_hits.faa"
    input_faa.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")

    def fake_run(cmd, check):
        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "candidate_a.pdb").write_text("MODEL A\n", encoding="utf-8")
        (output_dir / "candidate_b.pdb").write_text("MODEL B\n", encoding="utf-8")

    monkeypatch.setattr("thermo_mining.steps.structure_predict.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="p1"):
        run_structure_predict_stage(
            input_faa=input_faa,
            stage_dir=tmp_path / "05_structure",
            colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
            colabfold_data_dir=Path("/srv/.cache/colabfold"),
            msa_mode="single_sequence",
            num_models=1,
            num_recycle=1,
            software_version="test",
        )
