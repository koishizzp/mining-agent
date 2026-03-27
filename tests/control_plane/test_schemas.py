import pytest
from pydantic import ValidationError

from thermo_mining.control_plane.schemas import (
    REVIEW_EDITABLE_FIELDS,
    ExecutionPlan,
    InputBundle,
)
from thermo_mining.control_plane.stage_graph import build_stage_order


def test_input_bundle_requires_absolute_paths():
    with pytest.raises(ValidationError):
        InputBundle(
            bundle_type="proteins",
            sample_id="S01",
            input_paths=["inputs/S01.faa"],
            metadata={},
            output_root="/runs/S01",
        )


def test_execution_plan_defaults_to_confirmation():
    bundle = InputBundle(
        bundle_type="proteins",
        sample_id="S01",
        input_paths=["/mnt/disk2/S01.faa"],
        metadata={},
        output_root="/runs/S01",
    )

    plan = ExecutionPlan(
        bundle_type="proteins",
        input_items=[bundle],
        stage_order=build_stage_order("proteins"),
        parameter_overrides={},
        output_root="/runs/S01",
        resume_policy="if_possible",
        explanation="Run the default proteins flow",
    )

    assert plan.requires_confirmation is True
    assert "output_root" in REVIEW_EDITABLE_FIELDS


def test_build_stage_order_for_all_bundle_types():
    assert build_stage_order("paired_fastq") == [
        "fastp",
        "spades",
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ]
    assert build_stage_order("contigs")[0] == "prodigal"
    assert build_stage_order("proteins")[0] == "prefilter"
