from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SampleManifestRow:
    sample_id: str
    protein_faa: str
    metadata_json: str = ""


@dataclass(frozen=True)
class ProteinRecord:
    protein_id: str
    sequence: str
    header: str


@dataclass(frozen=True)
class DoneRecord:
    stage_name: str
    input_hash: str
    parameters: dict[str, Any]
    software_version: str
    runtime_seconds: float
    retain_count: int
    reject_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
