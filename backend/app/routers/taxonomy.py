# app/routers/taxonomy.py

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.auth.utils import get_current_user

router = APIRouter()

SUPERKINGDOM_TAXIDS = {2, 2157, 2759, 10239}
SUPERKINGDOM_NAMES  = {
    2:     "Bacteria",
    2157:  "Archaea",
    2759:  "Eukaryota",
    10239: "Viruses",
}


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class TaxonomyLoadRequest(BaseModel):
    name:                str
    ncbi_taxonomy_date:  str        # e.g. "2024-11-01"
    nodes_raw:           List[str]  # raw lines from nodes.dmp
    names_raw:           List[str]  # raw lines from names.dmp


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_nodes(lines: List[str]) -> dict[int, tuple[int, str]]:
    """
    Parse nodes.dmp lines into taxon_id -> (parent_id, rank).
    """
    nodes: dict[int, tuple[int, str]] = {}
    for line in lines:
        parts = line.split("\t|\t")
        if len(parts) < 3:
            continue
        taxon_id  = int(parts[0].strip())
        parent_id = int(parts[1].strip())
        rank      = parts[2].strip()
        nodes[taxon_id] = (parent_id, rank)
    return nodes


def parse_names(lines: List[str]) -> dict[int, dict]:
    """
    Parse names.dmp lines and extract scientific name and common name per taxon.
    Returns taxon_id -> {"name": str, "common_name": str | None}
    """
    scientific: dict[int, str]           = {}
    common:     dict[int, str]           = {}

    for line in lines:
        parts = line.split("\t|\t")
        if len(parts) < 4:
            continue
        taxon_id   = int(parts[0].strip())
        name_txt   = parts[1].strip()
        name_class = parts[3].rstrip("\t|").strip()

        if name_class == "scientific name":
            scientific[taxon_id] = name_txt
        elif name_class == "genbank common name" and taxon_id not in common:
            common[taxon_id] = name_txt
        elif name_class == "common name" and taxon_id not in common:
            common[taxon_id] = name_txt

    result: dict[int, dict] = {}
    all_ids = set(scientific) | set(common)
    for tid in all_ids:
        result[tid] = {
            "name":        scientific.get(tid),
            "common_name": common.get(tid),
        }
    return result


def resolve_superkingdom(
    taxon_id: int,
    nodes: dict[int, tuple[int, str]],
) -> Optional[str]:
    """
    Walk up the taxonomy tree until a superkingdom node is found.
    """
    visited: set[int] = set()
    current = taxon_id

    while current not in visited:
        if current in SUPERKINGDOM_TAXIDS:
            return SUPERKINGDOM_NAMES[current]
        if current not in nodes:
            return None
        parent_id, _ = nodes[current]
        if parent_id == current:
            return None
        visited.add(current)
        current = parent_id

    return None


def build_node_docs(
    nodes: dict[int, tuple[int, str]],
    names: dict[int, dict],
    taxonomy_db_id,
) -> list[dict]:
    """
    Join nodes and names into the final list of documents for MongoDB.
    """
    docs = []
    for taxon_id, (parent_id, rank) in nodes.items():
        name_entry  = names.get(taxon_id, {})
        superkingdom = resolve_superkingdom(taxon_id, nodes)
        docs.append({
            "taxonomy_db_id": taxonomy_db_id,
            "taxon_id":       taxon_id,
            "parent_id":      parent_id,
            "rank":           rank,
            "name":           name_entry.get("name"),
            "common_name":    name_entry.get("common_name"),
            "superkingdom":   superkingdom,
        })
    return docs


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/taxonomy/load")
async def load_taxonomy(
    request: TaxonomyLoadRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        nodes = parse_nodes(request.nodes_raw)
        names = parse_names(request.names_raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse taxonomy files: {e}")

    now = datetime.now(timezone.utc)

    # Upsert the taxonomy_databases record
    tax_doc = {
        "name":               request.name,
        "ncbi_taxonomy_date": request.ncbi_taxonomy_date,
        "loaded_at":          now,
        "node_count":         len(nodes),
    }
    result = await db["taxonomy_databases"].find_one_and_replace(
        {"name": request.name},
        tax_doc,
        upsert=True,
        return_document=True,
    )
    taxonomy_db_id = result["_id"]

    # Delete existing nodes for this taxonomy, then bulk insert
    await db["taxonomy_nodes"].delete_many({"taxonomy_db_id": taxonomy_db_id})

    docs = build_node_docs(nodes, names, taxonomy_db_id)

    batch_size = 10_000
    for i in range(0, len(docs), batch_size):
        await db["taxonomy_nodes"].insert_many(
            docs[i : i + batch_size], ordered=False
        )

    # Ensure compound index
    await db["taxonomy_nodes"].create_index(
        [("taxonomy_db_id", 1), ("taxon_id", 1)], unique=True
    )

    return {
        "name":               request.name,
        "taxonomy_db_id":     str(taxonomy_db_id),
        "ncbi_taxonomy_date": request.ncbi_taxonomy_date,
        "node_count":         len(docs),
    }


@router.get("/taxonomy")
async def list_taxonomies(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    docs = await db["taxonomy_databases"].find().to_list(length=100)
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs