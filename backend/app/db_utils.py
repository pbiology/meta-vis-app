# app/db_utils.py

import logging
from typing import Any

from app.constants import MAX_LIST_ITEMS

logger = logging.getLogger(__name__)


async def fetch_capped(cursor: Any, name: str) -> list[dict]:
    """Read a Motor cursor capped at MAX_LIST_ITEMS, warning if the cap is hit.

    Use only for collections expected to stay well below the cap (e.g. the
    overview of taxon lists). Not for taxon-list *entries*: those are read in
    full, since a list can legitimately hold tens of thousands of taxa.
    Hitting the cap is treated as a misconfiguration to surface, not a normal
    pagination boundary.
    """
    docs: list[dict] = await cursor.to_list(length=MAX_LIST_ITEMS)
    if len(docs) >= MAX_LIST_ITEMS:
        logger.warning(
            "Reference list %r reached MAX_LIST_ITEMS cap (%d); results may be truncated",
            name,
            MAX_LIST_ITEMS,
        )
    return docs
