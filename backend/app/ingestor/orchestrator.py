# app/ingestor/orchestrator.py

from datetime import datetime, timezone
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


async def ingest_run(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    run_doc = {
        "run_id": request.run_id,
        "ingested_at": now,
        "sample_ids": [],
    }
    run_result = await db["runs"].insert_one(run_doc)
    run_object_id = run_result.inserted_id

    sample_ids = []

    for s in request.samples:
        subject_object_id = await _upsert_subject(db, s.subject_id)

        profile = read_taxpasta(s.taxpasta_path, s.taxpasta_column)
        qc = read_multiqc(s.multiqc_path, s.taxpasta_column)
        pipeline_info = read_pipeline_info(s.pipeline_info_path)

        sample_doc = {
            "run_id": run_object_id,
            "subject_id": subject_object_id,
            "sample_type": s.sample_type,
            "order_date": s.order_date.isoformat() if s.order_date else None,
            "sample": s.sample.model_dump(),
            "library_preparation": s.library_preparation.model_dump() if s.library_preparation else None,
            "sequencing": s.sequencing.model_dump() if s.sequencing else None,
            "taxprofiler": {
                **qc,
                "pipeline_info": pipeline_info,
            },
            "profiles": [
                {
                    "classifier": s.classifier,
                    "classifier_db": s.classifier_db,
                    "profile": profile,
                }
            ],
            "krona_path": s.krona_path,
            "review": {
                "reviewed": False,
                "reviewed_by": None,
                "reviewed_at": None,
                "notes": None,
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
        "run_id": request.run_id,
        "run_object_id": str(run_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids": [str(sid) for sid in sample_ids],
    }