import csv
import hashlib
import json
from pathlib import Path

from .models import DoneRecord, ProteinRecord


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_fasta(path: str | Path) -> list[ProteinRecord]:
    records: list[ProteinRecord] = []
    header: str | None = None
    chunks: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    protein_id = header.split()[0]
                    records.append(ProteinRecord(protein_id=protein_id, sequence="".join(chunks), header=header))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
    if header is not None:
        protein_id = header.split()[0]
        records.append(ProteinRecord(protein_id=protein_id, sequence="".join(chunks), header=header))
    return records


def write_fasta(path: str | Path, records: list[ProteinRecord]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(f">{record.header}\n{record.sequence}\n")


def write_scores_tsv(path: str | Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_done_json(path: str | Path, record: DoneRecord) -> None:
    Path(path).write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
