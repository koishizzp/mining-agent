from thermo_mining.config import load_pipeline_config, stage_output_dirs


def test_load_pipeline_config_reads_thresholds(tmp_path):
    config_path = tmp_path / "pipeline.yaml"
    config_path.write_text(
        """
project_name: hot_spring_phase1
results_root: results
prefilter:
  min_length: 80
  max_length: 1200
  max_single_residue_fraction: 0.7
cluster:
  min_seq_id: 0.9
  coverage: 0.8
  threads: 64
""".strip(),
        encoding="utf-8",
    )

    cfg = load_pipeline_config(config_path)

    assert cfg.project_name == "hot_spring_phase1"
    assert cfg.prefilter.min_length == 80
    assert cfg.cluster.coverage == 0.8


def test_stage_output_dirs_are_deterministic(tmp_path):
    dirs = stage_output_dirs(tmp_path / "results", "run_001")

    assert dirs["01_prefilter"].as_posix().endswith("results/run_001/01_prefilter")
    assert dirs["06_rerank"].name == "06_rerank"
