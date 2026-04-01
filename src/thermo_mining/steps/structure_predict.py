import json
import shutil
import subprocess
from pathlib import Path
from time import perf_counter

from ..io_utils import read_fasta, sha256_file, write_done_json, write_fasta
from ..models import DoneRecord, ProteinRecord


def _path_text(value: str | Path) -> str:
    if isinstance(value, Path):
        return str(value) if value.drive else value.as_posix()
    return str(value)


def build_colabfold_command(
    colabfold_batch_bin: str,
    data_dir: str | Path,
    query_faa: str | Path,
    output_dir: str | Path,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
) -> list[str]:
    return [
        colabfold_batch_bin,
        "--data",
        _path_text(data_dir),
        "--msa-mode",
        msa_mode,
        "--num-models",
        str(num_models),
        "--num-recycle",
        str(num_recycle),
        _path_text(query_faa),
        _path_text(output_dir),
    ]


def _select_output_pdb(raw_output_dir: Path, protein_id: str) -> Path:
    ranked = sorted(raw_output_dir.glob("*rank_001*.pdb"))
    if len(ranked) == 1:
        return ranked[0]
    if not ranked:
        all_pdbs = sorted(raw_output_dir.glob("*.pdb"))
        if len(all_pdbs) == 1:
            return all_pdbs[0]
    raise RuntimeError(f"unable to choose a unique PDB for {protein_id}")


def run_structure_predict_stage(
    input_faa: str | Path,
    stage_dir: str | Path,
    colabfold_batch_bin: str,
    colabfold_data_dir: str | Path,
    msa_mode: str,
    num_models: int,
    num_recycle: int,
    software_version: str,
    dry_run: bool = False,
) -> dict[str, object]:
    started = perf_counter()
    input_faa = Path(input_faa)
    stage_dir = Path(stage_dir)
    queries_dir = stage_dir / "queries"
    raw_dir = stage_dir / "raw"
    structures_dir = stage_dir / "structures"

    for path in (queries_dir, raw_dir, structures_dir):
        path.mkdir(parents=True, exist_ok=True)

    records = read_fasta(input_faa)
    commands: list[list[str]] = []
    manifest: list[dict[str, str]] = []

    for record in records:
        query_faa = queries_dir / f"{record.protein_id}.faa"
        protein_raw_dir = raw_dir / record.protein_id
        protein_raw_dir.mkdir(parents=True, exist_ok=True)
        write_fasta(query_faa, [ProteinRecord(record.protein_id, record.sequence, record.header)])

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

        if dry_run:
            continue

        subprocess.run(cmd, check=True)
        source_pdb = _select_output_pdb(protein_raw_dir, record.protein_id)
        normalized_pdb = structures_dir / f"{record.protein_id}.pdb"
        shutil.copy2(source_pdb, normalized_pdb)
        manifest.append(
            {
                "protein_id": record.protein_id,
                "pdb_path": str(normalized_pdb),
            }
        )

    if dry_run:
        return {"commands": commands}

    manifest_path = stage_dir / "structure_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_done_json(
        stage_dir / "DONE.json",
        DoneRecord(
            stage_name="05_structure_predict",
            input_hash=sha256_file(input_faa),
            parameters={"msa_mode": msa_mode, "num_models": num_models, "num_recycle": num_recycle},
            software_version=software_version,
            runtime_seconds=round(perf_counter() - started, 4),
            retain_count=len(manifest),
            reject_count=0,
        ),
    )
    return {"structure_manifest": manifest, "structure_manifest_json": manifest_path}
