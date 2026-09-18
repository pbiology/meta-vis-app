# app/sample_controls.py
"""Which controls a sample is compared against.

Shared by the NTC-profile and clade endpoints so both use one definition: the
negative controls produced by the same analysis (sequencing run) with the same
nucleic acid. DNA and RNA controls are technically incomparable, and controls
from another run say nothing about this run's contamination. Positive controls
are handled separately and never included.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


async def matching_negative_controls(
    db: AsyncIOMotorDatabase, sample: dict, projection: dict[str, Any]
) -> list[dict]:
    """Negative controls for *sample*, ordered by sample_id.

    *sample* must carry ``_id``, ``analysis_id`` and ``nucleic_acid``. The
    sample itself is excluded, so a negative control is never compared with
    itself. Not capped: one analysis holds a handful of controls, and a cap
    would silently drop some from the comparison.
    """
    return (
        await db["samples"]
        .find(
            {
                "_id": {"$ne": sample["_id"]},
                "analysis_id": sample["analysis_id"],
                "sample_type": "negative_ctrl",
                "nucleic_acid": sample["nucleic_acid"],
            },
            projection,
        )
        .sort("sample_id", 1)
        .to_list(length=None)
    )
