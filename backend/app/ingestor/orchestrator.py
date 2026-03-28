from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.ingestor.taxpasta_reader import read_taxpasta
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.models.sample import IngestRequest


async def ingest_run(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    run_doc = {
        "run_id": request.run_id,
        "ingested_at": datetime.utcnow(),
        "sample_ids": [],
    }
    run_result = await db.runs.insert_one(run_doc)
    run_object_id = run_result.inserted_id

    inserted_sample_ids = []

    for sample_request in request.samples:
        patient_id = await _upsert_patient(sample_request.patient_id, db)

        profile = read_taxpasta(
            sample_request.taxpasta_path,
            column=sample_request.taxpasta_column,
        )

        qc_stats = read_multiqc(
            sample_request.multiqc_path,
            taxpasta_column=sample_request.taxpasta_column,
        )

        pipeline_info = read_pipeline_info(sample_request.pipeline_info_path)

        sample_doc = {
            "run_id": run_object_id,
            "patient_id": patient_id,
            "sample_type": sample_request.sample_type,
            "sample": sample_request.sample.model_dump(),
            "library_preparation": (
                sample_request.library_preparation.model_dump()
                if sample_request.library_preparation else None
            ),
            "sequencing": (
                sample_request.sequencing.model_dump()
                if sample_request.sequencing else None
            ),
            "taxprofiler": {
                **qc_stats,
                "pipeline_info": pipeline_info,
            },
            "profiles": [
                {
                    "classifier": sample_request.classifier,
                    "classifier_db": sample_request.classifier_db,
                    "profile": profile,
                }
            ],
            "krona_path": sample_request.krona_path,
            "ingested_at": datetime.utcnow(),
        }

        sample_result = await db.samples.insert_one(sample_doc)
        inserted_sample_ids.append(sample_result.inserted_id)

    await db.runs.update_one(
        {"_id": run_object_id},
        {"$set": {"sample_ids": inserted_sample_ids}},
    )

    return {
        "run_id": request.run_id,
        "run_object_id": str(run_object_id),
        "samples_ingested": len(inserted_sample_ids),
        "sample_ids": [str(sid) for sid in inserted_sample_ids],
    }


async def _upsert_patient(patient_id: str, db: AsyncIOMotorDatabase) -> ObjectId:
    existing = await db.patients.find_one({"patient_id": patient_id})
    if existing:
        return existing["_id"]

    result = await db.patients.insert_one({
        "patient_id": patient_id,
        "created_at": datetime.utcnow(),
    })
    return result.inserted_id