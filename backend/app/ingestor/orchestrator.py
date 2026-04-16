# app/ingestor/orchestrator.py

from datetime import datetime, timezone
from pathlib import Path
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Any
from pymongo import UpdateOne

from app.models.sample import IngestRequest
from app.ingestor.taxpasta_reader import load_taxpasta, extract_sample_profile
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.ingestor.metaval_reader import read_metaval
from app.ingestor.models import (
    MetavalOutput,
    MetavalResult,
    MultiQCRaw,
    PipelineInfoOutput,
    TaxonEntry,
)


async def _upsert_subject(db: AsyncIOMotorDatabase, subject_id: str) -> ObjectId:
    result = await db["subjects"].find_one({"subject_id": subject_id})
    if result:
        return result["_id"]
    insert = await db["subjects"].insert_one(
        {
            "subject_id": subject_id,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return insert.inserted_id


async def _store_krona(
    case_object_id: ObjectId,
    classifier_name: str,
    krona_path: str,
) -> None:
    from app.database import get_blob_store

    path = Path(krona_path)
    if not path.exists():
        raise FileNotFoundError(f"Krona file not found: {krona_path}")
    html = path.read_text(encoding="utf-8")
    key = f"krona/{case_object_id}/{classifier_name}.html"
    await get_blob_store().put(key, html)


def _compute_outbreak_taxa(
    profiles: list,
) -> list:
    """
    Extract taxa from profiles that match any enabled outbreak config.

    Uses the outbreak configs loaded from outbreak_configs.json at startup.
    """
    from app.config import settings

    if not settings.outbreak_configs:
        return []

    outbreak_taxa = []
    seen_taxon_ids = set()

    for profile in profiles:
        classifier_name = profile.get("classifier")

        for entry in profile.get("profile", []):
            taxon_id = entry.get("taxon_id")

            if taxon_id in seen_taxon_ids:
                continue

            superkingdom = entry.get("superkingdom")
            rank = entry.get("rank")
            abundance = entry.get("abundance", 0)

            # Check if this taxon matches ANY outbreak config
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


async def _upsert_taxa_from_profiles(profiles: list, db: AsyncIOMotorDatabase) -> None:
    """
    Lightweight fallback: upsert minimal taxon records from profile data.

    This ensures every taxon_id seen in a sample has at least a skeleton
    record in the `taxa` collection, even if load_taxonomy.py has not been
    run yet or hasn't been refreshed recently.

    Only creates new records ($setOnInsert) — never overwrites existing
    taxonomy data or clinical_notes populated by load_taxonomy.py.
    """

    seen: dict[int, dict[str, Any]] = {}
    for p in profiles:
        for entry in p.get("profile", []):
            taxon_id = entry.get("taxon_id")
            if taxon_id is None or taxon_id in seen:
                continue
            seen[taxon_id] = {
                "name": entry.get("name"),
                "rank": entry.get("rank"),
                "superkingdom": entry.get("superkingdom"),
            }

    if not seen:
        return

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
                        # Full lineage fields absent — indicates needs refresh
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
                        "taxdump_version": None,  # None = not yet loaded from dump
                        "updated_at": None,
                    }
                },
                upsert=True,
            )
        )

    await db["taxa"].bulk_write(ops, ordered=False)


async def _process_one_metaval_result(
    r: MetavalResult,
    case_object_id: ObjectId,
    db: AsyncIOMotorDatabase,
    now: datetime,
) -> None:
    """Upload blobs and insert a single metaval result document."""
    from app.database import get_blob_store

    blob_store = get_blob_store()

    existing_sample: dict | None = await db["samples"].find_one(
        {
            "case_id": case_object_id,
            "sample_id": r.sample_name,
        }
    )
    sample_object_id = existing_sample["_id"] if existing_sample else None

    async def _upload_igv(org: Any) -> dict:
        igv_key = None
        if not org.igv_too_large and org.igv_file_path:
            igv_key = (
                f"igv/{case_object_id}/{r.sample_name}/"
                f"{r.classifier}/{org.organism_name}.html"
            )
            html = Path(org.igv_file_path).read_text(encoding="utf-8")
            await blob_store.put(igv_key, html)
        return {
            "organism_name": org.organism_name,
            "igv_key": igv_key,
            "igv_file_size_bytes": org.igv_file_size_bytes,
            "igv_too_large": org.igv_too_large,
        }

    organisms = list(await asyncio.gather(*[_upload_igv(org) for org in r.organisms]))

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
                f"verification_data/{case_object_id}/{r.sample_name}/"
                f"{r.classifier}/{r.taxon_name}_{vd.type}.fa"
            )
            content = Path(vd.path).read_text(encoding="utf-8")
            await blob_store.put(blob_key, content)
            vd_store["blob_key"] = blob_key
    elif vd.type == "raw_reads":
        for read_num, path_val in [
            ("1", vd.read_1_path),
            ("2", vd.read_2_path),
        ]:
            if path_val and Path(path_val).exists():
                blob_key = (
                    f"verification_data/{case_object_id}/{r.sample_name}/"
                    f"{r.classifier}/{r.taxon_name}_read_{read_num}.fa"
                )
                content = Path(path_val).read_text(encoding="utf-8")
                await blob_store.put(blob_key, content)
                vd_store[f"read_{read_num}_key"] = blob_key

    await db["metaval_results"].insert_one(
        {
            "case_id": case_object_id,
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
    )


async def ingest_case(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    pipeline_info: PipelineInfoOutput = read_pipeline_info(request.pipeline_info_path)
    qc_data: MultiQCRaw = read_multiqc(request.multiqc_path)

    existing_case = await db["cases"].find_one({"case_id": request.case_id})
    if existing_case:
        raise ValueError(
            f"Case '{request.case_id}' already exists. "
            f"Delete the existing case first, or use a unique case_id."
        )

    classifier_docs = []
    for clf in request.classifiers:
        classifier_docs.append({"name": clf.name, "db": clf.db, "krona": None})

    case_doc = {
        "case_id": request.case_id,
        "order_date": request.order_date.isoformat() if request.order_date else None,
        "ingested_at": now,
        "sample_ids": [],
        "classifiers": classifier_docs,
        "has_krona": any(clf.krona for clf in request.classifiers),
        "pipeline_info": pipeline_info.model_dump(),
        "analysis_type": request.analysis_type.value if request.analysis_type else None,
        "sequencing_platform": request.sequencing_platform.value
        if request.sequencing_platform
        else None,
        "review": {
            "reviewed": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes": None,
        },
    }
    case_result = await db["cases"].insert_one(case_doc)
    case_object_id = case_result.inserted_id

    async def _upload_krona(clf: Any) -> dict:
        if clf.krona:
            await _store_krona(case_object_id, clf.name, clf.krona)
            return {"name": clf.name, "db": clf.db, "krona_id": clf.name}
        return {"name": clf.name, "db": clf.db, "krona_id": None}

    updated_classifiers = list(
        await asyncio.gather(*[_upload_krona(clf) for clf in request.classifiers])
    )

    await db["cases"].update_one(
        {"_id": case_object_id},
        {"$set": {"classifiers": updated_classifiers}},
    )

    # Fix 1: load each taxpasta file once, keyed by path
    import pandas as pd

    taxpasta_cache: dict[str, pd.DataFrame] = {}
    for clf in request.classifiers:
        if clf.taxpasta not in taxpasta_cache:
            taxpasta_cache[clf.taxpasta] = load_taxpasta(clf.taxpasta)

    sample_names = [s.sample_id for s in request.samples if s.sample_type == "sample"]
    sample_count = len([s for s in request.samples if s.sample_type == "sample"])
    control_count = len(
        [
            s
            for s in request.samples
            if s.sample_type in ("positive_ctrl", "negative_ctrl")
        ]
    )

    # Fix 2 + 3: build all sample docs first; accumulate profiles for one bulk taxa upsert
    sample_docs: list[dict] = []
    all_profiles: list[dict] = []

    for s in request.samples:
        subject_object_id = None
        if s.subject_id:
            subject_object_id = await _upsert_subject(db, s.subject_id)

        profiles = []
        classifier_qc = {}

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
            clf_qc = _extract_classifier_qc(qc_data, clf.name, col)
            if clf_qc:
                classifier_qc[clf.name] = clf_qc

        all_profiles.extend(profiles)
        base_qc = _extract_base_qc(qc_data, s.sample_id)

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
                "case_id": case_object_id,
                "case_id_str": request.case_id,
                "sample_id": s.sample_id,
                "sample_source": s.sample_source,
                "order_date": request.order_date.isoformat()
                if request.order_date
                else None,
                "subject_id": subject_object_id,
                "sample_type": s.sample_type,
                "material": s.material,
                "taxprofiler": {
                    **base_qc,
                    "classifiers": classifier_qc,
                    "pipeline_info": pipeline_info.model_dump(),
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

    # Single taxa upsert across all samples
    await _upsert_taxa_from_profiles(all_profiles, db)

    # Batch insert all samples in one round-trip
    insert_result = await db["samples"].insert_many(sample_docs)
    sample_ids = list(insert_result.inserted_ids)

    await db["cases"].update_one(
        {"_id": case_object_id},
        {
            "$set": {
                "sample_ids": sample_ids,
                "sample_count": sample_count,
                "control_count": control_count,
                "sample_names": sample_names,
            }
        },
    )

    if request.metaval:
        metaval_data: MetavalOutput = read_metaval(request.metaval.metaval_dir)
        metaval_results = metaval_data.results

        if metaval_data.pipeline_info:
            await db["cases"].update_one(
                {"_id": case_object_id},
                {
                    "$set": {
                        "metaval_pipeline_info": metaval_data.pipeline_info.model_dump()
                    }
                },
            )

        # Fix 4: fan out all metaval results concurrently
        await asyncio.gather(
            *[
                _process_one_metaval_result(r, case_object_id, db, now)
                for r in metaval_results
            ]
        )

    return {
        "case_id": request.case_id,
        "case_object_id": str(case_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids": [str(sid) for sid in sample_ids],
    }


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
