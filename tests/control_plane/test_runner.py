import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from thermo_mining.control_plane.run_store import create_pending_run
from thermo_mining.control_plane.runner import run_job
from thermo_mining.control_plane.schemas import ExecutionPlan, InputBundle
from thermo_mining.control_plane.stage_graph import build_stage_order


def _make_plan(
    bundle_type: str,
    input_paths: list[str],
    output_root: str,
    overrides: dict[str, object] | None = None,
) -> ExecutionPlan:
    bundle = InputBundle(
        bundle_type=bundle_type,
        sample_id="S01",
        input_paths=input_paths,
        metadata={},
        output_root=output_root,
    )
    return ExecutionPlan(
        bundle_type=bundle_type,
        input_items=[bundle],
        stage_order=build_stage_order(bundle_type),
        parameter_overrides=overrides or {},
        output_root=output_root,
        resume_policy="if_possible",
        explanation="test",
    )


def _install_score_stubs(monkeypatch, tmp_path: Path, calls: list[str], report_paths: list[Path] | None = None) -> None:
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.combine_stage_scores",
        lambda **kwargs: [
            {
                "protein_id": "p1",
                "tier": "Tier 1",
                "final_score": 0.9,
                "thermo_score": 0.9,
                "protrek_score": 0.9,
                "foldseek_score": 0.9,
                "origin_bonus": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner._read_scores_tsv",
        lambda path: [
            {
                "protein_id": "p1",
                "thermo_score": "0.9",
                "protrek_score": "0.9",
                "foldseek_score": "0.9",
            }
        ],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.write_report_outputs",
        lambda stage_dir, *args, **kwargs: (
            calls.append("report"),
            report_paths.append(Path(stage_dir)) if report_paths is not None else None,
            {"summary_md": tmp_path / "summary.md"},
        )[-1],
    )


def test_run_job_executes_expected_stage_order_for_contigs(tmp_path, monkeypatch):
    plan = _make_plan("contigs", ["/mnt/disk2/S01_contigs.fa"], "/runs/S01")
    record = create_pending_run(tmp_path, plan)
    calls: list[str] = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prodigal_stage",
        lambda **kwargs: calls.append("prodigal") or {"proteins_faa": tmp_path / "proteins.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": tmp_path / "filtered.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": tmp_path / "cluster.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_temstapro_screen",
        lambda **kwargs: (
            calls.append("temstapro"),
            (tmp_path / "hits.faa").write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8"),
            {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    _install_score_stubs(monkeypatch, tmp_path, calls)

    run_job(record.run_dir)

    state = json.loads((tmp_path / record.run_id / "runtime_state.json").read_text(encoding="utf-8"))
    assert calls == ["prodigal", "prefilter", "mmseqs", "temstapro", "protrek", "foldseek", "report"]
    assert state["status"] == "succeeded"


def test_run_job_executes_expected_stage_order_for_paired_fastq(tmp_path, monkeypatch):
    plan = _make_plan(
        "paired_fastq",
        ["/mnt/disk2/S01_R1.fastq.gz", "/mnt/disk2/S01_R2.fastq.gz"],
        "/runs/S01",
    )
    record = create_pending_run(tmp_path, plan)
    calls: list[str] = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_fastp_stage",
        lambda **kwargs: calls.append("fastp") or {"read1": tmp_path / "clean_R1.fastq.gz", "read2": tmp_path / "clean_R2.fastq.gz"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_spades_stage",
        lambda **kwargs: calls.append("spades") or {"contigs_fa": tmp_path / "contigs.fasta"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prodigal_stage",
        lambda **kwargs: calls.append("prodigal") or {"proteins_faa": tmp_path / "proteins.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": tmp_path / "filtered.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": tmp_path / "cluster.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_temstapro_screen",
        lambda **kwargs: (
            calls.append("temstapro"),
            (tmp_path / "hits.faa").write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8"),
            {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    _install_score_stubs(monkeypatch, tmp_path, calls)

    run_job(record.run_dir)

    assert calls == ["fastp", "spades", "prodigal", "prefilter", "mmseqs", "temstapro", "protrek", "foldseek", "report"]


def test_run_job_applies_overrides_and_builds_foldseek_manifest(tmp_path, monkeypatch):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">seed\nMSTNPKPQRK\n", encoding="utf-8")
    overrides = {
        "prefilter_min_length": 101,
        "prefilter_max_length": 999,
        "prefilter_max_single_residue_fraction": 0.42,
        "thermo_top_fraction": 0.25,
        "thermo_min_score": 0.73,
        "protrek_top_k": 13,
        "foldseek_topk": 7,
        "foldseek_min_tmscore": 0.88,
    }
    plan = _make_plan("proteins", [str(input_faa)], "/runs/S01", overrides=overrides)
    record = create_pending_run(tmp_path, plan)
    captured: dict[str, dict[str, object]] = {}
    calls: list[str] = []

    def fake_prefilter(**kwargs):
        captured["prefilter"] = kwargs
        calls.append("prefilter")
        return {"filtered_faa": tmp_path / "filtered.faa"}

    def fake_mmseqs(**kwargs):
        calls.append("mmseqs")
        return {"cluster_rep_faa": tmp_path / "cluster.faa"}

    def fake_temstapro(**kwargs):
        captured["temstapro"] = kwargs
        calls.append("temstapro")
        hits_faa = tmp_path / "hits.faa"
        hits_faa.write_text(">p1 desc\nMSTNPKPQRK\n>p2\nAAAAAA\n", encoding="utf-8")
        return {"thermo_hits_faa": hits_faa, "thermo_scores_tsv": tmp_path / "thermo.tsv"}

    def fake_protrek(**kwargs):
        captured["protrek"] = kwargs
        calls.append("protrek")
        return {"protrek_scores_tsv": tmp_path / "protrek.tsv"}

    def fake_foldseek(**kwargs):
        captured["foldseek"] = kwargs
        calls.append("foldseek")
        return {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"}

    monkeypatch.setattr("thermo_mining.control_plane.runner.run_prefilter", fake_prefilter)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_mmseqs_cluster", fake_mmseqs)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_temstapro_screen", fake_temstapro)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_protrek_stage", fake_protrek)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_foldseek_stage", fake_foldseek)
    _install_score_stubs(monkeypatch, tmp_path, calls)

    run_job(record.run_dir)

    assert captured["prefilter"]["min_length"] == 101
    assert captured["prefilter"]["max_length"] == 999
    assert captured["prefilter"]["max_single_residue_fraction"] == 0.42
    assert captured["temstapro"]["top_fraction"] == 0.25
    assert captured["temstapro"]["min_score"] == 0.73
    assert captured["protrek"]["top_k"] == 13
    assert captured["foldseek"]["topk"] == 7
    assert captured["foldseek"]["min_tmscore"] == 0.88
    assert captured["foldseek"]["structure_manifest"] == [
        {
            "protein_id": "p1",
            "pdb_path": str(Path(record.run_dir) / "05_foldseek" / "structures" / "p1.pdb"),
        },
        {
            "protein_id": "p2",
            "pdb_path": str(Path(record.run_dir) / "05_foldseek" / "structures" / "p2.pdb"),
        },
    ]


def test_run_job_writes_reports_to_reports_directory(tmp_path, monkeypatch):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">seed\nMSTNPKPQRK\n", encoding="utf-8")
    plan = _make_plan("proteins", [str(input_faa)], "/runs/S01")
    record = create_pending_run(tmp_path, plan)
    calls: list[str] = []
    report_paths: list[Path] = []

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: calls.append("prefilter") or {"filtered_faa": tmp_path / "filtered.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_mmseqs_cluster",
        lambda **kwargs: calls.append("mmseqs") or {"cluster_rep_faa": tmp_path / "cluster.faa"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_temstapro_screen",
        lambda **kwargs: (
            calls.append("temstapro"),
            (tmp_path / "hits.faa").write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8"),
            {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"},
        )[-1],
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_protrek_stage",
        lambda **kwargs: calls.append("protrek") or {"protrek_scores_tsv": tmp_path / "protrek.tsv"},
    )
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_foldseek_stage",
        lambda **kwargs: calls.append("foldseek") or {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"},
    )
    _install_score_stubs(monkeypatch, tmp_path, calls, report_paths=report_paths)

    run_job(record.run_dir)

    assert report_paths == [Path(record.run_dir) / "reports"]


def test_run_job_uses_settings_derived_tool_and_default_values(tmp_path, monkeypatch):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">seed\nMSTNPKPQRK\n", encoding="utf-8")
    plan = _make_plan("proteins", [str(input_faa)], "/runs/S01")
    record = create_pending_run(tmp_path, plan)
    captured: dict[str, dict[str, object]] = {}
    calls: list[str] = []

    monkeypatch.setenv("THERMO_PLATFORM_CONFIG", str(tmp_path / "platform.yaml"))
    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.load_settings",
        lambda path: SimpleNamespace(
            tools=SimpleNamespace(
                fastp_bin="fastp",
                spades_bin="spades.py",
                prodigal_bin="prodigal",
                mmseqs_bin="/custom/mmseqs",
                temstapro_bin="/custom/temstapro",
                protrek_python_bin="/custom/python",
                protrek_repo_root=Path("/srv/custom-protrek"),
                protrek_weights_dir=Path("/srv/custom-protrek/weights"),
                foldseek_base_url="http://foldseek.internal:9000",
            ),
            defaults=SimpleNamespace(
                prefilter_min_length=111,
                prefilter_max_length=888,
                prefilter_max_single_residue_fraction=0.39,
                cluster_min_seq_id=0.77,
                cluster_coverage=0.66,
                cluster_threads=12,
                thermo_top_fraction=0.31,
                thermo_min_score=0.61,
                protrek_query_texts=("thermostable enzyme", "industrial catalyst"),
                protrek_batch_size=5,
                protrek_top_k=17,
                foldseek_database="customdb",
                foldseek_topk=9,
                foldseek_min_tmscore=0.91,
            ),
        ),
    )

    def fake_prefilter(**kwargs):
        captured["prefilter"] = kwargs
        calls.append("prefilter")
        return {"filtered_faa": tmp_path / "filtered.faa"}

    monkeypatch.setattr("thermo_mining.control_plane.runner.run_prefilter", fake_prefilter)
    def fake_mmseqs(**kwargs):
        captured["mmseqs"] = kwargs
        calls.append("mmseqs")
        return {"cluster_rep_faa": tmp_path / "cluster.faa"}

    def fake_temstapro(**kwargs):
        captured["temstapro"] = kwargs
        calls.append("temstapro")
        (tmp_path / "hits.faa").write_text(">p1\nMSTNPKPQRK\n", encoding="utf-8")
        return {"thermo_hits_faa": tmp_path / "hits.faa", "thermo_scores_tsv": tmp_path / "thermo.tsv"}

    def fake_protrek(**kwargs):
        captured["protrek"] = kwargs
        calls.append("protrek")
        return {"protrek_scores_tsv": tmp_path / "protrek.tsv"}

    def fake_foldseek(**kwargs):
        captured["foldseek"] = kwargs
        calls.append("foldseek")
        return {"foldseek_scores_tsv": tmp_path / "foldseek.tsv"}

    monkeypatch.setattr("thermo_mining.control_plane.runner.run_mmseqs_cluster", fake_mmseqs)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_temstapro_screen", fake_temstapro)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_protrek_stage", fake_protrek)
    monkeypatch.setattr("thermo_mining.control_plane.runner.run_foldseek_stage", fake_foldseek)
    _install_score_stubs(monkeypatch, tmp_path, calls)

    run_job(record.run_dir)

    assert captured["prefilter"]["min_length"] == 111
    assert captured["prefilter"]["max_length"] == 888
    assert captured["prefilter"]["max_single_residue_fraction"] == 0.39
    assert captured["mmseqs"]["mmseqs_bin"] == "/custom/mmseqs"
    assert captured["mmseqs"]["min_seq_id"] == 0.77
    assert captured["mmseqs"]["coverage"] == 0.66
    assert captured["mmseqs"]["threads"] == 12
    assert captured["temstapro"]["temstapro_bin"] == "/custom/temstapro"
    assert captured["temstapro"]["top_fraction"] == 0.31
    assert captured["temstapro"]["min_score"] == 0.61
    assert captured["protrek"]["python_bin"] == "/custom/python"
    assert captured["protrek"]["repo_root"] == Path("/srv/custom-protrek")
    assert captured["protrek"]["weights_dir"] == Path("/srv/custom-protrek/weights")
    assert captured["protrek"]["query_texts"] == ["thermostable enzyme", "industrial catalyst"]
    assert captured["protrek"]["batch_size"] == 5
    assert captured["protrek"]["top_k"] == 17
    assert captured["foldseek"]["base_url"] == "http://foldseek.internal:9000"
    assert captured["foldseek"]["database"] == "customdb"
    assert captured["foldseek"]["topk"] == 9
    assert captured["foldseek"]["min_tmscore"] == 0.91


def test_run_job_marks_runtime_state_failed_when_stage_raises(tmp_path, monkeypatch):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(">seed\nMSTNPKPQRK\n", encoding="utf-8")
    plan = _make_plan("proteins", [str(input_faa)], "/runs/S01")
    record = create_pending_run(tmp_path, plan)

    monkeypatch.setattr(
        "thermo_mining.control_plane.runner.run_prefilter",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("prefilter failed")),
    )

    with pytest.raises(RuntimeError, match="prefilter failed"):
        run_job(record.run_dir)

    state = json.loads((Path(record.run_dir) / "runtime_state.json").read_text(encoding="utf-8"))
    assert state["status"] == "failed"
    assert state["active_stage"] == "prefilter"
    assert state["error_summary"] == "prefilter failed"
