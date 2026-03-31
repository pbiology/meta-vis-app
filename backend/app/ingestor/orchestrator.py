# app/ingestor/orchestrator.py

from datetime import datetime, timezone
from pathlib import Path
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
    case_object_id: ObjectId,
    classifier_name: str,
    krona_path: str,
) -> ObjectId:
    path = Path(krona_path)
    if not path.exists():
        raise FileNotFoundError(f"Krona file not found: {krona_path}")
    html = path.read_text(encoding="utf-8")
    result = await db["krona_files"].find_one_and_replace(
        {"case_id": case_object_id, "classifier": classifier_name},
        {
            "case_id":    case_object_id,
            "classifier": classifier_name,
            "html":       html,
            "stored_at":  datetime.now(timezone.utc),
        },
        upsert=True,
        return_document=True,
    )
    return result["_id"]


async def ingest_case(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    pipeline_info    = read_pipeline_info(request.pipeline_info_path)
    qc_data          = read_multiqc(request.multiqc_path)

    existing_case = await db["cases"].find_one({"case_id": request.case_id})
    if existing_case:
        raise ValueError(
            f"Case '{request.case_id}' already exists. "
            f"Delete the existing case first, or use a unique case_id."
        )

    # Store Krona files per classifier and build classifier metadata
    classifier_docs = []
    for clf in request.classifiers:
        krona_id = None
        if clf.krona:
            # Temporarily insert case to get ObjectId, then update
            pass
        classifier_docs.append({
            "name":  clf.name,
            "db":    clf.db,
            "krona": None,  # filled in after case insert
        })

    case_doc = {
        "case_id":     request.case_id,
        "ingested_at": now,
        "sample_ids":  [],
        "classifiers": classifier_docs,
        "has_krona":   any(clf.krona for clf in request.classifiers),
        "pipeline_info": pipeline_info,
        "review": {
            "reviewed":    False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes":       None,
        },
    }
    case_result    = await db["cases"].insert_one(case_doc)
    case_object_id = case_result.inserted_id

    # Now store Krona files with the real case ObjectId
    updated_classifiers = []
    for clf in request.classifiers:
        krona_id = None
        if clf.krona:
            krona_doc_id = await _store_krona(db, case_object_id, clf.name, clf.krona)
            krona_id = str(krona_doc_id)
        updated_classifiers.append({
            "name":     clf.name,
            "db":       clf.db,
            "krona_id": krona_id,
        })

    await db["cases"].update_one(
        {"_id": case_object_id},
        {"$set": {"classifiers": updated_classifiers}},
    )

    sample_ids = []

    for s in request.samples:
        subject_object_id = None
        if s.subject_id:
            subject_object_id = await _upsert_subject(db, s.subject_id)

        # Build profiles and classifier QC stats for each classifier
        profiles = []
        classifier_qc = {}

        for clf in request.classifiers:
            col = s.columns.get(clf.name)
            if not col:
                continue

            profile = read_taxpasta(
                clf.taxpasta,
                col,
            )
            profiles.append({
                "classifier":    clf.name,
                "classifier_db": clf.db,
                "profile":       profile,
            })

            clf_qc = _extract_classifier_qc(qc_data, clf.name, col)
            if clf_qc:
                classifier_qc[clf.name] = clf_qc

        # Classifier-agnostic QC (fastp, bowtie2, fastqc) — use first available column
        first_col = next(iter(s.columns.values()), None)
        base_qc = _extract_base_qc(qc_data, first_col) if first_col else {}

        sample_doc = {
            "case_id":     case_object_id,
            "subject_id":  subject_object_id,
            "sample_type": s.sample_type,
            "material":    s.material,
            "order_date":  s.order_date.isoformat() if s.order_date else None,
            "sample": {
                "sample_id":   s.sample_id,
                "material":    s.material,
                "sample_type": s.sample_type,
                "subject_id":  s.subject_id,
                "order_date":  s.order_date.isoformat() if s.order_date else None,
            },
            "library_preparation": s.library_preparation.model_dump() if s.library_preparation else None,
            "sequencing":          s.sequencing.model_dump() if s.sequencing else None,
            "taxprofiler": {
                **base_qc,
                "classifiers":   classifier_qc,
                "pipeline_info": pipeline_info,
            },
            "profiles":    profiles,
            "has_krona":   any(clf.krona for clf in request.classifiers),
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

    await db["cases"].update_one(
        {"_id": case_object_id},
        {"$set": {"sample_ids": sample_ids}},
    )

    return {
        "case_id":          request.case_id,
        "case_object_id":   str(case_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids":       [str(sid) for sid in sample_ids],
    }


def _base_sample_name(col: str) -> str:
    """Strip classifier/db suffixes to get the base sample name."""
    name = col.split(".kraken2")[0].split(".centrifuge")[0]
    name = name.split("_k2")[0]
    for sep in ["_p_compressed", "_p_h_v"]:
        name = name.split(sep)[0]
    return name


def _extract_classifier_qc(qc_data: dict, classifier_name: str, col: str) -> dict:
    """Extract classifier-specific QC stats (unclassified %, species, genera)."""
    stats = {}

    if classifier_name == "kraken2":
        kraken_key = col.split(".kraken2")[0]
        kraken2 = qc_data.get("kraken2", {}).get(kraken_key)
        if kraken2:
            unclassified_reads = sum(kraken2.get("U", {}).values()) if kraken2.get("U") else None
            total_classified   = sum(kraken2.get("R", {}).values()) if kraken2.get("R") else None
            num_species        = len(kraken2.get("S", {})) if kraken2.get("S") else None
            num_genera         = len(kraken2.get("G", {})) if kraken2.get("G") else None
            total_reads = (unclassified_reads or 0) + (total_classified or 0)
            pct_unclassified = (
                round(unclassified_reads / total_reads * 100, 2)
                if total_reads and unclassified_reads is not None else None
            )
            stats = {
                "pct_unclassified":  pct_unclassified,
                "unclassified_reads": unclassified_reads,
                "num_species":        num_species,
                "num_genera":         num_genera,
            }

    elif classifier_name == "centrifuge":
        centrifuge_key = col  # column name is the key directly
        centrifuge = qc_data.get("centrifuge", {}).get(centrifuge_key)
        if centrifuge:
            unclassified_reads = sum(centrifuge.get("U", {}).values()) if centrifuge.get("U") else None
            total_classified   = sum(centrifuge.get("R", {}).values()) if centrifuge.get("R") else None
            num_species        = len(centrifuge.get("S", {})) if centrifuge.get("S") else None
            num_genera         = len(centrifuge.get("G", {})) if centrifuge.get("G") else None
            total_reads = (unclassified_reads or 0) + (total_classified or 0)
            pct_unclassified = (
                round(unclassified_reads / total_reads * 100, 2)
                if total_reads and unclassified_reads is not None else None
            )
            stats = {
                "pct_unclassified":  pct_unclassified,
                "unclassified_reads": unclassified_reads,
                "num_species":        num_species,
                "num_genera":         num_genera,
            }

    return stats


def _extract_base_qc(qc_data: dict, col: str) -> dict:
    """Extract classifier-agnostic QC stats: fastp, bowtie2, fastqc."""
    stats = {}
    base = _base_sample_name(col)

    fastp_all   = qc_data.get("fastp", {})
    bowtie2_all = qc_data.get("bowtie2", {})

    fastp_lanes   = {k: v for k, v in fastp_all.items()   if k.startswith(f"{base}_")}
    bowtie2_lanes = {k: v for k, v in bowtie2_all.items() if k.startswith(f"{base}_")}

    if fastp_lanes:
        n_lanes      = len(fastp_lanes)
        total_before = sum(v.get("summary", {}).get("before_filtering", {}).get("total_reads", 0) for v in fastp_lanes.values())
        total_after  = sum(v.get("summary", {}).get("after_filtering",  {}).get("total_reads", 0) for v in fastp_lanes.values())
        passed       = sum(v.get("filtering_result", {}).get("passed_filter_reads", 0) for v in fastp_lanes.values())
        low_quality  = sum(v.get("filtering_result", {}).get("low_quality_reads",   0) for v in fastp_lanes.values())
        too_short    = sum(v.get("filtering_result", {}).get("too_short_reads",     0) for v in fastp_lanes.values())
        q20_vals     = [v.get("summary", {}).get("after_filtering", {}).get("q20_rate")  for v in fastp_lanes.values()]
        q30_vals     = [v.get("summary", {}).get("after_filtering", {}).get("q30_rate")  for v in fastp_lanes.values()]
        gc_vals      = [v.get("summary", {}).get("after_filtering", {}).get("gc_content") for v in fastp_lanes.values()]
        stats["fastp"] = {
            "total_reads_before_filtering": total_before or None,
            "total_reads_after_filtering":  total_after  or None,
            "passed_filter_reads":          passed       or None,
            "low_quality_reads":            low_quality  or None,
            "too_short_reads":              too_short    or None,
            "q20_rate":   round(sum(v for v in q20_vals if v) / n_lanes, 4) if any(q20_vals) else None,
            "q30_rate":   round(sum(v for v in q30_vals if v) / n_lanes, 4) if any(q30_vals) else None,
            "gc_content": round(sum(v for v in gc_vals  if v) / n_lanes, 4) if any(gc_vals)  else None,
        }

    if bowtie2_lanes:
        rates        = [v.get("overall_alignment_rate") for v in bowtie2_lanes.values()]
        overall_rate = round(sum(r for r in rates if r is not None) / len(rates), 2) if any(r is not None for r in rates) else None
        stats["bowtie2"] = {
            "total_reads":            sum(v.get("total_reads",           0) for v in bowtie2_lanes.values()) or None,
            "aligned_exactly_one":    sum(v.get("paired_aligned_one",    0) for v in bowtie2_lanes.values()) or None,
            "aligned_multi":          sum(v.get("paired_aligned_multi",  0) for v in bowtie2_lanes.values()) or None,
            "aligned_none":           sum(v.get("paired_aligned_none",   0) for v in bowtie2_lanes.values()) or None,
            "overall_alignment_rate": overall_rate,
        }

    fastqc_all       = qc_data.get("fastqc", {})
    fastqc_fwd_lanes = {k: v for k, v in fastqc_all.items() if k.startswith(f"{base}_") and k.endswith("_raw_1")}
    fastqc_rev_lanes = {k: v for k, v in fastqc_all.items() if k.startswith(f"{base}_") and k.endswith("_raw_2")}

    if fastqc_fwd_lanes or fastqc_rev_lanes:
        def _avg(lanes, field):
            vals = [v.get(field) for v in lanes.values() if v.get(field) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None
        stats["fastqc"] = {
            "total_sequences":            sum(v.get("total_sequences", 0) for v in fastqc_fwd_lanes.values()) or None,
            "avg_sequence_length":        _avg(fastqc_fwd_lanes, "avg_sequence_length"),
            "pct_gc_forward":             _avg(fastqc_fwd_lanes, "percent_gc"),
            "pct_gc_reverse":             _avg(fastqc_rev_lanes, "percent_gc"),
            "pct_poor_quality_forward":   _avg(fastqc_fwd_lanes, "percent_fails"),
            "pct_poor_quality_reverse":   _avg(fastqc_rev_lanes, "percent_fails"),
        }

    return stats