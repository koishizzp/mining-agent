import os
import shlex
import subprocess
from pathlib import Path

from .run_store import ActiveRunConflictError, claim_active_run, clear_active_run_if_match


class ActiveRunConflict(RuntimeError):
    pass


class JobManager:
    def __init__(
        self,
        runs_root: str | Path,
        tmux_bin: str,
        platform_config_path: str | Path | None = None,
    ) -> None:
        self.runs_root = Path(runs_root)
        self.tmux_bin = tmux_bin
        if platform_config_path is None:
            env_config_path = os.getenv("THERMO_PLATFORM_CONFIG")
            self.platform_config_path = Path(env_config_path) if env_config_path else None
        else:
            self.platform_config_path = Path(platform_config_path)

    def _session_name(self, run_id: str) -> str:
        return f"thermo_{run_id}"

    def confirm_run(self, run_id: str) -> str:
        run_dir = self.runs_root / run_id
        session_name = self._session_name(run_id)
        try:
            claimed = claim_active_run(self.runs_root, run_id)
        except ActiveRunConflictError as exc:
            raise ActiveRunConflict(str(exc)) from exc
        if not claimed:
            return session_name

        run_job_command = ["thermo-mining", "run-job"]
        if self.platform_config_path is not None:
            run_job_command.extend(["--config", str(self.platform_config_path)])
        run_job_command.extend(["--run-dir", str(run_dir)])

        command = [
            self.tmux_bin,
            "new-session",
            "-d",
            "-s",
            session_name,
            shlex.join(run_job_command),
        ]
        try:
            subprocess.run(command, check=True)
        except Exception:
            clear_active_run_if_match(self.runs_root, run_id)
            raise
        return session_name

    def stop_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "send-keys", "-t", self._session_name(run_id), "C-c"], check=True)
        clear_active_run_if_match(self.runs_root, run_id)

    def terminate_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "kill-session", "-t", self._session_name(run_id)], check=True)
        clear_active_run_if_match(self.runs_root, run_id)

    def resume_run(self, run_id: str) -> str:
        return self.confirm_run(run_id)
