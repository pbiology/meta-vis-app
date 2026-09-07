# app/sample_read_deltas.py
"""Compare a sample's raw read count against earlier analyses of its case.

A clinical case is sequenced, delivered partially so analysis can start early,
then topped up for any sample that had not reached the agreed data amount. Each
delivery is its own ``case_analysis``, so the evidence that a sample actually
gained data is its raw input read count rising between versions.

Read-time only: nothing here is stored, so a re-ingest never has to backfill.
"""

from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.sample import ReadDeltaStatus, SampleReadDelta

# Raw input reads, before any filtering — the count that actually reflects how
# much data the sequencing run delivered. These are the same fields the case
# view's "Total reads" column renders, so badge and number cannot disagree.
_TAXPROFILER_READS = "taxprofiler.fastp.total_reads_before_filtering"
_TRANA_READS = "trana.nanoplot_unprocessed.number_of_reads"

# Projection for the earlier-analysis lookup: sample identity plus the two read
# fields. Sample documents carry full classifier profiles, which must not be
# pulled into memory just to compare two integers.
_READ_PROJECTION: dict[str, Any] = {
    "sample_id": 1,
    "analysis_id": 1,
    _TAXPROFILER_READS: 1,
    _TRANA_READS: 1,
}


def read_count(doc: dict) -> Optional[int]:
    """Raw input reads for a sample document, whichever pipeline produced it.

    Returns None when the count is absent — a sample whose QC block never
    arrived. Callers must not treat that as zero.
    """
    trana = doc.get("trana") or {}
    nanoplot = trana.get("nanoplot_unprocessed") or {}
    if nanoplot.get("number_of_reads") is not None:
        return int(nanoplot["number_of_reads"])

    taxprofiler = doc.get("taxprofiler") or {}
    fastp = taxprofiler.get("fastp") or {}
    if fastp.get("total_reads_before_filtering") is not None:
        return int(fastp["total_reads_before_filtering"])

    return None


def _build_delta(
    current: Optional[int], previous: Optional[tuple[int, Optional[int]]]
) -> SampleReadDelta:
    """Classify one sample against its most recent earlier appearance.

    ``previous`` is (version, reads) or None when the sample is new to the case.
    """
    if previous is None:
        return SampleReadDelta(status="new", current_reads=current)

    previous_version, previous_reads = previous
    if current is None or previous_reads is None:
        return SampleReadDelta(
            status="unknown",
            current_reads=current,
            previous_reads=previous_reads,
            previous_version=previous_version,
        )

    delta = current - previous_reads
    status: ReadDeltaStatus
    if delta > 0:
        status = "increased"
    elif delta < 0:
        status = "decreased"
    else:
        status = "unchanged"

    return SampleReadDelta(
        status=status,
        current_reads=current,
        previous_reads=previous_reads,
        previous_version=previous_version,
        delta_reads=delta,
        # Guarded rather than assumed non-zero: a previous run that delivered
        # nothing would otherwise divide by zero.
        pct_change=round(delta / previous_reads * 100, 1) if previous_reads else None,
    )


async def _previous_reads_by_sample(
    db: AsyncIOMotorDatabase, case_id: str, version: int
) -> Optional[dict[str, tuple[int, Optional[int]]]]:
    """Map sample_id → (version, reads) of its most recent earlier appearance.

    Keyed on the newest earlier analysis *containing that sample* rather than
    ``version - 1``: a sample missing from one run and back in the next would
    otherwise read as brand new.

    None when the case has no earlier analysis at all — distinct from an empty
    mapping, where earlier runs exist but share no sample, and every sample of
    this run is genuinely new.
    """
    earlier = (
        await db["case_analysis"]
        .find({"case_id": case_id, "version": {"$lt": version}}, {"version": 1})
        .to_list(length=None)
    )
    if not earlier:
        return None

    version_by_oid: dict[ObjectId, int] = {d["_id"]: int(d["version"]) for d in earlier}

    best: dict[str, tuple[int, Optional[int]]] = {}
    cursor = db["samples"].find(
        {"analysis_id": {"$in": list(version_by_oid)}}, _READ_PROJECTION
    )
    async for doc in cursor:
        sample_id = doc.get("sample_id")
        analysis_version = version_by_oid.get(doc.get("analysis_id"))
        if sample_id is None or analysis_version is None:
            continue
        seen = best.get(sample_id)
        if seen is None or analysis_version > seen[0]:
            best[sample_id] = (analysis_version, read_count(doc))
    return best


async def attach_read_deltas(
    db: AsyncIOMotorDatabase, analysis: dict, docs: list[dict]
) -> None:
    """Add a ``read_delta`` block to each sample doc, in place.

    No-op on a case's first analysis: with nothing to compare against, every
    sample would be labelled as though it had failed to gain data.
    """
    previous = await _previous_reads_by_sample(
        db, analysis["case_id"], int(analysis["version"])
    )
    if previous is None:
        return

    for doc in docs:
        delta = _build_delta(read_count(doc), previous.get(doc.get("sample_id", "")))
        doc["read_delta"] = delta.model_dump()
