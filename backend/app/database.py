from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
)
from app.config import settings

client: AsyncIOMotorClient | None = None
_blob_store = None


def _build_mongo_url() -> str:
    if settings.mongodb_username and settings.mongodb_password:
        base = (
            f"mongodb://{settings.mongodb_username}:{settings.mongodb_password}"
            f"@{settings.mongodb_host}:{settings.mongodb_port}"
            f"/{settings.mongodb_db_name}?authSource={settings.mongodb_auth_source}"
        )
    else:
        base = f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}"
    if settings.mongodb_direct_connection:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}directConnection=true"
    return base


async def connect_db():
    global client, _blob_store
    client = AsyncIOMotorClient(_build_mongo_url())
    await _ensure_indexes()
    from app.blob_store import make_blob_store

    _blob_store = make_blob_store(client[settings.mongodb_db_name])


def get_blob_store():
    return _blob_store


def get_client() -> AsyncIOMotorClient:
    """Return the shared Motor client (used for transaction sessions)."""
    if client is None:
        raise RuntimeError("Database not connected")
    return client


async def _ensure_indexes():
    db = client[settings.mongodb_db_name]

    # users — preferences store keyed by Keycloak `sub`. Any legacy documents
    # (with `password_hash` / `role`) are wiped on startup; identity has moved
    # to Keycloak and the old schema is incompatible.
    await db["users"].delete_many({"sub": {"$exists": False}})
    await db["users"].create_index("sub", unique=True)

    # cases — fast lookup by case_id and filtering by order_date
    await db["cases"].create_index("case_id", unique=True)
    await db["cases"].create_index("ingested_at")
    await db["cases"].create_index("order_date")
    await db["cases"].create_index("review.reviewed")
    await db["cases"].create_index(
        [
            ("review.reviewed", 1),
            ("order_date", -1),
            ("ingested_at", -1),
        ]
    )

    # samples — fast lookup by case, by case+type+material (NTC profiles),
    # and by viral taxa fields used in the outbreak aggregation pipeline
    await db["samples"].create_index([("case_id", 1), ("sample_id", 1)])
    await db["samples"].create_index(
        [("case_id", 1), ("sample_type", 1), ("material", 1)]
    )
    await db["samples"].create_index("profiles.profile.superkingdom")
    await db["samples"].create_index("profiles.profile.taxon_id")
    await db["samples"].create_index([("order_date", -1), ("ingested_at", -1)])
    await db["samples"].create_index(
        [("sample_type", 1), ("order_date", -1), ("ingested_at", -1)]
    )
    await db["samples"].create_index(
        [("sample_id", 1), ("order_date", -1), ("ingested_at", -1)]
    )

    # blobs — used by MongoBlobStore when object storage is not configured
    await db["blobs"].create_index("key", unique=True)

    # metaval_results — fast lookup by sample and case
    await db["metaval_results"].create_index([("case_id", 1), ("sample_id", 1)])

    # outbreak_ignorelist — fast lookup by taxon_id and filtering by superkingdom
    await db["outbreak_ignorelist"].create_index("taxon_id", unique=True)
    await db["outbreak_ignorelist"].create_index("superkingdom")

    # samples — fast lookup of outbreak_taxa for queries
    await db["samples"].create_index("outbreak_taxa.superkingdom")
    await db["samples"].create_index("outbreak_taxa.taxon_id")

    # samples — fast pathogen detection using pre-computed flat taxon ID array
    await db["samples"].create_index("all_taxon_ids")

    # known_pathogens — fast lookup by taxon_id
    await db["known_pathogens"].create_index("taxon_id", unique=True)

    # ntc_ignorelist — fast lookup by taxon_id
    await db["ntc_ignorelist"].create_index("taxon_id", unique=True)

    # samples — compound index for NTC trends query (sample_type + material + order_date)
    await db["samples"].create_index(
        [("sample_type", 1), ("material", 1), ("order_date", -1)],
        name="ntc_trends_lookup",
    )

    # ntc_known_contaminants — fast lookup by taxon_id
    await db["ntc_known_contaminants"].create_index("taxon_id", unique=True)

    # subjects — fast lookup by subject_id
    await db["subjects"].create_index("subject_id", unique=True)

    # taxa — reference collection populated by load_taxonomy.py
    await db["taxa"].create_index("taxon_id", unique=True)
    await db["taxa"].create_index("superkingdom")
    await db["taxa"].create_index("name")

    # audit_log — append-only; no TTL (clinical audit logs must not auto-expire)
    await db["audit_log"].create_index([("timestamp", -1)])
    await db["audit_log"].create_index([("actor", 1), ("timestamp", -1)])
    await db["audit_log"].create_index([("action", 1), ("timestamp", -1)])
    await db["audit_log"].create_index(
        [("resource_type", 1), ("resource_id", 1), ("timestamp", -1)]
    )


async def close_db():
    global client
    if _blob_store is not None:
        await _blob_store.close()
    if client:
        client.close()


def get_db() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("Database not connected")
    return client[settings.mongodb_db_name]
