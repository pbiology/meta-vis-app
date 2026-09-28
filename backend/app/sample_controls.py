# app/sample_controls.py
"""Which controls a sample is compared against.

Shared by the NTC-profile and clade endpoints so both use one definition.

A clinical sample or positive control is compared against exactly the negative
controls declared for it at ingest (``negative_control_sample_ids``, validated
by ``app.models.ingest``). The link is never inferred from the analysis and
nucleic acid alone: a run can hold several controls per nucleic acid — one per
prep method, say — and comparing a sample with another prep's control flags the
wrong contaminants.

A negative control has no declared controls; it is compared against the other
negative controls of the same analysis and nucleic acid, which is context for
the control rather than a contamination check. Positive controls are never
returned.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


class ControlLinkError(RuntimeError):
    """A sample's stored control link does not match the database.

    Ingest validates every link, so this means the stored data is corrupt.
    Raised rather than showing fewer controls: a missing control silently
    disables contaminant flagging for the taxa it carried.
    """


async def matching_negative_controls(
    db: AsyncIOMotorDatabase, sample: dict, projection: dict[str, Any]
) -> list[dict]:
    """Negative controls for *sample*, ordered by sample_id.

    *sample* must carry ``_id``, ``analysis_id``, ``sample_type``,
    ``nucleic_acid`` and ``negative_control_sample_ids``. Not capped: one
    analysis holds a handful of controls, and a cap would silently drop some
    from the comparison.
    """
    query: dict[str, Any] = {
        "analysis_id": sample["analysis_id"],
        "sample_type": "negative_ctrl",
        "nucleic_acid": sample["nucleic_acid"],
    }
    # None for a negative control, which matches on analysis and nucleic acid.
    declared: list[str] | None = None
    if sample["sample_type"] == "negative_ctrl":
        # Never compare a control with itself.
        query["_id"] = {"$ne": sample["_id"]}
    else:
        declared = sample.get("negative_control_sample_ids")
        if declared is None:
            raise ControlLinkError(
                f"Sample {sample['_id']} ({sample['sample_type']}) has no "
                "negative_control_sample_ids; every non-control sample is "
                "ingested with one."
            )
        if not declared:
            # Explicitly ingested without a control; the UI warns about it.
            return []
        query["sample_id"] = {"$in": declared}

    controls: list[dict] = (
        await db["samples"]
        .find(query, {**projection, "sample_id": 1})
        .sort("sample_id", 1)
        .to_list(length=None)
    )

    if declared is not None:
        missing = sorted(set(declared) - {c["sample_id"] for c in controls})
        if missing:
            raise ControlLinkError(
                f"Sample {sample['_id']} declares negative control(s) {missing} "
                f"that are not {sample['nucleic_acid']} negative controls in "
                f"analysis {sample['analysis_id']}."
            )
    return controls
