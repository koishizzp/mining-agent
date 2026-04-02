import ntpath
import posixpath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

BundleType = Literal["paired_fastq", "contigs", "proteins", "seeded_proteins"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "stopped"]

REVIEW_EDITABLE_FIELDS = {
    "output_root",
    "resume_policy",
    "prefilter_min_length",
    "prefilter_max_length",
    "prefilter_max_single_residue_fraction",
    "thermo_top_fraction",
    "thermo_min_score",
    "protrek_top_k",
    "foldseek_topk",
    "foldseek_min_tmscore",
}


class InputBundle(BaseModel):
    bundle_type: BundleType
    sample_id: str
    input_paths: list[str]
    seed_paths: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_root: str

    @field_validator("input_paths", "seed_paths")
    @classmethod
    def validate_absolute_paths(cls, value: list[str]) -> list[str]:
        for item in value:
            if not (posixpath.isabs(item) or ntpath.isabs(item)):
                raise ValueError("input paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_seeded_contract(self) -> "InputBundle":
        if self.bundle_type == "seeded_proteins":
            if len(self.input_paths) != 1 or len(self.seed_paths) != 1:
                raise ValueError("seeded_proteins requires exactly one input path and one seed path")
        elif self.seed_paths:
            raise ValueError("seed paths are only valid for seeded_proteins bundles")
        return self


class ExecutionPlan(BaseModel):
    bundle_type: BundleType
    input_items: list[InputBundle]
    stage_order: list[str]
    parameter_overrides: dict[str, Any]
    output_root: str
    resume_policy: Literal["never", "if_possible"]
    requires_confirmation: bool = True
    explanation: str


class PathEntry(BaseModel):
    path: str
    name: str
    kind: Literal["file", "dir"]
    size: int
    mtime: float
    is_symlink: bool = False


class FastqPairCandidate(BaseModel):
    sample_id: str
    read1: str
    read2: str
    confidence: float
    needs_manual_confirmation: bool = False


class StageState(BaseModel):
    stage_name: str
    status: RunStatus
    input_hash: str = ""
    parameter_digest: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error_summary: str | None = None


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    created_at: str
    confirmed_at: str | None = None
    tmux_session: str | None = None
    run_dir: str


class ArtifactEntry(BaseModel):
    kind: str
    path: str
    label: str
    size: int
    updated_at: float
