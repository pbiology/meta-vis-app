# app/routers/taxa.py

import asyncio
from datetime import date, timedelta, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
import httpx
import time

from app.database import get_db
from app.auth.utils import get_current_user, require_role
from app.config import settings

router = APIRouter(prefix="/taxa", tags=["taxa"])


class ClinicalNotesPayload(BaseModel):
    clinical_notes: Optional[str] = None


# Simple in-memory cache: taxon_id -> (timestamp, data)
_links_cache: dict[int, tuple[float, list]] = {}
_literature_cache: dict[int, tuple[float, list]] = {}
_bvbrc_genomes_cache: dict[int, tuple[float, dict]] = {}
_bvbrc_specialty_cache: dict[int, tuple[float, dict]] = {}
LINKS_CACHE_TTL = 86400  # 24 hours — external links change rarely
LITERATURE_CACHE_TTL = 86400  # 24 hours — PubMed results change rarely
BVBRC_CACHE_TTL = 86400  # 24 hours — BV-BRC data changes rarely


@router.get(
    "/{taxon_id}/external_links",
    summary="Get curated external links for a taxon from NCBI",
)
async def get_external_links(
    taxon_id: int,
    _user: dict = Depends(get_current_user),
):
    now = time.time()
    if taxon_id in _links_cache:
        ts, data = _links_cache[taxon_id]
        if now - ts < LINKS_CACHE_TTL:
            return {"taxon_id": taxon_id, "links": data}

    url = f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{taxon_id}/links"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            raw = resp.json()
    except Exception:
        return {"taxon_id": taxon_id, "links": []}

    # Response is a flat object: {"tax_id": "...", "wikipedia": "https://...", ...}
    # Convert to a list of {name, url} dicts, skipping the tax_id field.
    links = [
        {"name": key.replace("_", " ").title(), "url": value}
        for key, value in raw.items()
        if key != "tax_id" and isinstance(value, str)
    ]

    _links_cache[taxon_id] = (now, links)
    return {"taxon_id": taxon_id, "links": links}


EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@router.get(
    "/{taxon_id}/literature",
    summary="Fetch recent clinical literature from PubMed for a taxon",
)
async def get_taxon_literature(
    taxon_id: int,
    max_results: int = Query(default=5, ge=1, le=20),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Queries NCBI PubMed for recent case reports and outbreak publications
    related to this taxon. Results are cached for 24 hours.

    Uses the taxon name from the local taxa collection to build a reliable
    PubMed query, combining it with the NCBI taxonomy ID for best coverage.
    Falls back to an empty list on any network error rather than raising.
    """
    now = time.time()
    cache_key = (taxon_id, max_results)

    # Reuse a separate cache keyed by (taxon_id, max_results)
    _lit_cache: dict = _literature_cache  # alias for brevity
    if cache_key in _lit_cache:
        ts, data, cached_query = _lit_cache[cache_key]
        if now - ts < LITERATURE_CACHE_TTL:
            return {
                "taxon_id": taxon_id,
                "article_count": len(data),
                "articles": data,
                "pubmed_query": cached_query,
            }

    # Resolve the taxon name from our local taxa collection
    taxon_doc = await db["taxa"].find_one({"taxon_id": taxon_id}, {"name": 1, "_id": 0})
    organism_name = taxon_doc["name"] if taxon_doc else str(taxon_id)

    # Build a PubMed query that targets clinical publications:
    # - Match by both NCBI organism tag and free-text name for best recall
    # - Filter to Case Reports, Disease Outbreaks, or Pathogenicity subheadings
    search_query = (
        f'(txid{taxon_id}[Organism] OR "{organism_name}"[Organism] OR "{organism_name}"[All Fields]) '
        f'AND ("Case Reports"[Publication Type] OR "Disease Outbreaks"[MeSH Terms] '
        f'OR "Pathogenicity"[MeSH Subheading])'
    )

    # Optional NCBI API key: raises rate limit from 3 req/s to 10 req/s
    base_params: dict = (
        {"api_key": settings.ncbi_api_key} if settings.ncbi_api_key else {}
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            # Step 1: ESearch — get PubMed IDs matching the query
            search_res = await http.get(
                f"{EUTILS_BASE}/esearch.fcgi",
                params={
                    **base_params,
                    "db": "pubmed",
                    "term": search_query,
                    "retmode": "json",
                    "retmax": max_results,
                    "sort": "date",
                },
            )
            search_res.raise_for_status()
            pmids: list[str] = (
                search_res.json().get("esearchresult", {}).get("idlist", [])
            )

            if not pmids:
                _lit_cache[cache_key] = (now, [], search_query)
                return {
                    "taxon_id": taxon_id,
                    "article_count": 0,
                    "articles": [],
                    "pubmed_query": search_query,
                }

            # Step 2: ESummary — fetch title, journal, and date for each PMID
            summary_res = await http.get(
                f"{EUTILS_BASE}/esummary.fcgi",
                params={
                    **base_params,
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "json",
                },
            )
            summary_res.raise_for_status()
            result_dict = summary_res.json().get("result", {})

            articles = [
                {
                    "pmid": pmid,
                    "title": result_dict[pmid].get("title", "No title available"),
                    "journal": result_dict[pmid].get(
                        "fulljournalname", "Unknown Journal"
                    ),
                    "pub_date": result_dict[pmid].get("pubdate", "Unknown date"),
                    "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                }
                for pmid in pmids
                if pmid in result_dict
            ]

    except Exception:
        # Network errors, timeouts, or unexpected response shapes — degrade gracefully
        return {
            "taxon_id": taxon_id,
            "article_count": 0,
            "articles": [],
            "pubmed_query": None,
        }

    _lit_cache[cache_key] = (now, articles, search_query)
    return {
        "taxon_id": taxon_id,
        "article_count": len(articles),
        "articles": articles,
        "pubmed_query": search_query,
    }


BVBRC_BASE = "https://www.bv-brc.org/api"


@router.get(
    "/{taxon_id}/bvbrc/genomes",
    summary="Get BV-BRC genome summary for a taxon",
)
async def get_bvbrc_genomes(
    taxon_id: int,
    _user: dict = Depends(get_current_user),
) -> dict:
    """
    Fetches genome metadata from BV-BRC and returns an aggregated summary:
    total genome count, top isolation sources, top countries, and AMR phenotypes.

    Uses taxon_lineage_ids so that strain-level genomes are included for
    species-level queries. Results cached 24 hours. Degrades gracefully on
    any network error.
    """
    now = time.time()
    if taxon_id in _bvbrc_genomes_cache:
        ts, data = _bvbrc_genomes_cache[taxon_id]
        if now - ts < BVBRC_CACHE_TTL:
            return data

    bvbrc_url = f"https://www.bv-brc.org/view/Taxonomy/{taxon_id}#view_tab=genomes"
    empty: dict = {
        "taxon_id": taxon_id,
        "total_genomes": 0,
        "isolation_sources": [],
        "countries": [],
        "amr_phenotypes": [],
        "bvbrc_url": bvbrc_url,
    }

    url = (
        f"{BVBRC_BASE}/genome/"
        f"?eq(taxon_lineage_ids,{taxon_id})"
        f"&select(genome_id,isolation_source,isolation_country,antimicrobial_resistance)"
        f"&limit(1000)"
        f"&http_accept=application/json"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            genomes: list[dict] = resp.json()
    except Exception:
        return empty

    if not genomes:
        _bvbrc_genomes_cache[taxon_id] = (now, empty)
        return empty

    source_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    amr_counts: dict[str, int] = {}

    for g in genomes:
        src = g.get("isolation_source")
        if src:
            source_counts[src] = source_counts.get(src, 0) + 1

        country = g.get("isolation_country")
        if country:
            country_counts[country] = country_counts.get(country, 0) + 1

        # antimicrobial_resistance is a list of drug names for resistant genomes
        for drug in g.get("antimicrobial_resistance") or []:
            amr_counts[drug] = amr_counts.get(drug, 0) + 1

    result: dict = {
        "taxon_id": taxon_id,
        "total_genomes": len(genomes),
        "isolation_sources": [
            {"source": k, "count": v}
            for k, v in sorted(
                source_counts.items(), key=lambda kv: kv[1], reverse=True
            )
        ][:10],
        "countries": [
            {"country": k, "count": v}
            for k, v in sorted(
                country_counts.items(), key=lambda kv: kv[1], reverse=True
            )
        ][:10],
        "amr_phenotypes": [
            {"antibiotic": k, "count": v}
            for k, v in sorted(amr_counts.items(), key=lambda kv: kv[1], reverse=True)
        ],
        "bvbrc_url": bvbrc_url,
    }

    _bvbrc_genomes_cache[taxon_id] = (now, result)
    return result


@router.get(
    "/{taxon_id}/bvbrc/specialty_genes",
    summary="Get BV-BRC specialty genes (AMR + virulence) for a taxon",
)
async def get_bvbrc_specialty_genes(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    """
    Fetches specialty gene (AMR genes, virulence factors) and AMR phenotype data
    from BV-BRC for bacterial taxa. For viral taxa (superkingdom = "Viruses"),
    returns an empty result immediately without querying BV-BRC, as those
    endpoints cover bacteria only.

    Uses asyncio.gather to run specialty_gene and genome_amr calls concurrently.
    Results cached 24 hours. Degrades gracefully on any network error.
    """
    now = time.time()
    if taxon_id in _bvbrc_specialty_cache:
        ts, data = _bvbrc_specialty_cache[taxon_id]
        if now - ts < BVBRC_CACHE_TTL:
            return data

    taxon_doc = await db["taxa"].find_one(
        {"taxon_id": taxon_id}, {"superkingdom": 1, "_id": 0}
    )
    is_viral: bool = (taxon_doc or {}).get("superkingdom") == "Viruses"

    bvbrc_url = (
        f"https://www.bv-brc.org/view/Taxonomy/{taxon_id}#view_tab=specialtyGenes"
    )
    empty: dict = {
        "taxon_id": taxon_id,
        "is_viral": is_viral,
        "amr_genes": [],
        "virulence_factors": [],
        "amr_phenotypes": [],
        "bvbrc_url": bvbrc_url,
    }

    if is_viral:
        _bvbrc_specialty_cache[taxon_id] = (now, empty)
        return empty

    # BV-BRC sp_gene endpoint (renamed from specialty_gene in their API).
    # Property filter via in() does not work for multi-word text values in
    # BV-BRC's SOLR index, so we fetch all records and filter in Python.
    # genome_amr uses taxon_id (taxon_lineage_ids is not an indexed field there).
    sg_url = (
        f"{BVBRC_BASE}/sp_gene/"
        f"?eq(taxon_id,{taxon_id})"
        f"&select(gene,property,source,product,antibiotics,antibiotics_class,pmid)"
        f"&limit(500)"
        f"&http_accept=application/json"
    )
    amr_url = (
        f"{BVBRC_BASE}/genome_amr/"
        f"?eq(taxon_id,{taxon_id})"
        f"&select(antibiotic,resistant_phenotype,evidence)"
        f"&limit(1000)"
        f"&http_accept=application/json"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            sg_resp, amr_resp = await asyncio.gather(
                http.get(sg_url, headers={"Accept": "application/json"}),
                http.get(amr_url, headers={"Accept": "application/json"}),
            )
            sg_resp.raise_for_status()
            amr_resp.raise_for_status()
            specialty_genes: list[dict] = sg_resp.json()
            amr_records: list[dict] = amr_resp.json()
    except Exception:
        return empty

    # Deduplicate by (gene, property) and split into AMR vs virulence.
    # Other property values (Transporter, Drug Target, Human Homolog) are skipped.
    seen: set[tuple[str, str]] = set()
    amr_genes: list[dict] = []
    virulence_factors: list[dict] = []

    for g in specialty_genes:
        gene = g.get("gene") or ""
        prop = g.get("property") or ""
        if prop not in {"Antibiotic Resistance", "Virulence Factor"}:
            continue
        key = (gene, prop)
        if key in seen:
            continue
        seen.add(key)
        entry: dict = {
            "gene": gene,
            "source": g.get("source"),
            "product": g.get("product"),
            "antibiotics": g.get("antibiotics") or [],
            "antibiotics_class": g.get("antibiotics_class"),
            "pmid": g.get("pmid") or [],
        }
        if prop == "Antibiotic Resistance":
            amr_genes.append(entry)
        else:
            virulence_factors.append(entry)

    # Aggregate AMR phenotypes: count resistant vs susceptible per antibiotic
    phenotype_counts: dict[str, dict[str, int]] = {}
    for rec in amr_records:
        antibiotic = rec.get("antibiotic")
        phenotype = (rec.get("resistant_phenotype") or "").lower()
        if not antibiotic:
            continue
        if antibiotic not in phenotype_counts:
            phenotype_counts[antibiotic] = {"resistant": 0, "susceptible": 0}
        if "resistant" in phenotype and "not" not in phenotype:
            phenotype_counts[antibiotic]["resistant"] += 1
        elif "susceptible" in phenotype:
            phenotype_counts[antibiotic]["susceptible"] += 1

    amr_phenotypes: list[dict] = [
        {
            "antibiotic": drug,
            "resistant": counts["resistant"],
            "susceptible": counts["susceptible"],
        }
        for drug, counts in sorted(
            phenotype_counts.items(),
            key=lambda kv: kv[1]["resistant"],
            reverse=True,
        )
    ]

    result: dict = {
        "taxon_id": taxon_id,
        "is_viral": False,
        "amr_genes": amr_genes,
        "virulence_factors": virulence_factors,
        "amr_phenotypes": amr_phenotypes,
        "bvbrc_url": bvbrc_url,
    }

    _bvbrc_specialty_cache[taxon_id] = (now, result)
    return result


@router.get("/{taxon_id}", summary="Get taxon reference data")
async def get_taxon(
    taxon_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await db["taxa"].find_one({"taxon_id": taxon_id}, {"_id": 0})
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Taxon {taxon_id} not found in the taxa collection. "
                "Run load_taxonomy.py to populate reference data."
            ),
        )
    # Flag to the frontend that this record has not been loaded from the
    # NCBI dump yet — only a skeleton from ingest-time fallback exists.
    doc["needs_taxonomy_refresh"] = doc.get("taxdump_version") is None
    return doc


@router.patch(
    "/{taxon_id}/clinical_notes",
    summary="Add or update clinical notes for a taxon",
)
async def update_clinical_notes(
    taxon_id: int,
    payload: ClinicalNotesPayload,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_role("writer", "admin")),
):
    now = datetime.now(timezone.utc)
    result = await db["taxa"].update_one(
        {"taxon_id": taxon_id},
        {
            "$set": {
                "clinical_notes": payload.clinical_notes,
                "clinical_notes_author": current_user["username"]
                if payload.clinical_notes
                else None,
                "clinical_notes_updated_at": now if payload.clinical_notes else None,
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Taxon {taxon_id} not found")
    return {"updated": True, "taxon_id": taxon_id}


@router.get(
    "/{taxon_id}/occurrences",
    summary="Cases and samples in which this taxon has been detected",
)
async def get_taxon_occurrences(
    taxon_id: int,
    window_days: int = Query(default=90, ge=7, le=365),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """
    Returns cases where this taxon was detected within a rolling time window,
    along with per-classifier read counts. Mirrors the sliding-window approach
    used by outbreak detection.
    """
    cutoff = (date.today() - timedelta(days=window_days)).isoformat()

    pipeline: list[dict] = [
        # Scope to the time window and samples that contain the taxon
        {
            "$match": {
                "order_date": {"$gte": cutoff},
                "all_taxon_ids": taxon_id,
            }
        },
        # Unwind profiles to find per-classifier read counts
        {"$unwind": "$profiles"},
        {"$unwind": "$profiles.profile"},
        {"$match": {"profiles.profile.taxon_id": taxon_id}},
        # Group per sample+classifier
        {
            "$group": {
                "_id": {
                    "sample_id": "$sample.sample_id",
                    "case_id_str": "$case_id_str",
                    "order_date": "$order_date",
                    "classifier": "$profiles.classifier",
                },
                "abundance": {"$max": "$profiles.profile.abundance"},
            }
        },
        # Roll up to case level
        {
            "$group": {
                "_id": {
                    "case_id_str": "$_id.case_id_str",
                    "order_date": "$_id.order_date",
                },
                "samples": {
                    "$push": {
                        "sample_id": "$_id.sample_id",
                        "classifier": "$_id.classifier",
                        "abundance": "$abundance",
                    }
                },
                "sample_count": {"$addToSet": "$_id.sample_id"},
            }
        },
        {"$sort": {"_id.order_date": -1}},
        {"$limit": 200},
        {
            "$project": {
                "_id": 0,
                "case_id": "$_id.case_id_str",
                "order_date": "$_id.order_date",
                "sample_count": {"$size": "$sample_count"},
                "samples": 1,
            }
        },
    ]

    cases = await db["samples"].aggregate(pipeline).to_list(length=200)

    return {
        "taxon_id": taxon_id,
        "window_days": window_days,
        "total_cases": len(cases),
        "cases": cases,
    }
