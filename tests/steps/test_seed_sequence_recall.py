import csv
import json
from pathlib import Path

from thermo_mining.steps.seed_sequence_recall import (
    build_seed_sequence_search_command,
    run_seed_sequence_recall_stage,
)


def test_build_seed_sequence_search_command_uses_mmseqs_easy_search(tmp_path):
    cmd = build_seed_sequence_search_command(
        mmseqs_bin="mmseqs",
        seed_faa=tmp_path / "seeds.faa",
        target_faa=tmp_path / "targets.faa",
        output_tsv=tmp_path / "raw.tsv",
        tmp_dir=tmp_path / "tmp",
        min_seq_id=0.3,
        coverage=0.8,
        topk_per_seed=200,
        threads=8,
    )

    assert cmd[:2] == ["mmseqs", "easy-search"]
    assert "--format-output" in cmd
    assert "query,target,pident" in cmd


def test_run_seed_sequence_recall_stage_writes_hits_and_done(tmp_path, monkeypatch):
    seed_faa = tmp_path / "seeds.faa"
    target_faa = tmp_path / "targets.faa"
    seed_faa.write_text(">seed1\nAAAA\n>seed2\nBBBB\n", encoding="utf-8")
    target_faa.write_text(">t1\nCCCC\n", encoding="utf-8")
    stage_dir = tmp_path / "03_seed_sequence"

    def fake_run(cmd, check):
        output_tsv = Path(cmd[4])
        output_tsv.parent.mkdir(parents=True, exist_ok=True)
        output_tsv.write_text(
            "seed1\ttargetA\t90.0\nseed1\ttargetB\t75\nseed2\ttargetA\t88.88\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.seed_sequence_recall.subprocess.run", fake_run)

    result = run_seed_sequence_recall_stage(
        seed_faa=seed_faa,
        target_faa=target_faa,
        stage_dir=stage_dir,
        mmseqs_bin="mmseqs",
        min_seq_id=0.3,
        coverage=0.8,
        topk_per_seed=200,
        threads=8,
        software_version="test",
    )

    hits_tsv = result["sequence_hits_tsv"]
    with hits_tsv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))

    assert len(rows) == 3
    scores = {(row["target_id"], row["seed_id"]): float(row["sequence_score"]) for row in rows}
    assert scores == {
        ("targetA", "seed1"): 0.9,
        ("targetB", "seed1"): 0.75,
        ("targetA", "seed2"): 0.8888,
    }

    done = json.loads((stage_dir / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "03_seed_sequence_recall"
