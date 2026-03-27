from pathlib import Path

from thermo_mining.cli import main
from thermo_mining.pipeline import run_pipeline, should_skip_stage


def test_should_skip_stage_respects_done_json(tmp_path):
    done_path = tmp_path / "DONE.json"
    done_path.write_text(
        '{"stage_name":"01_prefilter","input_hash":"abc","parameters":{},"software_version":"0.1.0","runtime_seconds":1.0,"retain_count":1,"reject_count":0}',
        encoding="utf-8",
    )

    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=True) is True
    assert should_skip_stage(done_path=done_path, expected_input_hash="xyz", resume=True) is False
    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=False) is False


def test_run_pipeline_executes_stages_and_writes_reports(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        f"""
project_name: hot_spring_phase1
results_root: {tmp_path.as_posix()}/results
prefilter:
  min_length: 80
  max_length: 1200
  max_single_residue_fraction: 0.7
cluster:
  mmseqs_bin: mmseqs
  min_seq_id: 0.9
  coverage: 0.8
  threads: 64
thermo:
  temstapro_bin: temstapro
  model_dir: /models/temstapro/ProtTrans
  cache_dir: /tmp/temstapro_cache
  top_fraction: 0.1
  min_score: 0.5
protrek:
  python_bin: /opt/protrek/bin/python
  repo_root: /srv/ProTrek
  weights_dir: /srv/ProTrek/weights/ProTrek_650M
  query_texts:
    - thermostable enzyme
  batch_size: 8
  top_k: 50
foldseek:
  base_url: http://127.0.0.1:8100
  database: afdb50
  topk: 5
  min_tmscore: 0.6
""".strip(),
        encoding="utf-8",
    )
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">p1\nMSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTATPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF\n", encoding="utf-8")
    calls: list[str] = []

    def fake_prefilter(**kwargs):
        calls.append("prefilter")
        output = Path(kwargs["stage_dir"]) / "filtered.faa"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        return {"filtered_faa": output}

    def fake_cluster(**kwargs):
        calls.append("cluster")
        output = Path(kwargs["stage_dir"]) / "cluster_rep_seq.fasta"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        return {"cluster_rep_faa": output, "cluster_membership_tsv": Path(kwargs["stage_dir"]) / "cluster_cluster.tsv"}

    def fake_temstapro(**kwargs):
        calls.append("thermo")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "scores.tsv").write_text("protein_id\tprediction\tthermo_score\np1\tthermophilic\t0.9\n", encoding="utf-8")
        hits = output_dir / "thermo_hits.faa"
        hits.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        return {"thermo_hits_faa": hits, "thermo_scores_tsv": output_dir / "scores.tsv"}

    def fake_protrek(**kwargs):
        calls.append("protrek")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        scores = output_dir / "scores.tsv"
        scores.write_text("protein_id\tprotrek_score\np1\t0.8\n", encoding="utf-8")
        return {"protrek_scores_tsv": scores}

    def fake_foldseek(**kwargs):
        calls.append("foldseek")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        scores = output_dir / "scores.tsv"
        scores.write_text("protein_id\tfoldseek_score\np1\t0.7\n", encoding="utf-8")
        return {"foldseek_scores_tsv": scores}

    monkeypatch.setattr("thermo_mining.pipeline.run_prefilter", fake_prefilter)
    monkeypatch.setattr("thermo_mining.pipeline.run_mmseqs_cluster", fake_cluster)
    monkeypatch.setattr("thermo_mining.pipeline.run_temstapro_screen", fake_temstapro)
    monkeypatch.setattr("thermo_mining.pipeline.run_protrek_stage", fake_protrek)
    monkeypatch.setattr("thermo_mining.pipeline.run_foldseek_stage", fake_foldseek)

    result = run_pipeline(config_path=config_path, run_name="demo_run", input_faa=input_faa, resume=False)

    assert calls == ["prefilter", "cluster", "thermo", "protrek", "foldseek"]
    assert result["summary_md"].exists()
    assert result["top_100_tsv"].exists()


def test_cli_main_dispatches_run_pipeline(tmp_path, monkeypatch):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text("project_name: demo\nresults_root: results\n", encoding="utf-8")
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">p1\nAAAA\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run_pipeline(**kwargs):
        captured.update(kwargs)
        return {"summary_md": tmp_path / "summary.md"}

    monkeypatch.setattr("thermo_mining.cli.run_pipeline", fake_run_pipeline)

    main(
        [
            "run",
            "--config",
            str(config_path),
            "--run-name",
            "demo_run",
            "--input-faa",
            str(input_faa),
            "--resume",
        ]
    )

    assert captured["config_path"] == config_path
    assert captured["run_name"] == "demo_run"
    assert captured["input_faa"] == input_faa
    assert captured["resume"] is True
