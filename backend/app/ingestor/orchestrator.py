# app/ingestor/orchestrator.py

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.sample import IngestRequest
from app.ingestor.taxpasta_reader import read_taxpasta
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.pipeline_info_reader import read_pipeline_info


async def _upsert_subject(db: AsyncIOMotorDatabase, subject_id: str) -> ObjectId:
    result = await db["subjects"].find_one({"subject_id": subject_id})
    if result:
        return result["_id"]
    insert = await db["subjects"].insert_one({
        "subject_id": subject_id,
        "created_at": datetime.now(timezone.utc),
    })
    return insert.inserted_id


async def _store_krona(
    db: AsyncIOMotorDatabase,
    run_id: ObjectId,
    krona_path: str,
) -> None:
    """
    Read Krona HTML from disk at ingest time and store in MongoDB.
    Linked to the run, not individual samples.
    Filesystem is only accessed here — never at query time.
    """
    path = Path(krona_path)
    if not path.exists():
        raise FileNotFoundError(f"Krona file not found: {krona_path}")
    html = path.read_text(encoding="utf-8")
    await db["krona_files"].find_one_and_replace(
        {"run_id": run_id},
        {
            "run_id":    run_id,
            "html":      html,
            "stored_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )


async def _load_superkingdom_map(
    db: AsyncIOMotorDatabase,
    taxonomy_name: Optional[str],
) -> Optional[dict]:
    """
    Load taxon_id -> superkingdom mapping from the taxonomy_nodes collection.
    Returns None if no taxonomy_name is provided.
    Raises ValueError if the named taxonomy has not been loaded yet.
    """
    if not taxonomy_name:
        return None

    tax = await db["taxonomy_databases"].find_one({"name": taxonomy_name})
    if not tax:
        raise ValueError(
            f"Taxonomy '{taxonomy_name}' not found. "
            f"Load it first with: python taxonomy.py --name {taxonomy_name} ..."
        )

    taxonomy_db_id = tax["_id"]
    cursor = db["taxonomy_nodes"].find(
        {"taxonomy_db_id": taxonomy_db_id},
        {"taxon_id": 1, "superkingdom": 1, "_id": 0},
    )
    nodes = await cursor.to_list(length=None)
    return {n["taxon_id"]: n["superkingdom"] for n in nodes}


async def ingest_run(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    # Load superkingdom map once for the entire run
    superkingdom_map = await _load_superkingdom_map(db, request.taxonomy_db)

    # Read pipeline outputs once — shared across all samples in the run
    pipeline_info = read_pipeline_info(request.pipeline_info_path)
    qc_data       = read_multiqc(request.multiqc_path)

    has_krona = bool(request.krona_path)

    run_doc = {
        "run_id":      request.run_id,
        "ingested_at": now,
        "sample_ids":  [],
        "taxonomy_db": request.taxonomy_db,
        "has_krona":   has_krona,
    }
    run_result    = await db["runs"].insert_one(run_doc)
    run_object_id = run_result.inserted_id

    # Store Krona HTML in DB if provided — once per run
    if request.krona_path:
        await _store_krona(db, run_object_id, request.krona_path)

    sample_ids = []

    for s in request.samples:
        # Resolve subject — null for controls
        subject_object_id = None
        if s.subject_id:
            subject_object_id = await _upsert_subject(db, s.subject_id)

        # Read this sample's profile from the shared taxpasta file
        profile = read_taxpasta(
            request.taxpasta_path,
            s.taxpasta_column,
            superkingdom_map=superkingdom_map,
        )

        # Extract QC stats for this sample from the shared multiqc data
        sample_qc = extract_sample_qc(qc_data, s.taxpasta_column)

        sample_doc = {
            "run_id":              run_object_id,
            "subject_id":          subject_object_id,
            "sample_type":         s.sample_type,
            "material":            s.material,
            "order_date":          s.order_date.isoformat() if s.order_date else None,
            "sample":              {"sample_id": s.sample_id},
            "library_preparation": s.library_preparation.model_dump() if s.library_preparation else None,
            "sequencing":          s.sequencing.model_dump() if s.sequencing else None,
            "taxprofiler": {
                **sample_qc,
                "pipeline_info": pipeline_info,
            },
            "profiles": [
                {
                    "classifier":    "kraken2",
                    "classifier_db": request.taxonomy_db,
                    "profile":       profile,
                }
            ],
            "has_krona":   has_krona,
            "review": {
                "reviewed":    False,
                "reviewed_by": None,
                "reviewed_at": None,
                "notes":       None,
            },
            "ingested_at": now,
        }

        sample_result = await db["samples"].insert_one(sample_doc)
        sample_ids.append(sample_result.inserted_id)

    await db["runs"].update_one(
        {"_id": run_object_id},
        {"$set": {"sample_ids": sample_ids}},
    )

    return {
        "run_id":           request.run_id,
        "run_object_id":    str(run_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids":       [str(sid) for sid in sample_ids],
    }


def extract_sample_qc(qc_data: dict, sample_name: str) -> dict:
    """
    Extract per-sample QC stats from the pre-loaded multiqc data dict.
    """
    stats = {}

    kraken2 = qc_data.get("kraken2", {}).get(sample_name)
    if kraken2:
        stats["kraken2"] = kraken2

    fastqc_fwd = qc_data.get("fastqc", {}).get(f"{sample_name}_1", {})
    fastqc_rev = qc_data.get("fastqc", {}).get(f"{sample_name}_2", {})
    if fastqc_fwd or fastqc_rev:
        stats["fastqc"] = {
            "mean_phred_score_forward": fastqc_fwd.get("avg_sequence_quality"),
            "mean_phred_score_reverse": fastqc_rev.get("avg_sequence_quality"),
            "total_num_reads":          fastqc_fwd.get("total_sequences"),
        }

    fastp = qc_data.get("fastp", {}).get(sample_name)
    if fastp:
        stats["fastp"] = fastp

    bowtie2 = qc_data.get("bowtie2", {}).get(sample_name)
    if bowtie2:
        stats["bowtie2"] = bowtie2

    return stats