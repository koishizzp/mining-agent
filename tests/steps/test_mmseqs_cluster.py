from thermo_mining.steps.mmseqs_cluster import build_easy_linclust_command, parse_cluster_membership


def test_build_easy_linclust_command_uses_expected_flags(tmp_path):
    cmd = build_easy_linclust_command(
        mmseqs_bin="mmseqs",
        input_faa=tmp_path / "filtered.faa",
        output_prefix=tmp_path / "cluster",
        tmp_dir=tmp_path / "tmp",
        min_seq_id=0.9,
        coverage=0.8,
        threads=64,
    )

    assert cmd[:2] == ["mmseqs", "easy-linclust"]
    assert "--min-seq-id" in cmd
    assert "-c" in cmd
    assert "--threads" in cmd


def test_parse_cluster_membership_reads_representative_pairs(tmp_path):
    cluster_tsv = tmp_path / "cluster_cluster.tsv"
    cluster_tsv.write_text("rep1\tmember1\nrep1\tmember2\nrep2\tmember3\n", encoding="utf-8")

    rows = parse_cluster_membership(cluster_tsv)

    assert rows == [
        {"cluster_rep": "rep1", "member_id": "member1"},
        {"cluster_rep": "rep1", "member_id": "member2"},
        {"cluster_rep": "rep2", "member_id": "member3"},
    ]
