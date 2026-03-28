from thermo_mining.control_plane.upstream_steps import (
    build_fastp_command,
    build_prodigal_command,
    build_spades_command,
)


def test_build_fastp_command_includes_input_and_output_paths(tmp_path):
    cmd = build_fastp_command(
        fastp_bin="fastp",
        read1=tmp_path / "sample_1.fq.gz",
        read2=tmp_path / "sample_2.fq.gz",
        out_read1=tmp_path / "clean_1.fq.gz",
        out_read2=tmp_path / "clean_2.fq.gz",
        html_report=tmp_path / "fastp.html",
        json_report=tmp_path / "fastp.json",
    )

    assert cmd[:2] == ["fastp", "-i"]
    assert str(tmp_path / "clean_1.fq.gz") in cmd


def test_build_spades_and_prodigal_commands_use_expected_flags(tmp_path):
    spades_cmd = build_spades_command(
        spades_bin="spades.py",
        read1=tmp_path / "clean_1.fq.gz",
        read2=tmp_path / "clean_2.fq.gz",
        output_dir=tmp_path / "spades",
        threads=32,
    )
    prodigal_cmd = build_prodigal_command(
        prodigal_bin="prodigal",
        contigs_fa=tmp_path / "contigs.fasta",
        proteins_faa=tmp_path / "proteins.faa",
        genes_fna=tmp_path / "genes.fna",
    )

    assert "--threads" in spades_cmd
    assert "-a" in prodigal_cmd
