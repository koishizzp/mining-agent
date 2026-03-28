from pathlib import Path

from .schemas import PathEntry


def normalize_absolute_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        raise ValueError("path must be absolute")

    resolved = resolved.resolve()
    if not resolved.exists():
        raise FileNotFoundError(resolved)

    return resolved


def _to_path_entry(path: Path) -> PathEntry:
    stat = path.stat()
    return PathEntry(
        path=str(path),
        name=path.name,
        kind="dir" if path.is_dir() else "file",
        size=stat.st_size,
        mtime=stat.st_mtime,
        is_symlink=path.is_symlink(),
    )


def list_path_entries(path: str | Path) -> list[PathEntry]:
    root = normalize_absolute_path(path)
    if not root.is_dir():
        raise ValueError("path must be a directory")

    return [
        _to_path_entry(child)
        for child in sorted(root.iterdir(), key=lambda item: item.name.lower())
    ]


def search_path_entries(root: str | Path, query: str, limit: int = 50) -> list[PathEntry]:
    base = normalize_absolute_path(root)
    if not base.is_dir():
        raise ValueError("path must be a directory")
    if limit <= 0:
        return []

    matches: list[PathEntry] = []

    for candidate in base.rglob("*"):
        if query.lower() in candidate.name.lower():
            matches.append(_to_path_entry(candidate))
        if len(matches) >= limit:
            break

    return matches
