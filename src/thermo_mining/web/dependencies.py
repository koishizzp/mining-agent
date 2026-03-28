import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from thermo_mining.control_plane.job_manager import JobManager
from thermo_mining.control_plane.llm_client import OpenAIPlannerClient
from thermo_mining.settings import PlatformSettings, load_settings


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "platform.example.yaml"


def get_settings() -> PlatformSettings:
    config_path = Path(os.getenv("THERMO_PLATFORM_CONFIG", str(_default_config_path())))
    return load_settings(config_path)


def get_llm_client(settings: Annotated[PlatformSettings, Depends(get_settings)]) -> OpenAIPlannerClient:
    return OpenAIPlannerClient(
        model=settings.llm.model,
        api_key=settings.llm.api_key,
        base_url=settings.llm.base_url,
    )


def get_job_manager(settings: Annotated[PlatformSettings, Depends(get_settings)]) -> JobManager:
    return JobManager(runs_root=settings.runtime.runs_root, tmux_bin=settings.tools.tmux_bin)
