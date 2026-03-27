from pathlib import Path

from thermo_mining.settings import load_settings


def test_load_settings_reads_env_over_yaml(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
llm:
  model: gpt-4o-mini
  api_key: yaml-key
  base_url: https://llm.example/v1
runtime:
  data_root: /srv/thermo/data
  runs_root: /srv/thermo/runs
service:
  host: 0.0.0.0
  port: 9000
logging:
  log_path: /var/log/thermo/platform.log
tools:
  fastp_bin: /usr/bin/fastp
  spades_bin: /usr/bin/spades.py
  prodigal_bin: /usr/bin/prodigal
  mmseqs_bin: /usr/bin/mmseqs
  temstapro_bin: /opt/temstapro/bin/temstapro
  protrek_python_bin: /opt/protrek/bin/python
  protrek_repo_root: /srv/ProTrek
  protrek_weights_dir: /srv/ProTrek/weights/ProTrek_650M
  foldseek_base_url: http://127.0.0.1:8100
defaults:
  prefilter_min_length: 90
  prefilter_max_length: 1400
  prefilter_max_single_residue_fraction: 0.75
  cluster_min_seq_id: 0.92
  cluster_threads: 32
  cluster_coverage: 0.85
  thermo_top_fraction: 0.2
  thermo_min_score: 0.61
  protrek_query_texts:
    - thermostable enzyme
    - heat-stable protein
  protrek_batch_size: 16
  protrek_top_k: 75
  foldseek_database: swissprot
  foldseek_topk: 10
  foldseek_min_tmscore: 0.67
""".strip(),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
THERMO_LLM_MODEL=gpt-5-mini
THERMO_RUNS_ROOT=/mnt/disk4/thermo-runs
THERMO_SERVICE_PORT=9100
THERMO_LOG_PATH=/mnt/disk4/logs/platform.log
THERMO_MMSEQS_BIN=/opt/mmseqs/bin/mmseqs
THERMO_DEFAULT_THERMO_MIN_SCORE=0.72
THERMO_DEFAULT_PROTREK_QUERY_TEXTS=thermostable enzyme,heat-shock protein
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=env_path)

    assert settings.llm.model == "gpt-5-mini"
    assert settings.runtime.data_root == Path("/srv/thermo/data")
    assert settings.runtime.runs_root.as_posix() == "/mnt/disk4/thermo-runs"
    assert settings.service.host == "0.0.0.0"
    assert settings.service.port == 9100
    assert settings.logging.log_path.as_posix() == "/mnt/disk4/logs/platform.log"
    assert settings.tools.fastp_bin == "/usr/bin/fastp"
    assert settings.tools.prodigal_bin == "/usr/bin/prodigal"
    assert settings.tools.mmseqs_bin == "/opt/mmseqs/bin/mmseqs"
    assert settings.defaults.prefilter_min_length == 90
    assert settings.defaults.prefilter_max_length == 1400
    assert settings.defaults.prefilter_max_single_residue_fraction == 0.75
    assert settings.defaults.cluster_min_seq_id == 0.92
    assert settings.defaults.cluster_threads == 32
    assert settings.defaults.cluster_coverage == 0.85
    assert settings.defaults.thermo_top_fraction == 0.2
    assert settings.defaults.thermo_min_score == 0.72
    assert settings.defaults.protrek_query_texts == ("thermostable enzyme", "heat-shock protein")
    assert settings.defaults.protrek_batch_size == 16
    assert settings.defaults.protrek_top_k == 75
    assert settings.defaults.foldseek_database == "swissprot"
    assert settings.defaults.foldseek_topk == 10
    assert settings.defaults.foldseek_min_tmscore == 0.67


def test_load_settings_prefers_process_env_over_env_file(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("llm:\n  model: gpt-4o-mini\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text("THERMO_LLM_MODEL=gpt-5-mini\n", encoding="utf-8")
    monkeypatch.setenv("THERMO_LLM_MODEL", "gpt-5.1")

    settings = load_settings(config_path, env_path=env_path)

    assert settings.llm.model == "gpt-5.1"


def test_repo_no_longer_shadows_yaml_or_requests():
    assert not Path("src/yaml.py").exists()
    assert not Path("src/requests.py").exists()
