import json
from pathlib import Path


def should_skip_stage(done_path: str | Path, expected_input_hash: str, resume: bool) -> bool:
    if not resume:
        return False
    done_path = Path(done_path)
    if not done_path.exists():
        return False
    payload = json.loads(done_path.read_text(encoding="utf-8"))
    return payload.get("input_hash") == expected_input_hash
