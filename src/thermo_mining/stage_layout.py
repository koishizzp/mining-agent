from pathlib import Path


STAGE_DIR_SUFFIXES: dict[str, str] = {
    "fastp": "fastp",
    "spades": "spades",
    "prodigal": "prodigal",
    "prefilter": "prefilter",
    "mmseqs_cluster": "cluster",
    "seed_sequence_recall": "seed_sequence",
    "seed_structure_recall": "seed_structure",
    "seed_recall_merge": "seed_merge",
    "temstapro_screen": "temstapro",
    "protrek_recall": "protrek",
    "structure_predict": "structure",
    "foldseek_confirm": "foldseek",
    "rerank_report": "report",
}


def build_stage_dirs(run_root: str | Path, stage_order: list[str]) -> dict[str, Path]:
    run_root = Path(run_root)
    return {
        stage_name: run_root / f"{index:02d}_{STAGE_DIR_SUFFIXES[stage_name]}"
        for index, stage_name in enumerate(stage_order, start=1)
    }
