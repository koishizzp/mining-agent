import csv
import json
from pathlib import Path

import pytest

from thermo_mining.steps.seed_structure_recall import (
    build_foldseek_createdb_command,
    run_seed_structure_recall_stage,
)


def test_build_foldseek_createdb_command_uses_local_binary(tmp_path):
    cmd = build_foldseek_createdb_command(
        foldseek_bin="/opt/foldseek/bin/foldseek",
        structures_dir=tmp_path / "target_structures",
        database_prefix=tmp_path / "target_db" / "db",
    )

    assert cmd == [
        "/opt/foldseek/bin/foldseek",
        "createdb",
        str(tmp_path / "target_structures"),
        str(tmp_path / "target_db" / "db"),
    ]


def test_run_seed_structure_recall_stage_fails_when_target_cap_is_exceeded(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1\nAAAA\n>target2\nCCCC\n", encoding="utf-8")

    def fail_run(*args, **kwargs):
        pytest.fail("target cap check should fail before any subprocess invocation")

    monkeypatch.setattr("thermo_mining.steps.seed_structure_recall.subprocess.run", fail_run)

    with pytest.raises(RuntimeError, match="seed_structure_max_targets"):
        run_seed_structure_recall_stage(
            seed_faa=seed_faa,
            cluster_rep_faa=cluster_rep_faa,
            stage_dir=tmp_path / "04_seed_structure",
            colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
            colabfold_data_dir=Path("/srv/.cache/colabfold"),
            foldseek_bin="/opt/foldseek/bin/foldseek",
            msa_mode="single_sequence",
            num_models=1,
            num_recycle=1,
            min_tmscore=0.55,
            topk_per_seed=200,
            max_targets=1,
            software_version="test",
        )


def test_run_seed_structure_recall_stage_writes_per_pair_scores(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1\nAAAAAA\n>target2\nGGGGGG\n", encoding="utf-8")

    def fake_run(cmd, check):
        if cmd[1] == "createdb":
            Path(cmd[3]).parent.mkdir(parents=True, exist_ok=True)
            return
        if cmd[1] == "easy-search":
            output_tsv = Path(cmd[4])
            output_tsv.parent.mkdir(parents=True, exist_ok=True)
            output_tsv.write_text(
                "seed_query\ttarget1\t0.81\nseed_query\ttarget2\t0.49\n",
                encoding="utf-8",
            )
            return

        output_dir = Path(cmd[-1])
        output_dir.mkdir(parents=True, exist_ok=True)
        query_faa = Path(cmd[-2])
        (output_dir / f"{query_faa.stem}_unrelaxed_rank_001_model_1.pdb").write_text(
            f"MODEL {query_faa.stem}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.seed_structure_recall.subprocess.run", fake_run)

    result = run_seed_structure_recall_stage(
        seed_faa=seed_faa,
        cluster_rep_faa=cluster_rep_faa,
        stage_dir=tmp_path / "04_seed_structure",
        colabfold_batch_bin="/opt/colabfold/bin/colabfold_batch",
        colabfold_data_dir=Path("/srv/.cache/colabfold"),
        foldseek_bin="/opt/foldseek/bin/foldseek",
        msa_mode="single_sequence",
        num_models=1,
        num_recycle=1,
        min_tmscore=0.55,
        topk_per_seed=200,
        max_targets=50,
        software_version="test",
    )

    assert result["structure_hits_tsv"] == tmp_path / "04_seed_structure" / "structure_hits.tsv"
    with result["structure_hits_tsv"].open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert rows == [{"target_id": "target1", "seed_id": "cas1", "structure_score": "0.81"}]
    assert (tmp_path / "04_seed_structure" / "seed_structures" / "cas1.pdb").exists()
    assert (tmp_path / "04_seed_structure" / "target_structures" / "target1.pdb").exists()
    done = json.loads((tmp_path / "04_seed_structure" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "04_seed_structure_recall"
    assert done["retain_count"] == 1
