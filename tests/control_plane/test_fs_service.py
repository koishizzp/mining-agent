import pytest

from thermo_mining.control_plane.fs_service import (
    list_path_entries,
    normalize_absolute_path,
    search_path_entries,
)


def test_normalize_absolute_path_rejects_relative_paths(tmp_path):
    with pytest.raises(ValueError):
        normalize_absolute_path("relative/path.txt")


def test_list_path_entries_returns_sorted_children(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    rows = list_path_entries(tmp_path)

    assert [row.name for row in rows] == ["a.txt", "b.txt"]
    assert rows[0].kind == "file"


def test_search_path_entries_finds_nested_matches(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hot_spring_reads_1.fq.gz").write_text("x", encoding="utf-8")

    rows = search_path_entries(tmp_path, "hot_spring")

    assert rows[0].path.endswith("hot_spring_reads_1.fq.gz")
