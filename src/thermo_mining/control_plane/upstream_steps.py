import subprocess
from pathlib import Path


def build_fastp_command(
    fastp_bin: str,
    read1: str | Path,
    read2: str | Path,
    out_read1: str | Path,
    out_read2: str | Path,
    html_report: str | Path,
    json_report: str | Path,
) -> list[str]:
    return [
        fastp_bin,
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


def build_spades_command(
    spades_bin: str,
    read1: str | Path,
    read2: str | Path,
    output_dir: str | Path,
    threads: int,
) -> list[str]:
    return [
        spades_bin,
        "-1",
        str(read1),
        "-2",
        str(read2),
        "-o",
        str(output_dir),
        "--threads",
        str(threads),
    ]


def build_prodigal_command(
    prodigal_bin: str,
    contigs_fa: str | Path,
    proteins_faa: str | Path,
    genes_fna: str | Path,
) -> list[str]:
    return [
        prodigal_bin,
        "-i",
        str(contigs_fa),
        "-a",
        str(proteins_faa),
        "-d",
        str(genes_fna),
        "-p",
        "meta",
    ]


def run_fastp_stage(
    read1: str | Path,
    read2: str | Path,
    stage_dir: str | Path,
    fastp_bin: str,
) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    out_read1 = stage_dir / "clean_R1.fastq.gz"
    out_read2 = stage_dir / "clean_R2.fastq.gz"
    cmd = build_fastp_command(
        fastp_bin=fastp_bin,
        read1=read1,
        read2=read2,
        out_read1=out_read1,
        out_read2=out_read2,
        html_report=stage_dir / "fastp.html",
        json_report=stage_dir / "fastp.json",
    )
    subprocess.run(cmd, check=True)
    return {"read1": out_read1, "read2": out_read2}


def run_spades_stage(
    read1: str | Path,
    read2: str | Path,
    stage_dir: str | Path,
    spades_bin: str,
    threads: int,
) -> dict[str, Path]:
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_spades_command(spades_bin, read1, read2, stage_dir, threads)
    subprocess.run(cmd, check=True)
    return {"contigs_fa": stage_dir / "contigs.fasta"}


def run_prodigal_stage(
    contigs_fa: str | Path,
    stage_dir: str | Path,
    prodigal_bin: str = "prodigal",
    software_version: str = "0.1.0",
) -> dict[str, Path]:
    _ = software_version
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    proteins_faa = stage_dir / "proteins.faa"
    genes_fna = stage_dir / "genes.fna"
    cmd = build_prodigal_command(prodigal_bin, contigs_fa, proteins_faa, genes_fna)
    subprocess.run(cmd, check=True)
    return {"proteins_faa": proteins_faa, "genes_fna": genes_fna}
