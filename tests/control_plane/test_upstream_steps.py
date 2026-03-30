from pathlib import Path

from thermo_mining.control_plane import upstream_steps
from thermo_mining.control_plane.upstream_steps import (
    build_fastp_command,
    build_prodigal_command,
    build_spades_command,
    run_fastp_stage,
    run_prodigal_stage,
    run_spades_stage,
)


def test_build_fastp_command_includes_required_flags_and_paths_in_order(tmp_path):
    read1 = tmp_path / "sample_1.fq.gz"
    read2 = tmp_path / "sample_2.fq.gz"
    out_read1 = tmp_path / "clean_1.fq.gz"
    out_read2 = tmp_path / "clean_2.fq.gz"
    html_report = tmp_path / "fastp.html"
    json_report = tmp_path / "fastp.json"

    cmd = build_fastp_command(
        fastp_bin="fastp",
        read1=read1,
        read2=read2,
        out_read1=out_read1,
        out_read2=out_read2,
        html_report=html_report,
        json_report=json_report,
    )

    assert cmd == [
        "fastp",
        "-i",
        str(read1),
        "-I",
        str(read2),
        "-o",
        str(out_read1),
        "-O",
        str(out_read2),
        "--html",
        str(html_report),
        "--json",
        str(json_report),
    ]


def test_build_spades_command_includes_required_flags_and_paths_in_order(tmp_path):
    read1 = tmp_path / "clean_1.fq.gz"
    read2 = tmp_path / "clean_2.fq.gz"
    output_dir = tmp_path / "spades"

    cmd = build_spades_command(
        spades_bin="spades.py",
        read1=read1,
        read2=read2,
        output_dir=output_dir,
        threads=32,
    )

    assert cmd == [
        "spades.py",
        "-1",
        str(read1),
        "-2",
        str(read2),
        "-o",
        str(output_dir),
        "--threads",
        "32",
    ]


def test_build_prodigal_command_includes_required_flags_and_paths_in_order(tmp_path):
    contigs_fa = tmp_path / "contigs.fasta"
    proteins_faa = tmp_path / "proteins.faa"
    genes_fna = tmp_path / "genes.fna"

    cmd = build_prodigal_command(
        prodigal_bin="prodigal",
        contigs_fa=contigs_fa,
        proteins_faa=proteins_faa,
        genes_fna=genes_fna,
    )

    assert cmd == [
        "prodigal",
        "-i",
        str(contigs_fa),
        "-a",
        str(proteins_faa),
        "-d",
        str(genes_fna),
        "-p",
        "meta",
    ]


def test_run_fastp_stage_builds_expected_command_and_returns_paths(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        assert check is True
        calls.append(cmd)

    monkeypatch.setattr(upstream_steps.subprocess, "run", fake_run)

    stage_dir = tmp_path / "fastp_stage"
    read1 = tmp_path / "raw_1.fq.gz"
    read2 = tmp_path / "raw_2.fq.gz"

    result = run_fastp_stage(read1=read1, read2=read2, stage_dir=stage_dir, fastp_bin="fastp")

    out_read1 = stage_dir / "clean_R1.fastq.gz"
    out_read2 = stage_dir / "clean_R2.fastq.gz"
    assert calls == [
        [
            "fastp",
            "-i",
            str(read1),
            "-I",
            str(read2),
            "-o",
            str(out_read1),
            "-O",
            str(out_read2),
            "--html",
            str(stage_dir / "fastp.html"),
            "--json",
            str(stage_dir / "fastp.json"),
        ]
    ]
    assert stage_dir.is_dir()
    assert result == {"read1": out_read1, "read2": out_read2}


def test_run_spades_stage_builds_expected_command_and_returns_paths(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        assert check is True
        calls.append(cmd)

    monkeypatch.setattr(upstream_steps.subprocess, "run", fake_run)

    stage_dir = tmp_path / "spades_stage"
    read1 = tmp_path / "clean_1.fq.gz"
    read2 = tmp_path / "clean_2.fq.gz"

    result = run_spades_stage(
        read1=read1,
        read2=read2,
        stage_dir=stage_dir,
        spades_bin="spades.py",
        threads=16,
    )

    assert calls == [
        [
            "spades.py",
            "-1",
            str(read1),
            "-2",
            str(read2),
            "-o",
            str(stage_dir),
            "--threads",
            "16",
        ]
    ]
    assert stage_dir.is_dir()
    assert result == {"contigs_fa": stage_dir / "contigs.fasta"}


def test_run_prodigal_stage_builds_expected_command_and_returns_paths(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool) -> None:
        assert check is True
        calls.append(cmd)

    monkeypatch.setattr(upstream_steps.subprocess, "run", fake_run)

    stage_dir = tmp_path / "prodigal_stage"
    contigs_fa = tmp_path / "contigs.fasta"

    result = run_prodigal_stage(
        contigs_fa=contigs_fa,
        stage_dir=stage_dir,
        prodigal_bin="prodigal",
    )

    proteins_faa = stage_dir / "proteins.faa"
    genes_fna = stage_dir / "genes.fna"
    assert calls == [
        [
            "prodigal",
            "-i",
            str(contigs_fa),
            "-a",
            str(proteins_faa),
            "-d",
            str(genes_fna),
            "-p",
            "meta",
        ]
    ]
    assert stage_dir.is_dir()
    assert result == {"proteins_faa": proteins_faa, "genes_fna": genes_fna}

