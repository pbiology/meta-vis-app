import logging
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import quote_plus

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)

from app.config import settings

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient | None = None
_blob_store = None


def _build_mongo_url() -> str:
    # Only reached when `mongodb_uri` is unset; the Settings validator
    # guarantees `mongodb_host` and `mongodb_db_name` are populated in that
    # branch, so the assert narrows the Optional for mypy without adding
    # runtime risk.
    assert settings.mongodb_host is not None, (
        "mongodb_host required when mongodb_uri unset"
    )
    username = settings.mongodb_username
    password = settings.mongodb_password
    if bool(username) != bool(password):
        raise ValueError(
            "MongoDB username and password must both be set or both be empty"
        )
    if username and password:
        user = quote_plus(username)
        pwd = quote_plus(password)
        auth_source = quote_plus(settings.mongodb_auth_source)
        base = (
            f"mongodb://{user}:{pwd}"
            f"@{settings.mongodb_host}:{settings.mongodb_port}"
            f"/{settings.mongodb_db_name}?authSource={auth_source}"
        )
    else:
        base = f"mongodb://{settings.mongodb_host}:{settings.mongodb_port}"
    if settings.mongodb_direct_connection:
        sep = "&" if "?" in base else "?"
        base = f"{base}{sep}directConnection=true"
    return base


def _redact_mongo_url(url: str) -> str:
    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)


async def connect_db():
    global client, _blob_store
    # Prefer a full URI when configured (production): it carries replicaSet,
    # tls, and seed-host params that the host/port/user/pass fields cannot
    # express. Otherwise fall back to building from parts (dev compose).
    url = settings.mongodb_uri or _build_mongo_url()
    logger.info("Connecting to MongoDB at %s", _redact_mongo_url(url))
    client = AsyncIOMotorClient(url)
    await _ensure_indexes()
    from app.blob_store import make_blob_store

    _blob_store = make_blob_store(client[settings.mongodb_db_name])

    # Verify the audit pipeline end-to-end. Must run after _ensure_indexes()
    # so the audit_log indexes exist before we write the sentinel.
    from app.audit import audit_selftest

    await audit_selftest(client[settings.mongodb_db_name])


@asynccontextmanager
async def maybe_transaction(
    mongo_client: AsyncIOMotorClient,
) -> AsyncIterator[Optional[AsyncIOMotorClientSession]]:
    """Yield a transactional session, or None when transactions are disabled.

    Motor accepts `session=None` on every collection op as a no-op, so call
    sites can pass the yielded value verbatim. Disable via
    `settings.mongodb_use_transactions = False` on standalone mongod where
    `start_transaction()` would raise.
    """
    if settings.mongodb_use_transactions:
        async with await mongo_client.start_session() as session:
            async with session.start_transaction():
                yield session
    else:
        yield None


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
    # Sparse: control-only cases have subject_id=None and shouldn't take up
    # index slots. Powers "cases for subject X" lookups and the orphan-cleanup
    # check in delete_case.
    await db["cases"].create_index("subject_id", sparse=True)
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
