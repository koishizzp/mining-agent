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
    assert not hasattr(settings.tools, "foldseek_base_url")
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
    assert settings.defaults.foldseek_topk == 10
    assert settings.defaults.foldseek_min_tmscore == 0.67


def test_load_settings_reads_structure_runtime_fields_from_yaml_and_env(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
tools:
  colabfold_batch_bin: /opt/colabfold/bin/colabfold_batch
  colabfold_data_dir: /srv/.cache/colabfold
  foldseek_bin: /opt/foldseek/bin/foldseek
  foldseek_database_path: /srv/foldseek/db/afdb50
defaults:
  colabfold_msa_mode: single_sequence
  colabfold_num_models: 1
  colabfold_num_recycle: 2
""".strip(),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
THERMO_COLABFOLD_BATCH_BIN=/custom/colabfold_batch
THERMO_FOLDSEEK_DATABASE_PATH=/custom/foldseek/db
THERMO_DEFAULT_COLABFOLD_NUM_RECYCLE=3
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tools.colabfold_batch_bin == "/custom/colabfold_batch"
    assert settings.tools.colabfold_data_dir == Path("/srv/.cache/colabfold")
    assert settings.tools.foldseek_bin == "/opt/foldseek/bin/foldseek"
    assert settings.tools.foldseek_database_path == Path("/custom/foldseek/db")
    assert settings.defaults.colabfold_msa_mode == "single_sequence"
    assert settings.defaults.colabfold_num_models == 1
    assert settings.defaults.colabfold_num_recycle == 3


def test_load_settings_ignores_deprecated_defaults_foldseek_database(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
defaults:
  foldseek_database: legacy_db
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert not hasattr(settings.defaults, "foldseek_database")


def test_load_settings_ignores_deprecated_tools_foldseek_base_url(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
tools:
  foldseek_base_url: http://127.0.0.1:8100
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert not hasattr(settings.tools, "foldseek_base_url")


def test_load_settings_prefers_process_env_over_env_file(tmp_path, monkeypatch):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text("llm:\n  model: gpt-4o-mini\n", encoding="utf-8")
    env_path = tmp_path / ".env"
    env_path.write_text("THERMO_LLM_MODEL=gpt-5-mini\n", encoding="utf-8")
    monkeypatch.setenv("THERMO_LLM_MODEL", "gpt-5.1")

    settings = load_settings(config_path, env_path=env_path)

    assert settings.llm.model == "gpt-5.1"


def test_load_settings_reads_temstapro_runtime_fields_from_yaml_and_env(tmp_path):
    config_path = tmp_path / "platform.yaml"
    config_path.write_text(
        """
tools:
  conda_bin: /opt/miniconda/bin/conda
  temstapro_bin: /opt/temstapro/bin/temstapro
  temstapro_conda_env_name: temstapro_cpu
  temstapro_repo_root: /srv/TemStaPro-main
  temstapro_model_dir: /srv/TemStaPro-main/models
  temstapro_cache_dir: /srv/TemStaPro-main/cache
  temstapro_hf_home: /srv/.cache/huggingface
  temstapro_transformers_offline: false
""".strip(),
        encoding="utf-8",
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        """
THERMO_CONDA_BIN=/custom/conda
THERMO_TEMSTAPRO_CONDA_ENV_NAME=temstapro_env_CPU
THERMO_TEMSTAPRO_TRANSFORMERS_OFFLINE=1
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, env_path=env_path)

    assert settings.tools.conda_bin == "/custom/conda"
    assert settings.tools.temstapro_bin == "/opt/temstapro/bin/temstapro"
    assert settings.tools.temstapro_conda_env_name == "temstapro_env_CPU"
    assert settings.tools.temstapro_repo_root == Path("/srv/TemStaPro-main")
    assert settings.tools.temstapro_model_dir == Path("/srv/TemStaPro-main/models")
    assert settings.tools.temstapro_cache_dir == Path("/srv/TemStaPro-main/cache")
    assert settings.tools.temstapro_hf_home == Path("/srv/.cache/huggingface")
    assert settings.tools.temstapro_transformers_offline is True


def test_repo_no_longer_shadows_yaml_or_requests():
    assert not Path("src/yaml.py").exists()
    assert not Path("src/requests.py").exists()
