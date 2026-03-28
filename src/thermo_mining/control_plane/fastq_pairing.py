import re
from pathlib import Path

from .schemas import FastqPairCandidate, InputBundle


PAIR_PATTERNS = [
    (re.compile(r"(.+)_R1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "_R2"),
    (re.compile(r"(.+)_1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "_2"),
    (re.compile(r"(.+)\.1(\.f(ast)?q(\.gz)?)$", re.IGNORECASE), ".2"),
]


def detect_fastq_pairs(paths: list[Path]) -> list[FastqPairCandidate]:
    index = {path.name: path for path in paths}
    pairs: list[FastqPairCandidate] = []
    for path in paths:
        for pattern, partner_marker in PAIR_PATTERNS:
            match = pattern.match(path.name)
            if not match:
                continue
            sample_id = match.group(1)
            partner_name = path.name.replace(partner_marker.replace("2", "1"), partner_marker)
            partner = index.get(partner_name)
            if partner is None:
                continue
            if "_R1" in path.name or path.name.endswith("_1.fastq.gz") or ".1.fastq.gz" in path.name:
                pairs.append(
                    FastqPairCandidate(
                        sample_id=sample_id,
                        read1=str(path.resolve()),
                        read2=str(partner.resolve()),
                        confidence=1.0,
                        needs_manual_confirmation=False,
                    )
                )
            break
    unique = {(pair.sample_id, pair.read1, pair.read2): pair for pair in pairs}
    return list(unique.values())


def scan_input_bundles(root: str | Path, output_root: str | Path) -> list[InputBundle]:
    root = Path(root).resolve()
    output_root = Path(output_root).resolve()
    paths = [path for path in root.iterdir() if path.is_file()]
    bundles: list[InputBundle] = []

    for pair in detect_fastq_pairs(paths):
        bundles.append(
            InputBundle(
                bundle_type="paired_fastq",
                sample_id=pair.sample_id,
                input_paths=[pair.read1, pair.read2],
                metadata={},
                output_root=str(output_root / pair.sample_id),
            )
        )

    for path in paths:
        suffixes = "".join(path.suffixes).lower()
        if suffixes.endswith((".faa", ".faa.gz")):
            bundles.append(
                InputBundle(
                    bundle_type="proteins",
                    sample_id=path.stem,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / path.stem),
                )
            )
        if suffixes.endswith((".fa", ".fasta", ".fa.gz", ".fasta.gz")) and "contig" in path.stem.lower():
            bundles.append(
                InputBundle(
                    bundle_type="contigs",
                    sample_id=path.stem,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / path.stem),
                )
            )
    return bundles
