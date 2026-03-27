import csv
from pathlib import Path

from .models import SampleManifestRow


def load_sample_manifest(path: str | Path) -> list[SampleManifestRow]:
    rows: list[SampleManifestRow] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rows.append(
                SampleManifestRow(
                    sample_id=row["sample_id"],
                    protein_faa=row["protein_faa"],
                    metadata_json=row.get("metadata_json", ""),
                )
            )
    return rows
