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


def test_detect_fastq_pairs_supports_underscore_1_2_non_gz(tmp_path):
    read1 = tmp_path / "sample_1.fastq"
    read2 = tmp_path / "sample_2.fastq"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    pairs = detect_fastq_pairs([read1, read2])

    assert len(pairs) == 1
    assert pairs[0].sample_id == "sample"
    assert pairs[0].read1.endswith("sample_1.fastq")
    assert pairs[0].read2.endswith("sample_2.fastq")


def test_detect_fastq_pairs_supports_dot_1_2_fq_non_gz(tmp_path):
    read1 = tmp_path / "sample.1.fq"
    read2 = tmp_path / "sample.2.fq"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    pairs = detect_fastq_pairs([read1, read2])

    assert len(pairs) == 1
    assert pairs[0].sample_id == "sample"
    assert pairs[0].read1.endswith("sample.1.fq")
    assert pairs[0].read2.endswith("sample.2.fq")


def test_scan_input_bundles_detects_proteins_and_contigs(tmp_path):
    proteins = tmp_path / "S01.faa"
    contigs = tmp_path / "S02_contigs.fa"
    proteins.write_text(">p1\nAAAA\n", encoding="utf-8")
    contigs.write_text(">c1\nATGC\n", encoding="utf-8")

    bundles = scan_input_bundles(tmp_path, output_root=tmp_path / "runs")

    assert {bundle.bundle_type for bundle in bundles} == {"proteins", "contigs"}


def test_scan_input_bundles_normalizes_gzipped_sample_ids(tmp_path):
    proteins = tmp_path / "S01.faa.gz"
    contigs = tmp_path / "S02_contigs.fa.gz"
    proteins.write_text(">p1\nAAAA\n", encoding="utf-8")
    contigs.write_text(">c1\nATGC\n", encoding="utf-8")

    bundles = scan_input_bundles(tmp_path, output_root=tmp_path / "runs")
    by_type = {bundle.bundle_type: bundle for bundle in bundles}

    assert by_type["proteins"].sample_id == "S01"
    assert by_type["contigs"].sample_id == "S02_contigs"


def test_scan_input_bundles_creates_paired_fastq_bundle_from_underscore_pairs(tmp_path):
    read1 = tmp_path / "A01_1.fastq"
    read2 = tmp_path / "A01_2.fastq"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    bundles = scan_input_bundles(tmp_path, output_root=tmp_path / "runs")

    paired = [bundle for bundle in bundles if bundle.bundle_type == "paired_fastq"]
    assert len(paired) == 1
    assert paired[0].sample_id == "A01"
    assert paired[0].input_paths[0].endswith("A01_1.fastq")
    assert paired[0].input_paths[1].endswith("A01_2.fastq")


def test_detect_fastq_pairs_deduplicates_repeated_read1_entries(tmp_path):
    read1 = tmp_path / "dup_R1.fastq.gz"
    read2 = tmp_path / "dup_R2.fastq.gz"
    read1.write_text("x", encoding="utf-8")
    read2.write_text("y", encoding="utf-8")

    pairs = detect_fastq_pairs([read1, read2, read1])

    assert len(pairs) == 1
