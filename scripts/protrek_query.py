import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch


def cosine_similarity(query: np.ndarray, index: np.ndarray) -> np.ndarray:
    query = query / np.linalg.norm(query, axis=1, keepdims=True)
    index = index / np.linalg.norm(index, axis=1, keepdims=True)
    return query @ index.T


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--weights-dir", required=True)
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--output-tsv", required=True)
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--query-text", action="append", dest="query_texts", required=True)
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

    with torch.no_grad():
        query_embeddings = model.get_text_repr(args.query_texts).detach().cpu().numpy()
    index_dir = Path(args.index_dir)
    index = np.load(index_dir / "sequence_embeddings.npy")
    metadata_rows = list(csv.DictReader((index_dir / "metadata.tsv").open("r", encoding="utf-8"), delimiter="\t"))
    sims = cosine_similarity(query_embeddings, index)

    with Path(args.output_tsv).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_text", "protein_id", "protrek_score", "rank"], delimiter="\t")
        writer.writeheader()
        for query_idx, query_text in enumerate(args.query_texts):
            top_indices = np.argsort(sims[query_idx])[::-1][: args.top_k]
            for rank, idx in enumerate(top_indices, start=1):
                writer.writerow(
                    {
                        "query_text": query_text,
                        "protein_id": metadata_rows[int(idx)]["protein_id"],
                        "protrek_score": round(float(sims[query_idx][int(idx)]), 6),
                        "rank": rank,
                    }
                )


if __name__ == "__main__":
    main()
