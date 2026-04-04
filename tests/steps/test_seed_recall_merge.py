import json

from thermo_mining.steps.seed_recall_merge import run_seed_recall_merge_stage


def test_run_seed_recall_merge_stage_unions_hits_and_writes_seeded_targets(tmp_path):
    cluster_rep_faa = tmp_path / "cluster_rep_seq.fasta"
    cluster_rep_faa.write_text(">target1 desc\nAAAA\n>target2\nCCCC\n>target3\nGGGG\n", encoding="utf-8")
    sequence_hits_tsv = tmp_path / "sequence_hits.tsv"
    sequence_hits_tsv.write_text(
        "target_id\tseed_id\tsequence_score\n"
        "target1\tcas1\t0.91\n"
        "target2\tcas1\t0.72\n",
        encoding="utf-8",
    )
    structure_hits_tsv = tmp_path / "structure_hits.tsv"
    structure_hits_tsv.write_text(
        "target_id\tseed_id\tstructure_score\n"
        "target2\tcas2\t0.81\n"
        "target3\tcas1\t0.77\n",
        encoding="utf-8",
    )

    result = run_seed_recall_merge_stage(
        cluster_rep_faa=cluster_rep_faa,
        sequence_hits_tsv=sequence_hits_tsv,
        structure_hits_tsv=structure_hits_tsv,
        stage_dir=tmp_path / "05_seed_merge",
        software_version="test",
    )

    manifest_text = result["seed_manifest_tsv"].read_text(encoding="utf-8")
    assert "target1\tcas1\tsequence\t0.91\t0.0" in manifest_text
    assert "target2\tcas1;cas2\tboth\t0.72\t0.81" in manifest_text
    assert "target3\tcas1\tstructure\t0.0\t0.77" in manifest_text
    seeded_targets_text = result["seeded_targets_faa"].read_text(encoding="utf-8")
    assert ">target1 desc" in seeded_targets_text
    assert ">target3" in seeded_targets_text
    done = json.loads((tmp_path / "05_seed_merge" / "DONE.json").read_text(encoding="utf-8"))
    assert done["stage_name"] == "05_seed_recall_merge"
