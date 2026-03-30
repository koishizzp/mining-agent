from .schemas import BundleType

STAGE_ORDERS: dict[BundleType, list[str]] = {
    "paired_fastq": [
        "fastp",
        "spades",
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
    "contigs": [
        "prodigal",
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
    "proteins": [
        "prefilter",
        "mmseqs_cluster",
        "temstapro_screen",
        "protrek_recall",
        "foldseek_confirm",
        "rerank_report",
    ],
}


def build_stage_order(bundle_type: BundleType) -> list[str]:
    return STAGE_ORDERS[bundle_type].copy()
