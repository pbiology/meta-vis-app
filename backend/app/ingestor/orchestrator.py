# app/ingestor/orchestrator.py

from datetime import datetime, timezone
from pathlib import Path
import asyncio
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Any
from pymongo import UpdateOne

from app.models.sample import IngestRequest
from app.ingestor.taxpasta_reader import read_taxpasta
from app.ingestor.multiqc_reader import read_multiqc
from app.ingestor.pipeline_info_reader import read_pipeline_info
from app.ingestor.metaval_reader import read_metaval


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


async def _compute_outbreak_taxa(
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


async def ingest_case(request: IngestRequest, db: AsyncIOMotorDatabase) -> dict:
    now = datetime.now(timezone.utc)

    pipeline_info = read_pipeline_info(request.pipeline_info_path)
    qc_data = read_multiqc(request.multiqc_path)

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
        "pipeline_info": pipeline_info,
        "review": {
            "reviewed": False,
            "reviewed_by": None,
            "reviewed_at": None,
            "notes": None,
        },
    }
    case_result = await db["cases"].insert_one(case_doc)
    case_object_id = case_result.inserted_id

    async def _upload_krona(clf):
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

    sample_ids = []
    sample_names = [s.sample_id for s in request.samples if s.sample_type == "sample"]
    sample_count = len([s for s in request.samples if s.sample_type == "sample"])
    control_count = len(
        [
            s
            for s in request.samples
            if s.sample_type in ("positive_ctrl", "negative_ctrl")
        ]
    )

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
            profile = read_taxpasta(clf.taxpasta, col)
            profiles.append(
                {
                    "classifier": clf.name,
                    "classifier_db": clf.db,
                    "profile": profile,
                }
            )
            clf_qc = _extract_classifier_qc(qc_data, clf.name, col)
            if clf_qc:
                classifier_qc[clf.name] = clf_qc

        await _upsert_taxa_from_profiles(profiles, db)
        base_qc = _extract_base_qc(qc_data, s.sample_id)

        # Compute outbreak_taxa from profiles using active configs
        outbreak_taxa = await _compute_outbreak_taxa(profiles)

        # Flat set of all taxon IDs across all classifiers — used for fast
        # pathogen matching at query time without unwinding nested arrays.
        all_taxon_ids: list[int] = list(
            {
                entry["taxon_id"]
                for p in profiles
                for entry in p.get("profile", [])
                if isinstance(entry, dict) and entry.get("taxon_id") is not None
            }
        )

        sample_doc = {
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
                "pipeline_info": pipeline_info,
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

        sample_result = await db["samples"].insert_one(sample_doc)
        sample_ids.append(sample_result.inserted_id)

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
        metaval_data = read_metaval(request.metaval.metaval_dir)
        metaval_results = metaval_data["results"]

        if metaval_data.get("pipeline_info"):
            await db["cases"].update_one(
                {"_id": case_object_id},
                {"$set": {"metaval_pipeline_info": metaval_data["pipeline_info"]}},
            )

        from app.database import get_blob_store

        for r in metaval_results:
            existing_sample: dict | None = await db["samples"].find_one(
                {
                    "case_id": case_object_id,
                    "sample_id": r["sample_name"],
                }
            )
            sample_object_id = existing_sample["_id"] if existing_sample else None

            # Upload IGV HTML files
            async def _upload_igv(org):
                igv_key = None
                if not org.get("igv_too_large") and org.get("igv_file_path"):
                    igv_key = (
                        f"igv/{case_object_id}/{r['sample_name']}/"
                        f"{r['classifier']}/{org['organism_name']}.html"
                    )
                    html = Path(org["igv_file_path"]).read_text(encoding="utf-8")
                    await get_blob_store().put(igv_key, html)
                return {
                    "organism_name": org["organism_name"],
                    "igv_key": igv_key,
                    "igv_file_size_bytes": org["igv_file_size_bytes"],
                    "igv_too_large": org["igv_too_large"],
                }

            organisms = list(
                await asyncio.gather(*[_upload_igv(org) for org in r["organisms"]])
            )

            # Upload verification data (scaffolds, contigs, or raw reads)
            vd = r.get("verification_data", {})
            vd_type = vd.get("type")
            vd_store = {
                "type": vd_type,
                "count": vd.get("count", 0),
                "avg_length": vd.get("avg_length", 0),
                "file_count": vd.get("file_count", 1),
            }

            if vd_type in ("scaffolds", "contigs"):
                fasta_path = vd.get("path")
                if fasta_path and Path(fasta_path).exists():
                    blob_key = (
                        f"verification_data/{case_object_id}/{r['sample_name']}/"
                        f"{r['classifier']}/{r['taxon_name']}_{vd_type}.fa"
                    )
                    content = Path(fasta_path).read_text(encoding="utf-8")
                    await get_blob_store().put(blob_key, content)
                    vd_store["blob_key"] = blob_key
            elif vd_type == "raw_reads":
                for read_num, path_key in [("1", "read_1_path"), ("2", "read_2_path")]:
                    fasta_path = vd.get(path_key)
                    if fasta_path and Path(fasta_path).exists():
                        blob_key = (
                            f"verification_data/{case_object_id}/{r['sample_name']}/"
                            f"{r['classifier']}/{r['taxon_name']}_read_{read_num}.fa"
                        )
                        content = Path(fasta_path).read_text(encoding="utf-8")
                        await get_blob_store().put(blob_key, content)
                        vd_store[f"read_{read_num}_key"] = blob_key

            await db["metaval_results"].insert_one(
                {
                    "case_id": case_object_id,
                    "sample_id": sample_object_id,
                    "sample_name": r["sample_name"],
                    "classifier": r["classifier"],
                    "taxon_id": r["taxon_id"],
                    "taxon_name": r["taxon_name"],
                    "organisms": organisms,
                    "blast": r["blast"],
                    "verification_data": vd_store,
                    "ingested_at": now,
                }
            )

    return {
        "case_id": request.case_id,
        "case_object_id": str(case_object_id),
        "samples_ingested": len(sample_ids),
        "sample_ids": [str(sid) for sid in sample_ids],
    }


def _extract_classifier_qc(qc_data: dict, classifier_name: str, col: str) -> dict:
    """Extract classifier-specific QC stats from multiqc data."""

    if classifier_name == "kraken2":
        key = col.split(".kraken2")[0]
        records = qc_data.get("kraken2", {}).get(key)
    elif classifier_name == "centrifuge":
        records = qc_data.get("centrifuge", {}).get(col)
    else:
        return {}

    if not records or not isinstance(records, list):
        return {}

    unclassified_reads = sum(
        r["counts_rooted"] for r in records if r.get("rank_code") == "U"
    )
    root_records = [r for r in records if r.get("rank_code") == "R"]
    num_species = len([r for r in records if r.get("rank_code") == "S"])
    num_genera = len([r for r in records if r.get("rank_code") == "G"])

    if root_records:
        classified_reads = root_records[0]["counts_rooted"]
    else:
        classified_reads = sum(
            r["counts_rooted"] for r in records if r.get("rank_code") == "S"
        )

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


def _extract_base_qc(qc_data: dict, sample_id: str) -> dict:
    """Extract classifier-agnostic QC stats: fastp, bowtie2, fastqc."""
    stats = {}

    fastp_all = qc_data.get("fastp", {})
    bowtie2_all = qc_data.get("bowtie2", {})

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

    fastqc_all = qc_data.get("fastqc", {})
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

        def _avg(lanes, field):
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
