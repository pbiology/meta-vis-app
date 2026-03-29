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
    sample_id: ObjectId,
    krona_path: str,
) -> None:
    """
    Read Krona HTML from disk at ingest time and store in MongoDB.
    The filesystem is only accessed here — never at query time.
    """
    path = Path(krona_path)
    if not path.exists():
        raise FileNotFoundError(f"Krona file not found: {krona_path}")
    html = path.read_text(encoding="utf-8")
    await db["krona_files"].find_one_and_replace(
        {"sample_id": sample_id},
        {
            "sample_id": sample_id,
            "html":       html,
            "stored_at":  datetime.now(timezone.utc),
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

    run_doc = {
        "run_id":      request.run_id,
        "ingested_at": now,
        "sample_ids":  [],
        "taxonomy_db": request.taxonomy_db,
    }
    run_result = await db["runs"].insert_one(run_doc)
    run_object_id = run_result.inserted_id

    sample_ids = []

    for s in request.samples:
        subject_object_id = await _upsert_subject(db, s.subject_id)

        profile       = read_taxpasta(s.taxpasta_path, s.taxpasta_column, superkingdom_map=superkingdom_map)
        qc            = read_multiqc(s.multiqc_path, s.taxpasta_column)
        pipeline_info = read_pipeline_info(s.pipeline_info_path)

        sample_doc = {
            "run_id":              run_object_id,
            "subject_id":          subject_object_id,
            "sample_type":         s.sample_type,
            "order_date":          s.order_date.isoformat() if s.order_date else None,
            "sample":              s.sample.model_dump(),
            "library_preparation": s.library_preparation.model_dump() if s.library_preparation else None,
            "sequencing":          s.sequencing.model_dump() if s.sequencing else None,
            "taxprofiler": {
                **qc,
                "pipeline_info": pipeline_info,
            },
            "profiles": [
                {
                    "classifier":    s.classifier,
                    "classifier_db": s.classifier_db,
                    "profile":       profile,
                }
            ],
            "has_krona":  bool(s.krona_path),  # lightweight flag for the frontend
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

        # Store Krona HTML in DB if path was provided
        if s.krona_path:
            await _store_krona(db, sample_result.inserted_id, s.krona_path)

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