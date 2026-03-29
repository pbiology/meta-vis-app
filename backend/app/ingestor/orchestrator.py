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
    case_object_id: ObjectId,
    krona_path: str,
) -> None:
    """
    Read Krona HTML from disk at ingest time and store in MongoDB.
    Linked to the case, not individual samples.
    Filesystem is only accessed here — never at query time.
    """
    path = Path(krona_path)
    if not path.exists():
        raise FileNotFoundError(f"Krona file not found: {krona_path}")
    html = path.read_text(encoding="utf-8")
    await db["krona_files"].find_one_and_replace(
        {"case_id": case_object_id},
        {
            "case_id":   case_object_id,
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


async def ingest_case(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    # Load superkingdom map once for the entire case
    superkingdom_map = await _load_superkingdom_map(db, request.taxonomy_db)

    # Read pipeline outputs once — shared across all samples in the case
    pipeline_info = read_pipeline_info(request.pipeline_info_path)
    qc_data       = read_multiqc(request.multiqc_path)

    has_krona = bool(request.krona_path)

    # Guard against duplicate case ID (see TECHNICAL_DEBT.md)
    existing_case = await db["cases"].find_one({"run_id": request.run_id})
    if existing_case:
        raise ValueError(
            f"Case '{request.run_id}' already exists (ObjectId: {existing_case['_id']}). "
            f"Delete the existing case first, or use a unique run_id."
        )

    case_doc = {
        "run_id":      request.run_id,
        "ingested_at": now,
        "sample_ids":  [],
        "taxonomy_db": request.taxonomy_db,
        "has_krona":   has_krona,
        "review": {
            "reviewed":    False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes":       None,
        },
    }
    case_result    = await db["cases"].insert_one(case_doc)
    case_object_id = case_result.inserted_id

    # Store Krona HTML in DB if provided — once per case
    if request.krona_path:
        await _store_krona(db, case_object_id, request.krona_path)

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
            "case_id":             case_object_id,
            "subject_id":          subject_object_id,
            "sample_type":         s.sample_type,
            "material":            s.material,
            "order_date":          s.order_date.isoformat() if s.order_date else None,
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

    await db["cases"].update_one(
        {"_id": case_object_id},
        {"$set": {"sample_ids": sample_ids}},
    )

    return {
        "case_id":          request.run_id,
        "case_object_id":   str(case_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids":       [str(sid) for sid in sample_ids],
    }


def _base_sample_name(taxpasta_column: str) -> str:
    """
    Derive the canonical base sample name from a taxpasta column string.

    taxprofiler appends classifier/db suffixes to column names:
        PE-04-28_k2_pluspf.kraken2.kraken2.report  ->  PE-04-28

    Strategy: split on '_k2' (Kraken2 suffix) or '.kraken2' first;
    fall back to the whole string if neither pattern matches.
    """
    # Strip the '.kraken2.kraken2.report' (or similar) dot-suffix first
    name = taxpasta_column.split(".kraken2")[0]  # PE-04-28_k2_pluspf
    # Strip the '_k2...' classifier+db suffix
    name = name.split("_k2")[0]                  # PE-04-28
    return name


def extract_sample_qc(qc_data: dict, taxpasta_column: str) -> dict:
    """
    Extract per-sample QC stats from the pre-loaded multiqc data dict.

    taxprofiler uses different key formats in each MultiQC section:
      multiqc_kraken  : {base}_k2_{db}          e.g. PE-04-28_k2_pluspf
      multiqc_fastp   : {base}_{lane}            e.g. PE-04-28_1  (aggregated)
      multiqc_bowtie2 : {base}_{lane}            e.g. PE-04-28_1  (aggregated)
      multiqc_fastqc  : {base}_{lane}_raw_{1|2}  e.g. PE-04-28_1_raw_1

    All are derived from the taxpasta_column supplied at ingest time.
    """
    stats = {}
    base = _base_sample_name(taxpasta_column)

    # --- Kraken2 ---
    # Key format: {base}_k2_{db}  — reconstruct from the column name directly
    # The column is e.g. 'PE-04-28_k2_pluspf.kraken2.kraken2.report'
    # Strip the dot-suffix to get 'PE-04-28_k2_pluspf'
    kraken_key = taxpasta_column.split(".kraken2")[0]  # PE-04-28_k2_pluspf
    kraken2 = qc_data.get("kraken2", {}).get(kraken_key)
    if kraken2:
        # Flatten the nested rank-dict into plain counts
        unclassified_reads = sum(kraken2.get("U", {}).values()) if kraken2.get("U") else None
        total_classified   = sum(kraken2.get("R", {}).values()) if kraken2.get("R") else None
        num_species        = len(kraken2.get("S", {})) if kraken2.get("S") else None
        num_genera         = len(kraken2.get("G", {})) if kraken2.get("G") else None
        total_reads = (unclassified_reads or 0) + (total_classified or 0)
        pct_unclassified = (
            round(unclassified_reads / total_reads * 100, 2)
            if total_reads and unclassified_reads is not None
            else None
        )
        stats["kraken2"] = {
            "pct_unclassified": pct_unclassified,
            "unclassified_reads": unclassified_reads,
            "num_species": num_species,
            "num_genera": num_genera,
        }

    # --- fastp & bowtie2 (lane-level, aggregated) ---
    # Keys like PE-04-28_1, PE-04-28_2, ...
    fastp_all   = qc_data.get("fastp", {})
    bowtie2_all = qc_data.get("bowtie2", {})

    fastp_lanes   = {k: v for k, v in fastp_all.items()   if k.startswith(f"{base}_")}
    bowtie2_lanes = {k: v for k, v in bowtie2_all.items() if k.startswith(f"{base}_")}

    if fastp_lanes:
        # Sum read counts across lanes; average rates
        total_before = sum(v.get("summary", {}).get("before_filtering", {}).get("total_reads", 0)
                           for v in fastp_lanes.values())
        total_after  = sum(v.get("summary", {}).get("after_filtering",  {}).get("total_reads", 0)
                           for v in fastp_lanes.values())
        passed       = sum(v.get("filtering_result", {}).get("passed_filter_reads", 0)
                           for v in fastp_lanes.values())
        low_quality  = sum(v.get("filtering_result", {}).get("low_quality_reads",  0)
                           for v in fastp_lanes.values())
        too_short    = sum(v.get("filtering_result", {}).get("too_short_reads",    0)
                           for v in fastp_lanes.values())
        n_lanes = len(fastp_lanes)
        q20_vals = [v.get("summary", {}).get("after_filtering", {}).get("q20_rate")
                    for v in fastp_lanes.values()]
        q30_vals = [v.get("summary", {}).get("after_filtering", {}).get("q30_rate")
                    for v in fastp_lanes.values()]
        gc_vals  = [v.get("summary", {}).get("after_filtering", {}).get("gc_content")
                    for v in fastp_lanes.values()]
        stats["fastp"] = {
            "total_reads_before_filtering": total_before or None,
            "total_reads_after_filtering":  total_after  or None,
            "passed_filter_reads":          passed       or None,
            "low_quality_reads":            low_quality  or None,
            "too_short_reads":              too_short    or None,
            "q20_rate": round(sum(v for v in q20_vals if v) / n_lanes, 4) if any(q20_vals) else None,
            "q30_rate": round(sum(v for v in q30_vals if v) / n_lanes, 4) if any(q30_vals) else None,
            "gc_content": round(sum(v for v in gc_vals if v)  / n_lanes, 4) if any(gc_vals)  else None,
        }

    if bowtie2_lanes:
        # Sum reads across lanes; average alignment rate
        total_reads_bt = sum(v.get("total_reads", 0) for v in bowtie2_lanes.values())
        aligned_one    = sum(v.get("paired_aligned_one",   0) for v in bowtie2_lanes.values())
        aligned_multi  = sum(v.get("paired_aligned_multi", 0) for v in bowtie2_lanes.values())
        aligned_none   = sum(v.get("paired_aligned_none",  0) for v in bowtie2_lanes.values())
        rates = [v.get("overall_alignment_rate") for v in bowtie2_lanes.values()]
        overall_rate   = round(sum(r for r in rates if r is not None) / len(rates), 2) if any(r is not None for r in rates) else None
        stats["bowtie2"] = {
            "total_reads":           total_reads_bt or None,
            "aligned_exactly_one":   aligned_one    or None,
            "aligned_multi":         aligned_multi  or None,
            "aligned_none":          aligned_none   or None,
            "overall_alignment_rate": overall_rate,
        }

    # --- FastQC (pre-trimming, per lane, paired) ---
    # Keys like PE-04-28_1_raw_1, PE-04-28_1_raw_2
    fastqc_all = qc_data.get("fastqc", {})
    fastqc_fwd_lanes = {k: v for k, v in fastqc_all.items()
                        if k.startswith(f"{base}_") and k.endswith("_raw_1")}
    fastqc_rev_lanes = {k: v for k, v in fastqc_all.items()
                        if k.startswith(f"{base}_") and k.endswith("_raw_2")}

    if fastqc_fwd_lanes or fastqc_rev_lanes:
        def _avg(lanes: dict, field: str):
            vals = [v.get(field) for v in lanes.values() if v.get(field) is not None]
            return round(sum(vals) / len(vals), 2) if vals else None

        stats["fastqc"] = {
            "total_sequences":       sum(v.get("total_sequences", 0) for v in fastqc_fwd_lanes.values()) or None,
            "avg_sequence_length":   _avg(fastqc_fwd_lanes, "avg_sequence_length"),
            "pct_gc_forward":        _avg(fastqc_fwd_lanes, "percent_gc"),
            "pct_gc_reverse":        _avg(fastqc_rev_lanes, "percent_gc"),
            "pct_poor_quality_forward": _avg(fastqc_fwd_lanes, "percent_fails"),
            "pct_poor_quality_reverse": _avg(fastqc_rev_lanes, "percent_fails"),
        }

    return stats