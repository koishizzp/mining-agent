import argparse
import os
from pathlib import Path

import uvicorn

from .control_plane import runner as control_plane_runner
from .control_plane.run_store import clear_active_run_if_match
from .pipeline import run_pipeline
from .settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thermo-mining")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--run-name", required=True)
    run_parser.add_argument("--input-faa", required=True)
    run_parser.add_argument("--resume", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.add_argument("--config", default="config/platform.example.yaml")

    run_job_parser = subparsers.add_parser("run-job")
    run_job_parser.add_argument("--run-dir", required=True)
    run_job_parser.add_argument("--config", default="config/platform.example.yaml")
    return parser


def serve_app(config_path: str | Path, host: str | None, port: int | None) -> None:
    resolved_config_path = Path(config_path)
    os.environ["THERMO_PLATFORM_CONFIG"] = str(resolved_config_path)
    settings = load_settings(resolved_config_path)
    app_host = host or settings.service.host
    app_port = port or settings.service.port
    uvicorn.run("thermo_mining.web.app:create_app", factory=True, host=app_host, port=app_port)


def run_job(run_dir: str | Path, config_path: str | Path | None = None) -> None:
    run_dir_path = Path(run_dir)
    runs_root = run_dir_path.parent
    if config_path is not None:
        os.environ["THERMO_PLATFORM_CONFIG"] = str(Path(config_path))
    try:
        control_plane_runner.run_job(run_dir_path)
    finally:
        clear_active_run_if_match(runs_root, run_dir_path.name)


def main(argv: list[str] | None = None) -> dict[str, object] | None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        serve_app(args.config, args.host, args.port)
        return None
    if args.command == "run-job":
        run_job(args.run_dir, args.config)
        return None
    if args.command != "run":
        return None
    return run_pipeline(
        config_path=Path(args.config),
        run_name=args.run_name,
        input_faa=Path(args.input_faa),
        resume=args.resume,
    )
