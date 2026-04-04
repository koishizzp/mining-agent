from pathlib import Path

from thermo_mining.cli import main
from thermo_mining.control_plane.stage_graph import build_stage_order
from thermo_mining.pipeline import run_pipeline, should_skip_stage
from thermo_mining.stage_layout import build_stage_dirs


def test_should_skip_stage_respects_done_json(tmp_path):
    done_path = tmp_path / "DONE.json"
    done_path.write_text(
        '{"stage_name":"01_prefilter","input_hash":"abc","parameters":{},"software_version":"0.1.0","runtime_seconds":1.0,"retain_count":1,"reject_count":0}',
        encoding="utf-8",
    )

    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=True) is True
    assert should_skip_stage(done_path=done_path, expected_input_hash="xyz", resume=True) is False
    assert should_skip_stage(done_path=done_path, expected_input_hash="abc", resume=False) is False


def test_run_pipeline_uses_platform_settings_and_executes_structure_stage(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        f"""
runtime:
  runs_root: {tmp_path.as_posix()}/runs
tools:
  mmseqs_bin: /opt/mmseqs/bin/mmseqs
  conda_bin: /opt/miniconda/bin/conda
  temstapro_bin: /opt/temstapro/bin/temstapro
  temstapro_conda_env_name: temstapro_env_CPU
  temstapro_repo_root: /srv/TemStaPro-main
  temstapro_model_dir: /srv/TemStaPro-main/models
  temstapro_cache_dir: /srv/TemStaPro-main/cache
  temstapro_hf_home: /srv/.cache/huggingface
  temstapro_transformers_offline: true
  protrek_python_bin: /opt/protrek/bin/python
  protrek_repo_root: /srv/ProTrek
  protrek_weights_dir: /srv/ProTrek/ProTrek_650M.pt
  colabfold_batch_bin: /opt/colabfold/bin/colabfold_batch
  colabfold_data_dir: /srv/.cache/colabfold
  foldseek_bin: /opt/foldseek/bin/foldseek
  foldseek_database_path: /srv/foldseek/db/afdb50
defaults:
  prefilter_min_length: 80
  prefilter_max_length: 1200
  prefilter_max_single_residue_fraction: 0.7
  cluster_min_seq_id: 0.9
  cluster_coverage: 0.8
  cluster_threads: 64
  thermo_top_fraction: 0.1
  thermo_min_score: 0.5
  protrek_query_texts:
    - thermostable enzyme
  protrek_batch_size: 8
  protrek_top_k: 50
  colabfold_msa_mode: single_sequence
  colabfold_num_models: 1
  colabfold_num_recycle: 1
  foldseek_topk: 5
  foldseek_min_tmscore: 0.6
""".strip(),
        encoding="utf-8",
    )
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
    calls: list[str] = []
    captured: dict[str, dict[str, object]] = {}

    def fake_prefilter(**kwargs):
        calls.append("prefilter")
        output = Path(kwargs["stage_dir"]) / "filtered.faa"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        return {"filtered_faa": output}

    def fake_cluster(**kwargs):
        calls.append("cluster")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "cluster_rep_seq.fasta"
        output.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        membership = output_dir / "cluster_cluster.tsv"
        membership.write_text("p1\tp1\n", encoding="utf-8")
        return {"cluster_rep_faa": output, "cluster_membership_tsv": membership}

    def fake_temstapro(**kwargs):
        calls.append("thermo")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        hits = output_dir / "thermo_hits.faa"
        hits.write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        scores = output_dir / "scores.tsv"
        scores.write_text("protein_id\tprediction\tthermo_score\np1\tthermophilic\t0.9\n", encoding="utf-8")
        return {"thermo_hits_faa": hits, "thermo_scores_tsv": scores}

    def fake_protrek(**kwargs):
        calls.append("protrek")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        scores = output_dir / "scores.tsv"
        scores.write_text("protein_id\tprotrek_score\np1\t0.8\n", encoding="utf-8")
        return {"protrek_scores_tsv": scores}

    monkeypatch.setattr("thermo_mining.pipeline.run_prefilter", fake_prefilter)
    monkeypatch.setattr("thermo_mining.pipeline.run_mmseqs_cluster", fake_cluster)
    monkeypatch.setattr("thermo_mining.pipeline.run_temstapro_screen", fake_temstapro)
    monkeypatch.setattr("thermo_mining.pipeline.run_protrek_stage", fake_protrek)

    def fake_structure(**kwargs):
        captured["structure"] = kwargs
        calls.append("structure")
        return {
            "structure_manifest": [{"protein_id": "p1", "pdb_path": str(tmp_path / "05_structure" / "structures" / "p1.pdb")}],
            "structure_manifest_json": tmp_path / "05_structure" / "structure_manifest.json",
        }

    def fake_foldseek(**kwargs):
        captured["foldseek"] = kwargs
        calls.append("foldseek")
        output_dir = Path(kwargs["stage_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        scores = output_dir / "scores.tsv"
        scores.write_text("protein_id\tfoldseek_score\np1\t0.7\n", encoding="utf-8")
        return {"foldseek_scores_tsv": scores}

    monkeypatch.setattr("thermo_mining.pipeline.run_structure_predict_stage", fake_structure, raising=False)
    monkeypatch.setattr("thermo_mining.pipeline.run_foldseek_stage", fake_foldseek)

    result = run_pipeline(config_path=config_path, run_name="demo_run", input_faa=input_faa, resume=False)

    assert calls == ["prefilter", "cluster", "thermo", "protrek", "structure", "foldseek"]
    assert captured["structure"]["colabfold_batch_bin"] == "/opt/colabfold/bin/colabfold_batch"
    assert captured["foldseek"]["database_path"] == Path("/srv/foldseek/db/afdb50")
    assert result["summary_md"].exists()


def test_cli_main_dispatches_run_pipeline_with_platform_config(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("runtime:\n  runs_root: runs\n", encoding="utf-8")
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


def test_run_seeded_pipeline_executes_seed_recall_before_thermo_stages(tmp_path, monkeypatch):
    from thermo_mining.pipeline import run_seeded_pipeline

    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        f"""
runtime:
  runs_root: {tmp_path.as_posix()}/runs
defaults:
  seed_sequence_min_seq_id: 0.30
  seed_sequence_coverage: 0.80
  seed_sequence_topk_per_seed: 200
  seed_structure_min_tmscore: 0.55
  seed_structure_topk_per_seed: 200
  seed_structure_max_targets: 500
  prefilter_min_length: 80
  prefilter_max_length: 1200
  prefilter_max_single_residue_fraction: 0.7
  cluster_min_seq_id: 0.9
  cluster_coverage: 0.8
  cluster_threads: 64
  thermo_top_fraction: 0.1
  thermo_min_score: 0.5
  protrek_query_texts:
    - thermostable enzyme
  protrek_batch_size: 8
  protrek_top_k: 50
  colabfold_msa_mode: single_sequence
  colabfold_num_models: 1
  colabfold_num_recycle: 1
  foldseek_topk: 5
  foldseek_min_tmscore: 0.6
tools:
  mmseqs_bin: /opt/mmseqs/bin/mmseqs
  conda_bin: /opt/miniconda/bin/conda
  temstapro_bin: /opt/temstapro/bin/temstapro
  temstapro_conda_env_name: temstapro_env_CPU
  temstapro_repo_root: /srv/TemStaPro-main
  temstapro_model_dir: /srv/TemStaPro-main/models
  temstapro_cache_dir: /srv/TemStaPro-main/cache
  temstapro_hf_home: /srv/.cache/huggingface
  temstapro_transformers_offline: true
  protrek_python_bin: /opt/protrek/bin/python
  protrek_repo_root: /srv/ProTrek
  protrek_weights_dir: /srv/ProTrek/ProTrek_650M.pt
  colabfold_batch_bin: /opt/colabfold/bin/colabfold_batch
  colabfold_data_dir: /srv/.cache/colabfold
  foldseek_bin: /opt/foldseek/bin/foldseek
  foldseek_database_path: /srv/foldseek/db/afdb50
""".strip(),
        encoding="utf-8",
    )
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: calls.append("cluster")
        or {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: (
            calls.append("seed_sequence"),
            (tmp_path / "sequence_hits.tsv").write_text(
                "target_id\tseed_id\tsequence_score\ntarget1\tcas1\t0.9\n",
                encoding="utf-8",
            ),
            {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: (
            calls.append("seed_structure"),
            (tmp_path / "structure_hits.tsv").write_text(
                "target_id\tseed_id\tstructure_score\ntarget1\tcas1\t0.8\n",
                encoding="utf-8",
            ),
            {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: (
            calls.append("seed_merge"),
            (tmp_path / "seeded_targets.faa").write_text(">target1\nAAAAAA\n", encoding="utf-8"),
            {
                "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
                "seeded_targets_faa": tmp_path / "seeded_targets.faa",
                "seed_rows": [
                    {
                        "target_id": "target1",
                        "seed_ids": "cas1",
                        "seed_channels": "both",
                        "best_sequence_score": 0.9,
                        "best_structure_score": 0.8,
                    }
                ],
            },
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_temstapro_screen",
        lambda **kwargs: calls.append("thermo")
        or {"thermo_hits_faa": target_faa, "thermo_scores_tsv": tmp_path / "thermo.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_structure_predict_stage",
        lambda **kwargs: calls.append("structure")
        or {
            "structure_manifest": [{"protein_id": "target1", "pdb_path": str(tmp_path / "p1.pdb")}],
            "structure_manifest_json": tmp_path / "structure_manifest.json",
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline._read_scores_tsv",
        lambda path: [{"protein_id": "target1", "thermo_score": "0.9", "protrek_score": "0.8", "foldseek_score": "0.7"}],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: calls.append("report") or {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_demo",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=False,
    )

    assert calls == [
        "prefilter",
        "cluster",
        "seed_sequence",
        "seed_structure",
        "seed_merge",
        "thermo",
        "protrek",
        "structure",
        "foldseek",
        "report",
    ]


def test_run_seeded_pipeline_short_circuits_when_merge_is_empty(tmp_path, monkeypatch):
    from thermo_mining.pipeline import run_seeded_pipeline

    config_path = tmp_path / "platform.yaml"
    config_path.write_text(f"runtime:\n  runs_root: {tmp_path.as_posix()}/runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    calls: list[object] = []

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: calls.append("cluster")
        or {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: (
            calls.append("seed_sequence"),
            (tmp_path / "sequence_hits.tsv").write_text(
                "target_id\tseed_id\tsequence_score\ntarget1\tcas1\t0.9\n",
                encoding="utf-8",
            ),
            {"sequence_hits_tsv": tmp_path / "sequence_hits.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: (
            calls.append("seed_structure"),
            (tmp_path / "structure_hits.tsv").write_text(
                "target_id\tseed_id\tstructure_score\ntarget1\tcas1\t0.8\n",
                encoding="utf-8",
            ),
            {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: calls.append("seed_merge")
        or {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": tmp_path / "seeded_targets.faa",
            "seed_rows": [],
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: calls.append(("report", rows)) or {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_empty",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=False,
    )

    assert calls == [
        "prefilter",
        "cluster",
        "seed_sequence",
        "seed_structure",
        "seed_merge",
        ("report", []),
    ]


def test_run_seeded_pipeline_skips_seed_sequence_stage_when_resume_hash_matches(tmp_path, monkeypatch):
    import json

    from thermo_mining.pipeline import _combined_resume_hash, run_seeded_pipeline

    config_path = tmp_path / "platform.yaml"
    config_path.write_text(f"runtime:\n  runs_root: {tmp_path.as_posix()}/runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    run_root = tmp_path / "runs" / "seeded_resume"
    stage_dirs = build_stage_dirs(run_root, build_stage_order("seeded_proteins"))
    stage_dirs["seed_sequence_recall"].mkdir(parents=True, exist_ok=True)
    (stage_dirs["seed_sequence_recall"] / "sequence_hits.tsv").write_text(
        "target_id\tseed_id\tsequence_score\ntarget1\tcas1\t0.9\n",
        encoding="utf-8",
    )
    (stage_dirs["seed_sequence_recall"] / "DONE.json").write_text(
        json.dumps(
                {
                    "stage_name": "03_seed_sequence_recall",
                    "input_hash": _combined_resume_hash(seed_faa, target_faa),
                    "parameters": {},
                    "software_version": "test",
                    "runtime_seconds": 0.1,
                    "retain_count": 1,
                "reject_count": 0,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "thermo_mining.pipeline.run_prefilter",
        lambda **kwargs: {"filtered_faa": target_faa},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_mmseqs_cluster",
        lambda **kwargs: {"cluster_rep_faa": target_faa, "cluster_membership_tsv": tmp_path / "cluster.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_sequence_recall_stage",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("seed sequence stage should have been skipped")),
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_structure_recall_stage",
        lambda **kwargs: (
            (tmp_path / "structure_hits.tsv").write_text(
                "target_id\tseed_id\tstructure_score\ntarget1\tcas1\t0.8\n",
                encoding="utf-8",
            ),
            {"structure_hits_tsv": tmp_path / "structure_hits.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.run_seed_recall_merge_stage",
        lambda **kwargs: {
            "seed_manifest_tsv": tmp_path / "seed_manifest.tsv",
            "seeded_targets_faa": tmp_path / "seeded_targets.faa",
            "seed_rows": [],
        },
    )
    monkeypatch.setattr(
        "thermo_mining.pipeline.write_report_outputs",
        lambda stage_dir, run_name, rows: {"summary_md": tmp_path / "summary.md"},
    )

    run_seeded_pipeline(
        config_path=config_path,
        run_name="seeded_resume",
        seed_faa=seed_faa,
        target_faa=target_faa,
        resume=True,
    )


def test_cli_main_dispatches_run_seeded_pipeline(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("runtime:\n  runs_root: runs\n", encoding="utf-8")
    seed_faa = tmp_path / "seed.faa"
    seed_faa.write_text(">cas1\nMSTNPKPQRK\n", encoding="utf-8")
    target_faa = tmp_path / "targets.faa"
    target_faa.write_text(">target1\nAAAAAA\n", encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "thermo_mining.cli.run_seeded_pipeline",
        lambda **kwargs: captured.update(kwargs) or {"summary_md": tmp_path / "summary.md"},
    )

    main(
        [
            "run-seeded",
            "--config",
            str(config_path),
            "--run-name",
            "seeded_demo",
            "--seed-faa",
            str(seed_faa),
            "--target-faa",
            str(target_faa),
            "--resume",
        ]
    )

    assert captured["config_path"] == config_path
    assert captured["run_name"] == "seeded_demo"
    assert captured["seed_faa"] == seed_faa
    assert captured["target_faa"] == target_faa
    assert captured["resume"] is True
