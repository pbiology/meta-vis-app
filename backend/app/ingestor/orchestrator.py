# app/ingestor/orchestrator.py

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Any
from pymongo import ReturnDocument, UpdateOne

from app.database import get_client
from app.models.sample import IngestRequest, TranaIngestRequest
from app.ingestor.taxpasta_reader import load_taxpasta, extract_sample_profile
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.ingestor.metaval_reader import read_metaval
from app.ingestor.emu_reader import read_emu_abundance
from app.ingestor.nanoplot_reader import read_nanostats
from app.ingestor.models import (
    MetavalOutput,
    MetavalResult,
    MultiQCRaw,
    NanoPlotStats,
    PipelineInfoOutput,
    TaxonEntry,
)


# ---------------------------------------------------------------------------
# Prepared-ingest dataclasses
#
# Issue #10: ingest_case is split into three phases — prepare (pure; no DB or
# blob writes), commit (all Mongo writes inside a single transaction), and
# upload-blobs (after the transaction commits). These dataclasses carry the
# fully-materialised writes from prepare to commit/upload so that a failure
# in any one phase cannot leave Mongo in an inconsistent state.
# ---------------------------------------------------------------------------


@dataclass
class _BlobUpload:
    key: str
    content: str


@dataclass
class _MetavalPrepared:
    doc: dict  # ready-to-insert metaval_results document
    blob_uploads: list[_BlobUpload]


@dataclass
class _PreparedIngest:
    case_doc: dict
    # sample_docs each carry a pre-generated _id and (possibly placeholder)
    # subject_id that is resolved to a real ObjectId inside the transaction.
    sample_docs: list[dict]
    # subject_id string -> list of sample_doc indices that reference it
    subject_refs: dict[str, list[int]] = field(default_factory=dict)
    taxa_upsert_ops: list[UpdateOne] = field(default_factory=list)
    metaval_prepared: list[_MetavalPrepared] = field(default_factory=list)
    metaval_pipeline_info: dict | None = None
    krona_uploads: list[_BlobUpload] = field(default_factory=list)
    multiqc_upload: _BlobUpload | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_text(path: str, label: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return p.read_text(encoding="utf-8")


def _compute_outbreak_taxa(profiles: list) -> list:
    """Extract taxa from profiles that match any enabled outbreak config."""
    from app.config import settings

    if not settings.outbreak_configs:
        return []

    outbreak_taxa = []
    seen_taxon_ids: set = set()

    for profile in profiles:
        classifier_name = profile.get("classifier")

        for entry in profile.get("profile", []):
            taxon_id = entry.get("taxon_id")

            if taxon_id in seen_taxon_ids:
                continue

            superkingdom = entry.get("superkingdom")
            rank = entry.get("rank")
            abundance = entry.get("abundance", 0)

            for config in settings.outbreak_configs:
                if (
                    superkingdom in config["superkingdoms"]
                    and rank in config["min_rank"]
                    and abundance > config["min_abundance"]
                ):
                    outbreak_taxa.append(
                        {
                            "taxon_id": taxon_id,
                            "name": entry.get("name"),
                            "superkingdom": superkingdom,
                            "rank": rank,
                            "abundance": abundance,
                            "classifier": classifier_name,
                        }
                    )
                    seen_taxon_ids.add(taxon_id)
                    break

    return outbreak_taxa


def _build_taxa_upsert_ops(all_profiles: list) -> list[UpdateOne]:
    """
    Build $setOnInsert upsert operations for every taxon_id seen in profiles.

    Ensures every taxon_id seen in a sample has at least a skeleton record in
    the `taxa` collection. Never overwrites existing taxonomy data.
    """
    seen: dict[int, dict[str, Any]] = {}
    for p in all_profiles:
        for entry in p.get("profile", []):
            taxon_id = entry.get("taxon_id")
            if taxon_id is None or taxon_id in seen:
                continue
            seen[taxon_id] = {
                "name": entry.get("name"),
                "rank": entry.get("rank"),
                "superkingdom": entry.get("superkingdom"),
            }

    ops: list[UpdateOne] = []
    for taxon_id, taxon_fields in seen.items():
        ops.append(
            UpdateOne(
                {"taxon_id": taxon_id},
                {
                    "$setOnInsert": {
                        "taxon_id": taxon_id,
                        "name": taxon_fields["name"],
                        "rank": taxon_fields["rank"],
                        "superkingdom": taxon_fields["superkingdom"],
                        "kingdom": None,
                        "phylum": None,
                        "class": None,
                        "order": None,
                        "family": None,
                        "genus": None,
                        "species": None,
                        "ncbi_url": (
                            f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/"
                            f"wwwtax.cgi?id={taxon_id}"
                        ),
                        "clinical_notes": None,
                        "taxdump_version": None,
                        "updated_at": None,
                    }
                },
                upsert=True,
            )
        )
    return ops


# ---------------------------------------------------------------------------
# Prepare phase — taxprofiler / metaval ingest
# ---------------------------------------------------------------------------


def _prepare_metaval_result(
    r: MetavalResult,
    case_id: str,
    sample_name_to_oid: dict[str, ObjectId],
    now: datetime,
) -> _MetavalPrepared:
    """
    Build the metaval_results document + blob uploads for one result, reading
    all file contents upfront so the transaction phase never touches disk.
    """
    blob_uploads: list[_BlobUpload] = []

    organisms: list[dict] = []
    for org in r.organisms:
        igv_key = None
        if not org.igv_too_large and org.igv_file_path:
            igv_key = (
                f"igv/{case_id}/{r.sample_name}/{r.classifier}/{org.organism_name}.html"
            )
            blob_uploads.append(
                _BlobUpload(
                    key=igv_key,
                    content=_read_text(org.igv_file_path, "IGV report"),
                )
            )
        organisms.append(
            {
                "organism_name": org.organism_name,
                "igv_key": igv_key,
                "igv_file_size_bytes": org.igv_file_size_bytes,
                "igv_too_large": org.igv_too_large,
            }
        )

    vd = r.verification_data
    vd_store: dict[str, object] = {
        "type": vd.type,
        "count": vd.count,
        "avg_length": vd.avg_length,
        "file_count": vd.file_count,
    }

    if vd.type in ("scaffolds", "contigs"):
        if vd.path and Path(vd.path).exists():
            blob_key = (
                f"verification_data/{case_id}/{r.sample_name}/"
                f"{r.classifier}/{r.taxon_name}_{vd.type}.fa"
            )
            blob_uploads.append(
                _BlobUpload(
                    key=blob_key,
                    content=_read_text(vd.path, "verification data"),
                )
            )
            vd_store["blob_key"] = blob_key
    elif vd.type == "raw_reads":
        for read_num, path_val in [
            ("1", vd.read_1_path),
            ("2", vd.read_2_path),
        ]:
            if path_val and Path(path_val).exists():
                blob_key = (
                    f"verification_data/{case_id}/{r.sample_name}/"
                    f"{r.classifier}/{r.taxon_name}_read_{read_num}.fa"
                )
                blob_uploads.append(
                    _BlobUpload(
                        key=blob_key,
                        content=_read_text(path_val, "verification data"),
                    )
                )
                vd_store[f"read_{read_num}_key"] = blob_key

    sample_object_id = sample_name_to_oid.get(r.sample_name)

    doc = {
        "case_id": case_id,
        "sample_id": sample_object_id,
        "sample_name": r.sample_name,
        "classifier": r.classifier,
        "taxon_id": r.taxon_id,
        "taxon_name": r.taxon_name,
        "organisms": organisms,
        "blast": r.blast.model_dump(),
        "verification_data": vd_store,
        "ingested_at": now,
    }
    return _MetavalPrepared(doc=doc, blob_uploads=blob_uploads)


async def _prepare_ingest(request: IngestRequest, now: datetime) -> _PreparedIngest:
    """
    Phase 1: parse, validate, and materialise every write — no DB or blob I/O.

    All blocking file reads (taxpasta CSV, Krona HTML, MultiQC JSON) are fanned
    out concurrently via asyncio.to_thread so the event loop stays unblocked.
    Any exception raised here means nothing has been written anywhere.
    """
    import pandas as pd

    # Deduplicate taxpasta paths so we load each file only once
    unique_taxpasta_paths = list(
        dict.fromkeys(clf.taxpasta for clf in request.classifiers)
    )

    # Fan out: pipeline info + multiqc data + all taxpasta tables
    _io_results = await asyncio.gather(
        asyncio.to_thread(read_pipeline_info, request.pipeline_info_path),
        asyncio.to_thread(read_multiqc, request.multiqc_path),
        *(asyncio.to_thread(load_taxpasta, p) for p in unique_taxpasta_paths),
    )
    pipeline_info_typed: PipelineInfoOutput = _io_results[0]  # type: ignore[assignment]
    qc_data_typed: MultiQCRaw = _io_results[1]  # type: ignore[assignment]
    taxpasta_cache: dict[str, pd.DataFrame] = {
        p: _io_results[2 + i]  # type: ignore[misc]
        for i, p in enumerate(unique_taxpasta_paths)
    }

    # Fan out: Krona HTML files + optional MultiQC report HTML
    blob_keys: list[str] = []
    blob_tasks: list = []
    for clf in request.classifiers:
        if clf.krona:
            blob_keys.append(f"krona:{clf.name}")
            blob_tasks.append(asyncio.to_thread(_read_text, clf.krona, "Krona file"))
    if request.multiqc_report_path:
        blob_keys.append("multiqc")
        blob_tasks.append(
            asyncio.to_thread(_read_text, request.multiqc_report_path, "MultiQC HTML")
        )
    blob_contents: dict[str, str] = {}
    if blob_tasks:
        blob_results = await asyncio.gather(*blob_tasks)
        blob_contents = dict(zip(blob_keys, blob_results))

    krona_uploads: list[_BlobUpload] = []
    classifier_docs: list[dict] = []
    for clf in request.classifiers:
        krona_id = None
        if clf.krona:
            krona_id = clf.name
            krona_uploads.append(
                _BlobUpload(
                    key=f"krona/{request.case_id}/{clf.name}.html",
                    content=blob_contents[f"krona:{clf.name}"],
                )
            )
        classifier_docs.append({"name": clf.name, "db": clf.db, "krona_id": krona_id})

    multiqc_upload: _BlobUpload | None = None
    if request.multiqc_report_path:
        multiqc_upload = _BlobUpload(
            key=f"multiqc/{request.case_id}/report.html",
            content=blob_contents["multiqc"],
        )

    sample_names = [s.sample_id for s in request.samples if s.sample_type == "sample"]
    sample_count = len(sample_names)
    control_count = len(
        [
            s
            for s in request.samples
            if s.sample_type in ("positive_ctrl", "negative_ctrl")
        ]
    )

    sample_docs: list[dict] = []
    all_profiles: list[dict] = []
    subject_refs: dict[str, list[int]] = {}

    for idx, s in enumerate(request.samples):
        if s.subject_id:
            subject_refs.setdefault(s.subject_id, []).append(idx)

        profiles: list[dict] = []
        classifier_qc: dict = {}

        for clf in request.classifiers:
            col = s.columns.get(clf.name)
            if not col:
                continue
            taxon_entries: list[TaxonEntry] = extract_sample_profile(
                taxpasta_cache[clf.taxpasta], col
            )
            profiles.append(
                {
                    "classifier": clf.name,
                    "classifier_db": clf.db,
                    "profile": [e.model_dump() for e in taxon_entries],
                }
            )
            clf_qc = _extract_classifier_qc(qc_data_typed, clf.name, col)
            if clf_qc:
                classifier_qc[clf.name] = clf_qc

        all_profiles.extend(profiles)
        base_qc = _extract_base_qc(qc_data_typed, s.sample_id)
        outbreak_taxa = _compute_outbreak_taxa(profiles)

        all_taxon_ids: list[int] = list(
            {
                entry["taxon_id"]
                for p in profiles
                for entry in p.get("profile", [])
                if isinstance(entry, dict) and entry.get("taxon_id") is not None
            }
        )

        sample_docs.append(
            {
                "_id": ObjectId(),
                "case_id": request.case_id,
                "sample_id": s.sample_id,
                "sample_source": s.sample_source,
                "order_date": request.order_date.isoformat()
                if request.order_date
                else None,
                "subject_id": None,
                "sample_type": s.sample_type,
                "material": s.material,
                "taxprofiler": {
                    **base_qc,
                    "classifiers": classifier_qc,
                    "pipeline_info": pipeline_info_typed.model_dump(),
                },
                "profiles": profiles,
                "outbreak_taxa": outbreak_taxa,
                "all_taxon_ids": all_taxon_ids,
                "has_krona": any(clf.krona for clf in request.classifiers),
                "review": {
                    "reviewed": False,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "notes": None,
                },
                "ingested_at": now,
            }
        )

    sample_ids = [doc["_id"] for doc in sample_docs]
    sample_name_to_oid = {doc["sample_id"]: doc["_id"] for doc in sample_docs}

    case_doc = {
        "case_id": request.case_id,
        "ticket_id": request.ticket_id,
        "order_date": request.order_date.isoformat() if request.order_date else None,
        "ingested_at": now,
        "sample_ids": sample_ids,
        "sample_count": sample_count,
        "control_count": control_count,
        "sample_names": sample_names,
        "classifiers": classifier_docs,
        "has_krona": any(clf.krona for clf in request.classifiers),
        "has_multiqc": bool(request.multiqc_report_path),
        "pipeline_info": pipeline_info_typed.model_dump(),
        "analysis_type": request.analysis_type.value if request.analysis_type else None,
        "sequencing_platform": (
            request.sequencing_platform.value if request.sequencing_platform else None
        ),
        "review": {
            "reviewed": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes": None,
        },
    }

    metaval_prepared: list[_MetavalPrepared] = []
    metaval_pipeline_info: dict | None = None
    if request.metaval:
        metaval_data: MetavalOutput = await asyncio.to_thread(
            read_metaval, request.metaval.metaval_dir
        )
        if metaval_data.pipeline_info:
            metaval_pipeline_info = metaval_data.pipeline_info.model_dump()
        if metaval_data.results:
            metaval_prepared = list(
                await asyncio.gather(
                    *(
                        asyncio.to_thread(
                            _prepare_metaval_result,
                            r,
                            request.case_id,
                            sample_name_to_oid,
                            now,
                        )
                        for r in metaval_data.results
                    )
                )
            )

    return _PreparedIngest(
        case_doc=case_doc,
        sample_docs=sample_docs,
        subject_refs=subject_refs,
        taxa_upsert_ops=_build_taxa_upsert_ops(all_profiles),
        metaval_prepared=metaval_prepared,
        metaval_pipeline_info=metaval_pipeline_info,
        krona_uploads=krona_uploads,
        multiqc_upload=multiqc_upload,
    )


# ---------------------------------------------------------------------------
# Commit phase — all Mongo writes inside one transaction
# ---------------------------------------------------------------------------


async def _resolve_subject_ids(
    db: AsyncIOMotorDatabase,
    subject_ids: list[str],
) -> dict[str, ObjectId]:
    """
    Upsert each subject_id and return a map from subject_id -> ObjectId.

    Runs outside the transaction — $setOnInsert skeleton docs are idempotent,
    so a leftover subject row if the txn later aborts is harmless. Running
    outside the txn lets us fan out all upserts concurrently (MongoDB sessions
    do not support concurrent operations).
    """
    now = datetime.now(timezone.utc)

    async def _upsert_one(subject_id: str) -> tuple[str, ObjectId]:
        doc = await db["subjects"].find_one_and_update(
            {"subject_id": subject_id},
            {"$setOnInsert": {"subject_id": subject_id, "created_at": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return subject_id, doc["_id"]

    pairs = await asyncio.gather(*(_upsert_one(sid) for sid in subject_ids))
    return dict(pairs)


async def _commit_prepared(
    db: AsyncIOMotorDatabase,
    prepared: _PreparedIngest,
    subject_map: dict[str, ObjectId],
    session: Any,
) -> None:
    """Run every Mongo write for one ingest, inside an already-started txn."""
    # 1. Patch pre-resolved subject ObjectIds onto sample docs
    for subject_id, indices in prepared.subject_refs.items():
        oid = subject_map[subject_id]
        for idx in indices:
            prepared.sample_docs[idx]["subject_id"] = oid

    # 2. Case — unique index on case_id enforces atomicity inside the txn
    case_doc = dict(prepared.case_doc)
    if prepared.metaval_pipeline_info is not None:
        case_doc["metaval_pipeline_info"] = prepared.metaval_pipeline_info
    await db["cases"].insert_one(case_doc, session=session)

    # 3. Samples — pre-generated _ids ensure case_doc.sample_ids references
    #    exactly these documents.
    if prepared.sample_docs:
        await db["samples"].insert_many(prepared.sample_docs, session=session)

    # 4. Metaval results
    if prepared.metaval_prepared:
        await db["metaval_results"].insert_many(
            [m.doc for m in prepared.metaval_prepared], session=session
        )


# ---------------------------------------------------------------------------
# Taxa skeleton upsert — runs outside the transaction
#
# Taxa entries are idempotent $setOnInsert skeletons. Running them inside the
# txn is expensive (thousands of upserts per case on single-node RS) and not
# required for correctness: if the txn later aborts, leftover skeleton rows
# are harmless reference data — same trade-off we accept for blob uploads.
# ---------------------------------------------------------------------------


async def _upsert_taxa_skeleton(db: AsyncIOMotorDatabase, ops: list[UpdateOne]) -> None:
    if ops:
        await db["taxa"].bulk_write(ops, ordered=False)


# ---------------------------------------------------------------------------
# Blob-upload phase — runs only after the transaction commits
# ---------------------------------------------------------------------------


async def _upload_all_blobs(prepared: _PreparedIngest) -> None:
    """
    Upload every blob concurrently. Fail-fast: the first exception aborts.
    Because this runs after the DB transaction has committed, a partial upload
    leaves the DB consistent but the blob store may have orphans. Orphaned
    blobs are acceptable for a clinical app — orphaned DB records are not.
    """
    import asyncio

    from app.database import get_blob_store

    store = get_blob_store()

    uploads: list[_BlobUpload] = list(prepared.krona_uploads)
    if prepared.multiqc_upload is not None:
        uploads.append(prepared.multiqc_upload)
    for mv in prepared.metaval_prepared:
        uploads.extend(mv.blob_uploads)

    if uploads:
        await asyncio.gather(*(store.put(u.key, u.content) for u in uploads))


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


async def ingest_case(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    """
    Atomic ingest of a taxprofiler + optional metaval case.

    Runs in three phases:
      1. Prepare — parse inputs, read every blob into memory, materialise
         every Mongo doc. No side effects.
      2. Commit — all Mongo writes inside one transaction. On any failure
         the txn aborts; no records are persisted.
      3. Upload — blob-store writes. Partial failure leaves orphan blobs,
         never orphan Mongo records.
    """
    now = datetime.now(timezone.utc)

    # Pre-check: friendlier error than the transaction-time DuplicateKeyError.
    # The unique index on case_id still enforces atomicity inside the txn.
    if await db["cases"].find_one({"case_id": request.case_id}):
        raise ValueError(
            f"Case '{request.case_id}' already exists. "
            f"Delete the existing case first, or use a unique case_id."
        )

    prepared = await _prepare_ingest(request, now)

    subject_map: dict[str, ObjectId] = {}
    if prepared.subject_refs:
        subject_map = await _resolve_subject_ids(db, list(prepared.subject_refs.keys()))

    await _upsert_taxa_skeleton(db, prepared.taxa_upsert_ops)

    client = get_client()
    async with await client.start_session() as session:
        async with session.start_transaction():
            await _commit_prepared(db, prepared, subject_map, session=session)

    await _upload_all_blobs(prepared)

    return {
        "case_id": request.case_id,
        "samples_ingested": len(prepared.sample_docs),
        "sample_ids": [str(doc["_id"]) for doc in prepared.sample_docs],
    }


# ---------------------------------------------------------------------------
# Trana ingest — same three-phase pattern
# ---------------------------------------------------------------------------


async def _prepare_trana_ingest(
    request: TranaIngestRequest, now: datetime
) -> _PreparedIngest:
    has_krona = any(s.krona_path for s in request.samples)

    # Fan out per-sample I/O: emu abundance + optional nanoplot stats + optional krona
    async def _load_sample_io(
        s: Any,
    ) -> tuple[
        list[TaxonEntry], NanoPlotStats | None, NanoPlotStats | None, str | None
    ]:
        tasks: list = [asyncio.to_thread(read_emu_abundance, s.abundance_path)]
        has_unprocessed = bool(s.nanoplot_unprocessed_path)
        has_processed = bool(s.nanoplot_processed_path)
        has_krona_file = bool(s.krona_path)
        if has_unprocessed:
            tasks.append(asyncio.to_thread(read_nanostats, s.nanoplot_unprocessed_path))
        if has_processed:
            tasks.append(asyncio.to_thread(read_nanostats, s.nanoplot_processed_path))
        if has_krona_file:
            tasks.append(asyncio.to_thread(_read_text, s.krona_path, "Krona file"))
        results = await asyncio.gather(*tasks)
        i = 0
        taxon_entries: list[TaxonEntry] = results[i]
        i += 1
        nano_unproc: NanoPlotStats | None = results[i] if has_unprocessed else None
        if has_unprocessed:
            i += 1
        nano_proc: NanoPlotStats | None = results[i] if has_processed else None
        if has_processed:
            i += 1
        krona_content: str | None = results[i] if has_krona_file else None
        return taxon_entries, nano_unproc, nano_proc, krona_content

    # pipeline info + all per-sample I/O concurrently
    _trana_results = await asyncio.gather(
        asyncio.to_thread(read_pipeline_info, request.pipeline_info_path),
        *(_load_sample_io(s) for s in request.samples),
    )
    pipeline_info: PipelineInfoOutput = _trana_results[0]  # type: ignore[assignment]
    sample_io_results: list[
        tuple[list[TaxonEntry], NanoPlotStats | None, NanoPlotStats | None, str | None]
    ] = _trana_results[1:]  # type: ignore[assignment]

    multiqc_upload: _BlobUpload | None = None
    if request.multiqc_report_path:
        multiqc_upload = _BlobUpload(
            key=f"multiqc/{request.case_id}/report.html",
            content=await asyncio.to_thread(
                _read_text, request.multiqc_report_path, "MultiQC HTML"
            ),
        )

    sample_names = [s.sample_id for s in request.samples if s.sample_type == "sample"]
    sample_count = len(sample_names)
    control_count = len(
        [
            s
            for s in request.samples
            if s.sample_type in ("positive_ctrl", "negative_ctrl")
        ]
    )

    sample_docs: list[dict[str, Any]] = []
    all_profiles: list[dict[str, Any]] = []
    subject_refs: dict[str, list[int]] = {}
    krona_uploads: list[_BlobUpload] = []

    for idx, (s, (taxon_entries, nano_unproc, nano_proc, krona_content)) in enumerate(
        zip(request.samples, sample_io_results)
    ):
        if s.subject_id:
            subject_refs.setdefault(s.subject_id, []).append(idx)

        if krona_content is not None:
            krona_uploads.append(
                _BlobUpload(
                    key=f"krona/{request.case_id}/{s.sample_id}.html",
                    content=krona_content,
                )
            )

        profile: dict[str, Any] = {
            "classifier": "emu",
            "classifier_db": "default",
            "profile": [e.model_dump() for e in taxon_entries],
        }
        profiles = [profile]
        all_profiles.extend(profiles)

        outbreak_taxa = _compute_outbreak_taxa(profiles)
        all_taxon_ids: list[int] = [e.taxon_id for e in taxon_entries]

        trana_qc: dict[str, Any] = {
            "nanoplot_unprocessed": nano_unproc.model_dump() if nano_unproc else None,
            "nanoplot_processed": nano_proc.model_dump() if nano_proc else None,
            "pipeline_info": pipeline_info.model_dump(),
        }

        sample_docs.append(
            {
                "_id": ObjectId(),
                "case_id": request.case_id,
                "sample_id": s.sample_id,
                "sample_source": s.sample_source,
                "order_date": (
                    request.order_date.isoformat() if request.order_date else None
                ),
                "subject_id": None,
                "sample_type": s.sample_type,
                "material": s.material,
                "trana": trana_qc,
                "profiles": profiles,
                "outbreak_taxa": outbreak_taxa,
                "all_taxon_ids": all_taxon_ids,
                "has_krona": bool(s.krona_path),
                "review": {
                    "reviewed": False,
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "notes": None,
                },
                "ingested_at": now,
            }
        )

    sample_ids = [doc["_id"] for doc in sample_docs]

    case_doc: dict[str, Any] = {
        "case_id": request.case_id,
        "ticket_id": request.ticket_id,
        "order_date": request.order_date.isoformat() if request.order_date else None,
        "ingested_at": now,
        "sample_ids": sample_ids,
        "sample_count": sample_count,
        "control_count": control_count,
        "sample_names": sample_names,
        "classifiers": [{"name": "emu", "db": "default", "krona_id": None}],
        "has_krona": has_krona,
        "has_multiqc": bool(request.multiqc_report_path),
        "pipeline_info": pipeline_info.model_dump(),
        "analysis_type": request.analysis_type.value if request.analysis_type else None,
        "sequencing_platform": (
            request.sequencing_platform.value if request.sequencing_platform else None
        ),
        "review": {
            "reviewed": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes": None,
        },
    }

    return _PreparedIngest(
        case_doc=case_doc,
        sample_docs=sample_docs,
        subject_refs=subject_refs,
        taxa_upsert_ops=_build_taxa_upsert_ops(all_profiles),
        metaval_prepared=[],
        metaval_pipeline_info=None,
        krona_uploads=krona_uploads,
        multiqc_upload=multiqc_upload,
    )


async def ingest_trana_case(
    request: TranaIngestRequest, db: AsyncIOMotorDatabase
) -> dict:
    """Atomic ingest of a Trana (16S / ONT / Emu) case. See `ingest_case`."""
    now = datetime.now(timezone.utc)

    if await db["cases"].find_one({"case_id": request.case_id}):
        raise ValueError(
            f"Case '{request.case_id}' already exists. "
            f"Delete the existing case first, or use a unique case_id."
        )

    prepared = await _prepare_trana_ingest(request, now)

    subject_map: dict[str, ObjectId] = {}
    if prepared.subject_refs:
        subject_map = await _resolve_subject_ids(db, list(prepared.subject_refs.keys()))

    await _upsert_taxa_skeleton(db, prepared.taxa_upsert_ops)

    client = get_client()
    async with await client.start_session() as session:
        async with session.start_transaction():
            await _commit_prepared(db, prepared, subject_map, session=session)

    await _upload_all_blobs(prepared)

    return {
        "case_id": request.case_id,
        "samples_ingested": len(prepared.sample_docs),
        "sample_ids": [str(doc["_id"]) for doc in prepared.sample_docs],
    }


# ---------------------------------------------------------------------------
# Unchanged QC helpers
# ---------------------------------------------------------------------------


def _extract_classifier_qc(qc_data: MultiQCRaw, classifier_name: str, col: str) -> dict:
    """Extract classifier-specific QC stats from multiqc data.

    Expects the MultiQC v2 dict-of-dicts format:
      {"U": {"unclassified": N}, "R": {"root": N}, "S": {taxon: N, ...}, ...}
    """
    if classifier_name == "kraken2":
        key = col.split(".kraken2")[0]
        records = qc_data.kraken2.get(key)
    elif classifier_name == "centrifuge":
        records = qc_data.centrifuge.get(col)
    elif classifier_name == "diamond":
        key = col.split(".diamond")[0]
        stats = qc_data.diamond.get(key)
        if not stats:
            return {}
        return {"queries_aligned": stats.get("queries_aligned") or None}
    else:
        return {}

    if not records or not isinstance(records, dict):
        return {}

    unclassified_reads = sum(records.get("U", {}).values())

    root_counts = records.get("R", {})
    if root_counts:
        classified_reads = sum(root_counts.values())
    else:
        classified_reads = sum(records.get("S", {}).values())

    num_species = len(records.get("S", {}))
    num_genera = len(records.get("G", {}))
    total_reads = unclassified_reads + classified_reads

    return {
        "pct_unclassified": round(unclassified_reads / total_reads * 100, 2)
        if total_reads
        else None,
        "unclassified_reads": unclassified_reads or None,
        "classified_reads": classified_reads or None,
        "total_reads": total_reads or None,
        "num_species": num_species or None,
        "num_genera": num_genera or None,
    }


def _extract_base_qc(qc_data: MultiQCRaw, sample_id: str) -> dict:
    """Extract classifier-agnostic QC stats: fastp, bowtie2, fastqc."""
    stats = {}

    fastp_all = qc_data.fastp
    bowtie2_all = qc_data.bowtie2

    fastp_lanes = {
        k: v
        for k, v in fastp_all.items()
        if k.startswith(f"{sample_id}_") or k == sample_id
    }
    bowtie2_lanes = {
        k: v
        for k, v in bowtie2_all.items()
        if k.startswith(f"{sample_id}_") or k == sample_id
    }

    if fastp_lanes:
        n_lanes = len(fastp_lanes)
        total_before = sum(
            v.get("summary", {}).get("before_filtering", {}).get("total_reads", 0)
            for v in fastp_lanes.values()
        )
        total_after = sum(
            v.get("summary", {}).get("after_filtering", {}).get("total_reads", 0)
            for v in fastp_lanes.values()
        )
        passed = sum(
            v.get("filtering_result", {}).get("passed_filter_reads", 0)
            for v in fastp_lanes.values()
        )
        low_quality = sum(
            v.get("filtering_result", {}).get("low_quality_reads", 0)
            for v in fastp_lanes.values()
        )
        too_short = sum(
            v.get("filtering_result", {}).get("too_short_reads", 0)
            for v in fastp_lanes.values()
        )
        q20_vals = [
            v.get("summary", {}).get("after_filtering", {}).get("q20_rate")
            for v in fastp_lanes.values()
        ]
        q30_vals = [
            v.get("summary", {}).get("after_filtering", {}).get("q30_rate")
            for v in fastp_lanes.values()
        ]
        gc_vals = [
            v.get("summary", {}).get("after_filtering", {}).get("gc_content")
            for v in fastp_lanes.values()
        ]
        stats["fastp"] = {
            "total_reads_before_filtering": total_before or None,
            "total_reads_after_filtering": total_after or None,
            "passed_filter_reads": passed or None,
            "low_quality_reads": low_quality or None,
            "too_short_reads": too_short or None,
            "q20_rate": round(sum(v for v in q20_vals if v) / n_lanes, 4)
            if any(q20_vals)
            else None,
            "q30_rate": round(sum(v for v in q30_vals if v) / n_lanes, 4)
            if any(q30_vals)
            else None,
            "gc_content": round(sum(v for v in gc_vals if v) / n_lanes, 4)
            if any(gc_vals)
            else None,
        }

    if bowtie2_lanes:
        rates = [v.get("overall_alignment_rate") for v in bowtie2_lanes.values()]
        overall_rate = (
            round(sum(r for r in rates if r is not None) / len(rates), 2)
            if any(r is not None for r in rates)
            else None
        )
        stats["bowtie2"] = {
            "total_reads": sum(v.get("total_reads", 0) for v in bowtie2_lanes.values())
            or None,
            "aligned_exactly_one": sum(
                v.get("paired_aligned_one", 0) for v in bowtie2_lanes.values()
            )
            or None,
            "aligned_multi": sum(
                v.get("paired_aligned_multi", 0) for v in bowtie2_lanes.values()
            )
            or None,
            "aligned_none": sum(
                v.get("paired_aligned_none", 0) for v in bowtie2_lanes.values()
            )
            or None,
            "overall_alignment_rate": overall_rate,
        }

    fastqc_all = qc_data.fastqc
    fastqc_fwd_lanes = {
        k: v
        for k, v in fastqc_all.items()
        if k.startswith(f"{sample_id}_") and k.endswith("_raw_1")
    }
    fastqc_rev_lanes = {
        k: v
        for k, v in fastqc_all.items()
        if k.startswith(f"{sample_id}_") and k.endswith("_raw_2")
    }

    if fastqc_fwd_lanes or fastqc_rev_lanes:

        def _avg(lanes: dict, field: str) -> float | None:
            vals = [v.get(field) for v in lanes.values() if v.get(field) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        stats["fastqc"] = {
            "total_sequences": sum(
                v.get("total_sequences", 0) for v in fastqc_fwd_lanes.values()
            )
            or None,
            "avg_sequence_length": _avg(fastqc_fwd_lanes, "avg_sequence_length"),
            "pct_gc_forward": _avg(fastqc_fwd_lanes, "percent_gc"),
            "pct_gc_reverse": _avg(fastqc_rev_lanes, "percent_gc"),
            "pct_poor_quality_forward": _avg(fastqc_fwd_lanes, "percent_fails"),
            "pct_poor_quality_reverse": _avg(fastqc_rev_lanes, "percent_fails"),
        }

    return stats
