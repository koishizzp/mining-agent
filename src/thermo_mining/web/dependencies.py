from thermo_mining.control_plane.job_manager import JobManager
from thermo_mining.control_plane.llm_client import OpenAIPlannerClient
from thermo_mining.settings import PlatformSettings, load_settings


class MissingOpenAIPlannerClient:
    def plan(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        raise ModuleNotFoundError("No module named 'openai'")


def get_settings() -> PlatformSettings:
    return load_settings("config/platform.example.yaml")


def get_llm_client() -> OpenAIPlannerClient | MissingOpenAIPlannerClient:
    settings = get_settings()
    try:
        return OpenAIPlannerClient(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
        )
    except ModuleNotFoundError:
        return MissingOpenAIPlannerClient()


def get_job_manager() -> JobManager:
    settings = get_settings()
    return JobManager(runs_root=settings.runtime.runs_root, tmux_bin=settings.tools.tmux_bin)
