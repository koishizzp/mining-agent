import csv
import hashlib
import shutil
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta, write_scores_tsv
from ..models import DoneRecord, ProteinRecord
from .foldseek_client import build_foldseek_easy_search_command
from .structure_predict import _select_output_pdb, build_colabfold_command


def _path_text(value: str | Path) -> str:
    if isinstance(value, Path):
        return str(value) if value.drive else value.as_posix()
    return str(value)


def _combined_input_hash(*paths: str | Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()


def build_foldseek_createdb_command(
    foldseek_bin: str,
    structures_dir: str | Path,
    database_prefix: str | Path,
) -> list[str]:
    return [
        foldseek_bin,
        "createdb",
        _path_text(structures_dir),
        _path_text(database_prefix),
    ]


def _predict_structure_manifest(
    input_faa: str | Path,
    query_root: Path,
    raw_root: Path,
    structures_root: Path,
    colabfold_batch_bin: str,
    colabfold_data_dir: str | Path,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
    dry_run: bool = False,
) -> tuple[list[dict[str, str]], list[list[str]]]:
    query_root.mkdir(parents=True, exist_ok=True)
    raw_root.mkdir(parents=True, exist_ok=True)
    structures_root.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, str]] = []
    commands: list[list[str]] = []
    for record in read_fasta(input_faa):
        query_faa = query_root / f"{record.protein_id}.faa"
        protein_raw_dir = raw_root / record.protein_id
        protein_raw_dir.mkdir(parents=True, exist_ok=True)
        write_fasta(query_faa, [ProteinRecord(record.protein_id, record.sequence, record.header)])

        normalized_pdb = structures_root / f"{record.protein_id}.pdb"
        cmd = build_colabfold_command(
            colabfold_batch_bin=colabfold_batch_bin,
            data_dir=colabfold_data_dir,
            query_faa=query_faa,
            output_dir=protein_raw_dir,
            msa_mode=msa_mode,
            num_models=num_models,
            num_recycle=num_recycle,
        )
        commands.append(cmd)
        if not dry_run:
            subprocess.run(cmd, check=True)
            source_pdb = _select_output_pdb(protein_raw_dir, record.protein_id)
            shutil.copy2(source_pdb, normalized_pdb)

        manifest.append({"protein_id": record.protein_id, "pdb_path": str(normalized_pdb)})

    return manifest, commands


def run_seed_structure_recall_stage(
    seed_faa: str | Path,
    cluster_rep_faa: str | Path,
    stage_dir: str | Path,
    colabfold_batch_bin: str,
    colabfold_data_dir: str | Path,
    foldseek_bin: str,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
    min_tmscore: float,
    topk_per_seed: int,
    max_targets: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, Path] | dict[str, list[list[str]]]:
    started = perf_counter()
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)

    target_records = read_fasta(cluster_rep_faa)
    if len(target_records) > max_targets:
        raise RuntimeError(f"seed_structure_max_targets exceeded: {len(target_records)} > {max_targets}")

    seed_query_root = stage_dir / "seed_queries"
    seed_raw_root = stage_dir / "seed_raw"
    seed_structures_root = stage_dir / "seed_structures"
    target_query_root = stage_dir / "target_queries"
    target_raw_root = stage_dir / "target_raw"
    target_structures_root = stage_dir / "target_structures"
    target_db_prefix = stage_dir / "target_db" / "db"
    raw_hits_root = stage_dir / "raw"
    tmp_root = stage_dir / "tmp"

    raw_hits_root.mkdir(parents=True, exist_ok=True)
    tmp_root.mkdir(parents=True, exist_ok=True)
    target_db_prefix.parent.mkdir(parents=True, exist_ok=True)

    seed_manifest, seed_prediction_commands = _predict_structure_manifest(
        input_faa=seed_faa,
        query_root=seed_query_root,
        raw_root=seed_raw_root,
        structures_root=seed_structures_root,
        colabfold_batch_bin=colabfold_batch_bin,
        colabfold_data_dir=colabfold_data_dir,
        msa_mode=msa_mode,
        num_models=num_models,
        num_recycle=num_recycle,
        dry_run=dry_run,
    )
    _, target_prediction_commands = _predict_structure_manifest(
        input_faa=cluster_rep_faa,
        query_root=target_query_root,
        raw_root=target_raw_root,
        structures_root=target_structures_root,
        colabfold_batch_bin=colabfold_batch_bin,
        colabfold_data_dir=colabfold_data_dir,
        msa_mode=msa_mode,
        num_models=num_models,
        num_recycle=num_recycle,
        dry_run=dry_run,
    )

    commands = [*seed_prediction_commands, *target_prediction_commands]
    createdb_cmd = build_foldseek_createdb_command(
        foldseek_bin=foldseek_bin,
        structures_dir=target_structures_root,
        database_prefix=target_db_prefix,
    )
    commands.append(createdb_cmd)
    if not dry_run:
        subprocess.run(createdb_cmd, check=True)

    pair_scores: dict[tuple[str, str], float] = {}
    rejected_count = 0
    for seed_entry in seed_manifest:
        output_tsv = raw_hits_root / f"{seed_entry['protein_id']}.tsv"
        tmp_dir = tmp_root / seed_entry["protein_id"]
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cmd = build_foldseek_easy_search_command(
            foldseek_bin=foldseek_bin,
            query_pdb=seed_entry["pdb_path"],
            database_path=target_db_prefix,
            output_tsv=output_tsv,
            tmp_dir=tmp_dir,
            topk=topk_per_seed,
        )
        commands.append(cmd)
        if dry_run:
            continue

        subprocess.run(cmd, check=True)
        with output_tsv.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for row in reader:
                if not row:
                    continue
                target_id = Path(row[1]).stem
                score = float(row[2])
                if score < min_tmscore:
                    rejected_count += 1
                    continue
                pair_key = (target_id, seed_entry["protein_id"])
                pair_scores[pair_key] = max(pair_scores.get(pair_key, 0.0), score)

    if dry_run:
        return {"commands": commands}

    rows = [
        {
            "target_id": target_id,
            "seed_id": seed_id,
            "structure_score": round(score, 4),
        }
        for (target_id, seed_id), score in sorted(pair_scores.items())
    ]
    structure_hits_tsv = stage_dir / "structure_hits.tsv"
    write_scores_tsv(structure_hits_tsv, rows, ["target_id", "seed_id", "structure_score"])
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="04_seed_structure_recall",
            input_hash=_combined_input_hash(seed_faa, cluster_rep_faa),
            parameters={
                "min_tmscore": min_tmscore,
                "topk_per_seed": topk_per_seed,
                "max_targets": max_targets,
                "msa_mode": msa_mode,
                "num_models": num_models,
                "num_recycle": num_recycle,
            },
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(rows),
            reject_count=rejected_count,
        ),
    )
    return {"structure_hits_tsv": structure_hits_tsv}
