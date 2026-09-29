# app/taxonomy_indexes.py
"""Indexes on the `taxa_retired` reference collection.

Shared by the app (``database._ensure_indexes``) and ``load_taxonomy.py``,
which rebuilds the collection in a staging copy and renames it into place —
the rename drops the old collection's indexes, so the staging copy must get
them too. Kept free of app settings so the standalone script can import it.
"""

from motor.motor_asyncio import AsyncIOMotorCollection


async def ensure_retired_indexes(collection: AsyncIOMotorCollection) -> None:
    await collection.create_index("taxon_id", unique=True)
    # "Which retired ids were merged into these current ids?" — asked every
    # time a taxon list is used for matching. Partial: only the ~100k merged
    # records carry merged_into, so the index stays small. Queries must
    # include {"status": "merged"} for MongoDB to use it.
    await collection.create_index(
        "merged_into",
        name="merged_into_1_merged",
        partialFilterExpression={"status": "merged"},
    )
