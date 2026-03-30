import re
from pathlib import Path

from .schemas import FastqPairCandidate, InputBundle


READ1_PATTERNS = [
    (re.compile(r"^(?P<sample>.+)_R1(?P<ext>\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "{sample}_R2{ext}"),
    (re.compile(r"^(?P<sample>.+)_1(?P<ext>\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "{sample}_2{ext}"),
    (re.compile(r"^(?P<sample>.+)\.1(?P<ext>\.f(ast)?q(\.gz)?)$", re.IGNORECASE), "{sample}.2{ext}"),
]


def detect_fastq_pairs(paths: list[Path]) -> list[FastqPairCandidate]:
    index = {path.name: path for path in paths}
    pairs: list[FastqPairCandidate] = []
    seen: set[tuple[str, str, str]] = set()

    for path in paths:
        for pattern, partner_template in READ1_PATTERNS:
            match = pattern.match(path.name)
            if not match:
                continue
            sample_id = match.group("sample")
            ext = match.group("ext")
            partner_name = partner_template.format(sample=sample_id, ext=ext)
            partner = index.get(partner_name)
            if partner is None:
                continue

            read1 = str(path.resolve())
            read2 = str(partner.resolve())
            key = (sample_id, read1, read2)
            if key not in seen:
                seen.add(key)
                pairs.append(
                    FastqPairCandidate(
                        sample_id=sample_id,
                        read1=read1,
                        read2=read2,
                        confidence=1.0,
                        needs_manual_confirmation=False,
                    )
                )
            break
    return pairs


def _strip_suffixes(name: str, suffixes: tuple[str, ...]) -> str:
    lower_name = name.lower()
    for suffix in suffixes:
        if lower_name.endswith(suffix):
            return name[: -len(suffix)]
    return name


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
            sample_id = _strip_suffixes(path.name, (".faa.gz", ".faa"))
            bundles.append(
                InputBundle(
                    bundle_type="proteins",
                    sample_id=sample_id,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / sample_id),
                )
            )
        if suffixes.endswith((".fa", ".fasta", ".fa.gz", ".fasta.gz")):
            sample_id = _strip_suffixes(path.name, (".fasta.gz", ".fa.gz", ".fasta", ".fa"))
            if "contig" not in sample_id.lower():
                continue
            bundles.append(
                InputBundle(
                    bundle_type="contigs",
                    sample_id=sample_id,
                    input_paths=[str(path.resolve())],
                    metadata={},
                    output_root=str(output_root / sample_id),
                )
            )
    return bundles
