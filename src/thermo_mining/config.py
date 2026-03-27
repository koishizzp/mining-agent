from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PrefilterConfig:
    min_length: int = 80
    max_length: int = 1200
    max_single_residue_fraction: float = 0.7


@dataclass(frozen=True)
class ClusterConfig:
    mmseqs_bin: str = "mmseqs"
    min_seq_id: float = 0.9
    coverage: float = 0.8
    threads: int = 64


@dataclass(frozen=True)
class ThermoConfig:
    temstapro_bin: str = "temstapro"
    model_dir: Path = Path("/models/temstapro/ProtTrans")
    cache_dir: Path = Path("/tmp/temstapro_cache")
    top_fraction: float = 0.1
    min_score: float = 0.5


@dataclass(frozen=True)
class ProtrekConfig:
    python_bin: str = "python"
    repo_root: Path = Path("/srv/ProTrek")
    weights_dir: Path = Path("/srv/ProTrek/weights/ProTrek_650M")
    query_texts: tuple[str, ...] = ("thermostable enzyme", "heat-stable protein")
    batch_size: int = 8
    top_k: int = 50
    index_script: Path = Path("scripts/protrek_build_index.py")
    query_script: Path = Path("scripts/protrek_query.py")


@dataclass(frozen=True)
class FoldseekConfig:
    base_url: str = "http://127.0.0.1:8100"
    database: str = "afdb50"
    topk: int = 5
    min_tmscore: float = 0.6


@dataclass(frozen=True)
class PipelineConfig:
    project_name: str
    results_root: Path
    prefilter: PrefilterConfig
    cluster: ClusterConfig
    thermo: ThermoConfig
    protrek: ProtrekConfig
    foldseek: FoldseekConfig


def _load_yaml_dict(path: str | Path) -> dict[str, object]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return raw or {}


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    raw = _load_yaml_dict(path)
    cluster_raw = dict(raw.get("cluster", {}))
    thermo_raw = dict(raw.get("thermo", {}))
    protrek_raw = dict(raw.get("protrek", {}))
    foldseek_raw = dict(raw.get("foldseek", {}))

    return PipelineConfig(
        project_name=str(raw["project_name"]),
        results_root=Path(raw["results_root"]),
        prefilter=PrefilterConfig(**raw.get("prefilter", {})),
        cluster=ClusterConfig(**cluster_raw),
        thermo=ThermoConfig(
            temstapro_bin=str(thermo_raw.get("temstapro_bin", "temstapro")),
            model_dir=Path(thermo_raw.get("model_dir", "/models/temstapro/ProtTrans")),
            cache_dir=Path(thermo_raw.get("cache_dir", "/tmp/temstapro_cache")),
            top_fraction=float(thermo_raw.get("top_fraction", 0.1)),
            min_score=float(thermo_raw.get("min_score", 0.5)),
        ),
        protrek=ProtrekConfig(
            python_bin=str(protrek_raw.get("python_bin", "python")),
            repo_root=Path(protrek_raw.get("repo_root", "/srv/ProTrek")),
            weights_dir=Path(protrek_raw.get("weights_dir", "/srv/ProTrek/weights/ProTrek_650M")),
            query_texts=tuple(protrek_raw.get("query_texts", ("thermostable enzyme", "heat-stable protein"))),
            batch_size=int(protrek_raw.get("batch_size", 8)),
            top_k=int(protrek_raw.get("top_k", 50)),
            index_script=Path(protrek_raw.get("index_script", "scripts/protrek_build_index.py")),
            query_script=Path(protrek_raw.get("query_script", "scripts/protrek_query.py")),
        ),
        foldseek=FoldseekConfig(
            base_url=str(foldseek_raw.get("base_url", "http://127.0.0.1:8100")),
            database=str(foldseek_raw.get("database", "afdb50")),
            topk=int(foldseek_raw.get("topk", 5)),
            min_tmscore=float(foldseek_raw.get("min_tmscore", 0.6)),
        ),
    )


def stage_output_dirs(results_root: str | Path, run_name: str) -> dict[str, Path]:
    base = Path(results_root) / run_name
    return {
        "01_prefilter": base / "01_prefilter",
        "02_cluster": base / "02_cluster",
        "03_thermo_screen": base / "03_thermo_screen",
        "04_protrek_recall": base / "04_protrek_recall",
        "05_foldseek_confirm": base / "05_foldseek_confirm",
        "06_rerank": base / "06_rerank",
    }
