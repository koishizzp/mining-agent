import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch


def read_fasta(path: str | Path) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    seqs: list[str] = []
    header = None
    chunks: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    ids.append(header.split()[0])
                    seqs.append("".join(chunks))
                header = line[1:]
                chunks = []
            else:
                chunks.append(line)
    if header is not None:
        ids.append(header.split()[0])
        seqs.append("".join(chunks))
    return ids, seqs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--input-faa", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    sys.path.insert(0, args.repo_root)
    from model.ProTrek.protrek_trimodal_model import ProTrekTrimodalModel

    config = {
        "protein_config": str(Path(args.weights_dir) / "esm2_t33_650M_UR50D"),
        "text_config": str(Path(args.weights_dir) / "BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext"),
        "structure_config": str(Path(args.weights_dir) / "foldseek_t30_150M"),
        "from_checkpoint": str(Path(args.weights_dir) / "ProTrek_650M.pt"),
    }
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ProTrekTrimodalModel(**config).eval().to(device)

    protein_ids, sequences = read_fasta(args.input_faa)
    embeddings: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(sequences), args.batch_size):
            batch = sequences[start : start + args.batch_size]
            batch_embeddings = model.get_protein_repr(batch).detach().cpu().numpy()
            embeddings.append(batch_embeddings)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "sequence_embeddings.npy", np.concatenate(embeddings, axis=0))
    with (output_dir / "metadata.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["protein_id"], delimiter="\t")
        writer.writeheader()
        for protein_id in protein_ids:
            writer.writerow({"protein_id": protein_id})


if __name__ == "__main__":
    main()
