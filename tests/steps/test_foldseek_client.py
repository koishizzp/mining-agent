from pathlib import Path

from thermo_mining.steps.foldseek_client import build_foldseek_easy_search_command, run_foldseek_stage


def test_build_foldseek_easy_search_command_uses_local_binary(tmp_path):
    cmd = build_foldseek_easy_search_command(
        foldseek_bin="/opt/foldseek/bin/foldseek",
        query_pdb=tmp_path / "p1.pdb",
        database_path=Path("/srv/foldseek/db/afdb50"),
        output_tsv=tmp_path / "raw" / "p1.tsv",
        tmp_dir=tmp_path / "tmp" / "p1",
        topk=5,
    )

    assert cmd[:2] == ["/opt/foldseek/bin/foldseek", "easy-search"]
    assert cmd[2] == str(tmp_path / "p1.pdb")
    assert cmd[3] == "/srv/foldseek/db/afdb50"
    assert "--format-output" in cmd
    assert "--max-seqs" in cmd


def test_run_foldseek_stage_filters_hits_by_min_tmscore(tmp_path, monkeypatch):
    query_pdb = tmp_path / "structures" / "p1.pdb"
    query_pdb.parent.mkdir(parents=True, exist_ok=True)
    query_pdb.write_text("MODEL P1\n", encoding="utf-8")

    def fake_run(cmd, check):
        output_tsv = Path(cmd[4])
        output_tsv.parent.mkdir(parents=True, exist_ok=True)
        output_tsv.write_text(
            "query\thit_low\t0.55\nquery\thit_high\t0.81\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.foldseek_client.subprocess.run", fake_run)

    result = run_foldseek_stage(
        structure_manifest=[{"protein_id": "p1", "pdb_path": str(query_pdb)}],
        stage_dir=tmp_path / "06_foldseek",
        foldseek_bin="/opt/foldseek/bin/foldseek",
        database_path=Path("/srv/foldseek/db/afdb50"),
        topk=5,
        min_tmscore=0.6,
        software_version="test",
    )

    assert result["foldseek_scores_tsv"] == tmp_path / "06_foldseek" / "scores.tsv"
    assert "0.81" in (tmp_path / "06_foldseek" / "scores.tsv").read_text(encoding="utf-8")


def test_run_foldseek_stage_returns_zero_when_no_hit_passes_threshold(tmp_path, monkeypatch):
    query_pdb = tmp_path / "structures" / "p2.pdb"
    query_pdb.parent.mkdir(parents=True, exist_ok=True)
    query_pdb.write_text("MODEL P2\n", encoding="utf-8")

    def fake_run(cmd, check):
        output_tsv = Path(cmd[4])
        output_tsv.parent.mkdir(parents=True, exist_ok=True)
        output_tsv.write_text(
            "query\thit_low\t0.40\n",
            encoding="utf-8",
        )

    monkeypatch.setattr("thermo_mining.steps.foldseek_client.subprocess.run", fake_run)

    run_foldseek_stage(
        structure_manifest=[{"protein_id": "p2", "pdb_path": str(query_pdb)}],
        stage_dir=tmp_path / "06_foldseek",
        foldseek_bin="/opt/foldseek/bin/foldseek",
        database_path=Path("/srv/foldseek/db/afdb50"),
        topk=5,
        min_tmscore=0.6,
        software_version="test",
    )

    assert "0.0" in (tmp_path / "06_foldseek" / "scores.tsv").read_text(encoding="utf-8")
