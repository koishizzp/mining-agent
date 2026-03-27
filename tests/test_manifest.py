import json

from thermo_mining.io_utils import read_fasta, write_done_json
from thermo_mining.manifest import load_sample_manifest
from thermo_mining.models import DoneRecord


def test_load_sample_manifest_reads_tsv(tmp_path):
    manifest_path = tmp_path / "samples.tsv"
    manifest_path.write_text(
        "sample_id\tprotein_faa\tmetadata_json\n"
        "S01\tinputs/S01.faa\t{\"temperature\":\"75C\"}\n",
        encoding="utf-8",
    )

    rows = load_sample_manifest(manifest_path)

    assert rows[0].sample_id == "S01"
    assert rows[0].protein_faa == "inputs/S01.faa"


def test_write_done_json_persists_counts(tmp_path):
    done_path = tmp_path / "DONE.json"
    record = DoneRecord(
        stage_name="01_prefilter",
        input_hash="abc123",
        parameters={"min_length": 80},
        software_version="0.1.0",
        runtime_seconds=1.25,
        retain_count=10,
        reject_count=2,
    )

    write_done_json(done_path, record)
    saved = json.loads(done_path.read_text(encoding="utf-8"))

    assert saved["stage_name"] == "01_prefilter"
    assert saved["retain_count"] == 10


def test_read_fasta_reads_ids_and_sequences(tmp_path):
    fasta_path = tmp_path / "input.faa"
    fasta_path.write_text(">p1 sample=S01\nMSTNPKPQRK\n>p2\nAAAAA\n", encoding="utf-8")

    records = read_fasta(fasta_path)

    assert records[0].protein_id == "p1"
    assert records[0].sequence == "MSTNPKPQRK"
    assert records[1].protein_id == "p2"
