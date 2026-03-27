import argparse
from pathlib import Path

from .pipeline import run_pipeline


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


def main(argv: list[str] | None = None) -> dict[str, object] | None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        return None
    return run_pipeline(
        config_path=Path(args.config),
        run_name=args.run_name,
        input_faa=Path(args.input_faa),
        resume=args.resume,
    )
