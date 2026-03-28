import json
import subprocess
from pathlib import Path

from .run_store import clear_active_run, read_active_run


class ActiveRunConflict(RuntimeError):
    pass


class JobManager:
    def __init__(self, runs_root: str | Path, tmux_bin: str) -> None:
        self.runs_root = Path(runs_root)
        self.tmux_bin = tmux_bin

    def _session_name(self, run_id: str) -> str:
        return f"thermo_{run_id}"

    def _active_marker_path(self) -> Path:
        return self.runs_root / "_control_plane" / "active_run.json"

    def _claim_active_run(self, run_id: str) -> bool:
        marker = self._active_marker_path()
        marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            with marker.open("x", encoding="utf-8") as handle:
                json.dump({"run_id": run_id}, handle)
            return True
        except FileExistsError:
            active = read_active_run(self.runs_root)
            if active == run_id:
                return False
            raise ActiveRunConflict(f"active run already exists: {active}")

    def confirm_run(self, run_id: str) -> str:
        run_dir = self.runs_root / run_id
        session_name = self._session_name(run_id)
        claimed = self._claim_active_run(run_id)
        if not claimed:
            return session_name

        command = [
            self.tmux_bin,
            "new-session",
            "-d",
            "-s",
            session_name,
            f"thermo-mining run-job --run-dir {run_dir}",
        ]
        try:
            subprocess.run(command, check=True)
        except Exception:
            clear_active_run(self.runs_root)
            raise
        return session_name

    def stop_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "send-keys", "-t", self._session_name(run_id), "C-c"], check=True)
        clear_active_run(self.runs_root)

    def terminate_run(self, run_id: str) -> None:
        subprocess.run([self.tmux_bin, "kill-session", "-t", self._session_name(run_id)], check=True)
        clear_active_run(self.runs_root)

    def resume_run(self, run_id: str) -> str:
        return self.confirm_run(run_id)
