from dataclasses import dataclass, field
from pathlib import Path
import os

import yaml


def _read_env_file(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _env_text(env_data: dict[str, str], key: str, default: str | None = None) -> str | None:
    return env_data.get(key, default)


def _env_int(env_data: dict[str, str], key: str, default: int) -> int:
    value = env_data.get(key)
    return int(value) if value is not None else default


def _env_float(env_data: dict[str, str], key: str, default: float) -> float:
    value = env_data.get(key)
    return float(value) if value is not None else default


def _env_path(env_data: dict[str, str], key: str, default: Path) -> Path:
    value = env_data.get(key)
    return Path(value) if value is not None else default


def _env_list(env_data: dict[str, str], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = env_data.get(key)
    if value is None:
        return default
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


@dataclass(frozen=True)
class LLMSettings:
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None


@dataclass(frozen=True)
class RuntimeSettings:
    data_root: Path = Path("inputs")
    runs_root: Path = Path("runs")


@dataclass(frozen=True)
class ServiceSettings:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass(frozen=True)
class LoggingSettings:
    log_path: Path = Path("logs/platform.log")


@dataclass(frozen=True)
class ToolSettings:
    fastp_bin: str = "fastp"
    spades_bin: str = "spades.py"
    prodigal_bin: str = "prodigal"
    mmseqs_bin: str = "mmseqs"
    temstapro_bin: str = "temstapro"
    protrek_python_bin: str = "python"
    protrek_repo_root: Path = Path("/srv/ProTrek")
    protrek_weights_dir: Path = Path("/srv/ProTrek/weights/ProTrek_650M")
    foldseek_base_url: str = "http://127.0.0.1:8100"
    tmux_bin: str = "tmux"


@dataclass(frozen=True)
class DefaultSettings:
    prefilter_min_length: int = 80
    prefilter_max_length: int = 1200
    prefilter_max_single_residue_fraction: float = 0.7
    cluster_min_seq_id: float = 0.9
    cluster_coverage: float = 0.8
    cluster_threads: int = 64
    thermo_top_fraction: float = 0.1
    thermo_min_score: float = 0.5
    protrek_query_texts: tuple[str, ...] = field(
        default_factory=lambda: ("thermostable enzyme", "heat-stable protein")
    )
    protrek_batch_size: int = 8
    protrek_top_k: int = 50
    foldseek_database: str = "afdb50"
    foldseek_topk: int = 5
    foldseek_min_tmscore: float = 0.6


@dataclass(frozen=True)
class PlatformSettings:
    llm: LLMSettings
    runtime: RuntimeSettings
    service: ServiceSettings
    logging: LoggingSettings
    tools: ToolSettings
    defaults: DefaultSettings


def load_settings(config_path: str | Path, env_path: str | Path | None = None) -> PlatformSettings:
    config_raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    env_data = _read_env_file(Path(env_path) if env_path else None)
    env_data.update(os.environ)

    llm_raw = dict(config_raw.get("llm", {}))
    runtime_raw = dict(config_raw.get("runtime", {}))
    service_raw = dict(config_raw.get("service", {}))
    logging_raw = dict(config_raw.get("logging", {}))
    tools_raw = dict(config_raw.get("tools", {}))
    defaults_raw = dict(config_raw.get("defaults", {}))

    return PlatformSettings(
        llm=LLMSettings(
            model=_env_text(env_data, "THERMO_LLM_MODEL", llm_raw.get("model", "gpt-4o-mini")) or "gpt-4o-mini",
            api_key=_env_text(env_data, "THERMO_LLM_API_KEY", llm_raw.get("api_key")),
            base_url=_env_text(env_data, "THERMO_LLM_BASE_URL", llm_raw.get("base_url")),
        ),
        runtime=RuntimeSettings(
            data_root=_env_path(env_data, "THERMO_DATA_ROOT", Path(runtime_raw.get("data_root", "inputs"))),
            runs_root=_env_path(env_data, "THERMO_RUNS_ROOT", Path(runtime_raw.get("runs_root", "runs"))),
        ),
        service=ServiceSettings(
            host=_env_text(env_data, "THERMO_SERVICE_HOST", str(service_raw.get("host", "127.0.0.1"))) or "127.0.0.1",
            port=_env_int(env_data, "THERMO_SERVICE_PORT", int(service_raw.get("port", 8000))),
        ),
        logging=LoggingSettings(
            log_path=_env_path(env_data, "THERMO_LOG_PATH", Path(logging_raw.get("log_path", "logs/platform.log"))),
        ),
        tools=ToolSettings(
            fastp_bin=_env_text(env_data, "THERMO_FASTP_BIN", str(tools_raw.get("fastp_bin", "fastp"))) or "fastp",
            spades_bin=_env_text(env_data, "THERMO_SPADES_BIN", str(tools_raw.get("spades_bin", "spades.py"))) or "spades.py",
            prodigal_bin=_env_text(env_data, "THERMO_PRODIGAL_BIN", str(tools_raw.get("prodigal_bin", "prodigal"))) or "prodigal",
            mmseqs_bin=_env_text(env_data, "THERMO_MMSEQS_BIN", str(tools_raw.get("mmseqs_bin", "mmseqs"))) or "mmseqs",
            temstapro_bin=_env_text(env_data, "THERMO_TEMSTAPRO_BIN", str(tools_raw.get("temstapro_bin", "temstapro"))) or "temstapro",
            protrek_python_bin=_env_text(
                env_data,
                "THERMO_PROTREK_PYTHON_BIN",
                str(tools_raw.get("protrek_python_bin", "python")),
            )
            or "python",
            protrek_repo_root=_env_path(
                env_data,
                "THERMO_PROTREK_REPO_ROOT",
                Path(tools_raw.get("protrek_repo_root", "/srv/ProTrek")),
            ),
            protrek_weights_dir=_env_path(
                env_data,
                "THERMO_PROTREK_WEIGHTS_DIR",
                Path(tools_raw.get("protrek_weights_dir", "/srv/ProTrek/weights/ProTrek_650M")),
            ),
            foldseek_base_url=_env_text(
                env_data,
                "THERMO_FOLDSEEK_BASE_URL",
                str(tools_raw.get("foldseek_base_url", "http://127.0.0.1:8100")),
            )
            or "http://127.0.0.1:8100",
            tmux_bin=_env_text(env_data, "THERMO_TMUX_BIN", str(tools_raw.get("tmux_bin", "tmux"))) or "tmux",
        ),
        defaults=DefaultSettings(
            prefilter_min_length=_env_int(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MIN_LENGTH",
                int(defaults_raw.get("prefilter_min_length", 80)),
            ),
            prefilter_max_length=_env_int(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MAX_LENGTH",
                int(defaults_raw.get("prefilter_max_length", 1200)),
            ),
            prefilter_max_single_residue_fraction=_env_float(
                env_data,
                "THERMO_DEFAULT_PREFILTER_MAX_SINGLE_RESIDUE_FRACTION",
                float(defaults_raw.get("prefilter_max_single_residue_fraction", 0.7)),
            ),
            cluster_min_seq_id=_env_float(
                env_data,
                "THERMO_DEFAULT_CLUSTER_MIN_SEQ_ID",
                float(defaults_raw.get("cluster_min_seq_id", 0.9)),
            ),
            cluster_coverage=_env_float(
                env_data,
                "THERMO_DEFAULT_CLUSTER_COVERAGE",
                float(defaults_raw.get("cluster_coverage", 0.8)),
            ),
            cluster_threads=_env_int(
                env_data,
                "THERMO_DEFAULT_CLUSTER_THREADS",
                int(defaults_raw.get("cluster_threads", 64)),
            ),
            thermo_top_fraction=_env_float(
                env_data,
                "THERMO_DEFAULT_THERMO_TOP_FRACTION",
                float(defaults_raw.get("thermo_top_fraction", 0.1)),
            ),
            thermo_min_score=_env_float(
                env_data,
                "THERMO_DEFAULT_THERMO_MIN_SCORE",
                float(defaults_raw.get("thermo_min_score", 0.5)),
            ),
            protrek_query_texts=_env_list(
                env_data,
                "THERMO_DEFAULT_PROTREK_QUERY_TEXTS",
                tuple(defaults_raw.get("protrek_query_texts", ("thermostable enzyme", "heat-stable protein"))),
            ),
            protrek_batch_size=_env_int(
                env_data,
                "THERMO_DEFAULT_PROTREK_BATCH_SIZE",
                int(defaults_raw.get("protrek_batch_size", 8)),
            ),
            protrek_top_k=_env_int(
                env_data,
                "THERMO_DEFAULT_PROTREK_TOP_K",
                int(defaults_raw.get("protrek_top_k", 50)),
            ),
            foldseek_database=_env_text(
                env_data,
                "THERMO_DEFAULT_FOLDSEEK_DATABASE",
                str(defaults_raw.get("foldseek_database", "afdb50")),
            )
            or "afdb50",
            foldseek_topk=_env_int(
                env_data,
                "THERMO_DEFAULT_FOLDSEEK_TOPK",
                int(defaults_raw.get("foldseek_topk", 5)),
            ),
            foldseek_min_tmscore=_env_float(
                env_data,
                "THERMO_DEFAULT_FOLDSEEK_MIN_TMSCORE",
                float(defaults_raw.get("foldseek_min_tmscore", 0.6)),
            ),
        ),
    )
