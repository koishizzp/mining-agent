from thermo_mining.io_utils import read_fasta
from thermo_mining.steps.prefilter import prefilter_records, run_prefilter


def test_prefilter_keeps_valid_sequences_and_rejects_noise():
    input_records = [
        ("keep_1", "MSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTATPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF"),
        ("too_short", "MSTN"),
        ("low_complexity", "A" * 100),
    ]

    kept, scores = prefilter_records(input_records, min_length=80, max_length=1200, max_single_residue_fraction=0.7)

    assert [row[0] for row in kept] == ["keep_1"]
    assert {row["protein_id"]: row["keep"] for row in scores} == {
        "keep_1": "yes",
        "too_short": "no",
        "low_complexity": "no",
    }


def test_run_prefilter_writes_outputs(tmp_path):
    input_faa = tmp_path / "input.faa"
    input_faa.write_text(
        ">keep_1\nMSTNPKPQRKTKRNTNRRPQDVKFPGGGQIVGGVLTATPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRF\n"
        ">low_complexity\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
        encoding="utf-8",
    )
    stage_dir = tmp_path / "01_prefilter"

    result = run_prefilter(
        input_faa=input_faa,
        stage_dir=stage_dir,
        min_length=80,
        max_length=1200,
        max_single_residue_fraction=0.7,
        software_version="0.1.0",
    )

    kept = read_fasta(result["filtered_faa"])
    assert [record.protein_id for record in kept] == ["keep_1"]
    assert (stage_dir / "scores.tsv").exists()
    assert (stage_dir / "DONE.json").exists()
