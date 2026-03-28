from thermo_mining.control_plane.fastq_pairing import detect_fastq_pairs, scan_input_bundles


def test_detect_fastq_pairs_matches_common_r1_r2_patterns(tmp_path):
    read1 = tmp_path / "sample_R1.fastq.gz"
    read2 = tmp_path / "sample_R2.fastq.gz"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    pairs = detect_fastq_pairs([read1, read2])

    assert pairs[0].sample_id == "sample"
    assert pairs[0].read1.endswith("sample_R1.fastq.gz")
    assert pairs[0].read2.endswith("sample_R2.fastq.gz")


def test_scan_input_bundles_detects_proteins_and_contigs(tmp_path):
    proteins = tmp_path / "S01.faa"
    contigs = tmp_path / "S02_contigs.fa"
    proteins.write_text(">p1\nAAAA\n", encoding="utf-8")
    contigs.write_text(">c1\nATGC\n", encoding="utf-8")

    bundles = scan_input_bundles(tmp_path, output_root=tmp_path / "runs")

    assert {bundle.bundle_type for bundle in bundles} == {"proteins", "contigs"}
