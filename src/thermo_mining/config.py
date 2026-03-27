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
    min_seq_id: float = 0.9
    coverage: float = 0.8
    threads: int = 64


@dataclass(frozen=True)
class ThermoConfig:
    top_fraction: float = 0.1
    min_score: float = 0.5


@dataclass(frozen=True)
class PipelineConfig:
    project_name: str
    results_root: Path
    prefilter: PrefilterConfig
    cluster: ClusterConfig
    thermo: ThermoConfig


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PipelineConfig(
        project_name=raw["project_name"],
        results_root=Path(raw["results_root"]),
        prefilter=PrefilterConfig(**raw.get("prefilter", {})),
        cluster=ClusterConfig(**raw.get("cluster", {})),
        thermo=ThermoConfig(**raw.get("thermo", {})),
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
