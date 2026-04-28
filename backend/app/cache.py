# app/cache.py

from motor.motor_asyncio import AsyncIOMotorDatabase

_COLLECTION = "meta"
_VERSION_DOC_ID = "cache_version"


async def get_cache_version(db: AsyncIOMotorDatabase) -> int:
    """
    Read the shared cache invalidation counter from MongoDB.

    Returns -1 on any DB error so the caller treats the result as a cache miss
    rather than serving stale data.
    """
    try:
        doc = await db[_COLLECTION].find_one({"_id": _VERSION_DOC_ID})
        return int(doc["version"]) if doc else 0
    except Exception:
        return -1


async def bump_cache_version(db: AsyncIOMotorDatabase) -> None:
    """
    Atomically increment the shared version counter.

    All worker processes will detect the new version on their next cached
    request and recompute. Uses upsert so the document is created on first call.
    """
    await db[_COLLECTION].update_one(
        {"_id": _VERSION_DOC_ID},
        {"$inc": {"version": 1}},
        upsert=True,
    )
