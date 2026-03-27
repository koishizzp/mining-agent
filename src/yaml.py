from __future__ import annotations


def _parse_scalar(value: str):
    value = value.strip()
    if value == "":
        return ""
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def safe_load(text: str):
    root: dict[str, object] = {}
    current_section: dict[str, object] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  "):
            if current_section is None:
                continue
            key, value = raw_line.strip().split(":", 1)
            current_section[key.strip()] = _parse_scalar(value)
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            new_section: dict[str, object] = {}
            root[key] = new_section
            current_section = new_section
        else:
            root[key] = _parse_scalar(value)
            current_section = None
    return root
