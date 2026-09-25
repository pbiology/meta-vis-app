# tests/unit/test_sample_controls.py
"""matching_negative_controls: declared controls for a sample, never inferred."""

import pytest
from bson import ObjectId

from app.sample_controls import ControlLinkError, matching_negative_controls

ANALYSIS = ObjectId()


async def _insert(db, sample_id, sample_type="sample", nucleic_acid="DNA", **extra):
    doc = {
        "_id": ObjectId(),
        "analysis_id": extra.pop("analysis_id", ANALYSIS),
        "sample_id": sample_id,
        "sample_type": sample_type,
        "nucleic_acid": nucleic_acid,
        **extra,
    }
    await db["samples"].insert_one(doc)
    return doc


async def _seed_two_preps(db):
    """One DNA run with two preps, each with its own control."""
    for ntc in ("NTC-ELB-DNA", "NTC-HLSAN-DNA"):
        await _insert(db, ntc, sample_type="negative_ctrl")
    await _insert(db, "NTC-ELB-RNA", sample_type="negative_ctrl", nucleic_acid="RNA")
    await _insert(
        db, "NTC-OTHER-RUN", sample_type="negative_ctrl", analysis_id=ObjectId()
    )


def _ids(docs):
    return [d["sample_id"] for d in docs]


async def test_returns_only_the_declared_control(fake_db):
    await _seed_two_preps(fake_db)
    sample = await _insert(
        fake_db, "S-ELB-DNA", negative_control_sample_ids=["NTC-ELB-DNA"]
    )

    controls = await matching_negative_controls(fake_db, sample, {"profiles": 1})

    assert _ids(controls) == ["NTC-ELB-DNA"]


async def test_returns_several_declared_controls_in_order(fake_db):
    await _seed_two_preps(fake_db)
    sample = await _insert(
        fake_db,
        "S-DNA",
        negative_control_sample_ids=["NTC-HLSAN-DNA", "NTC-ELB-DNA"],
    )

    controls = await matching_negative_controls(fake_db, sample, {"profiles": 1})

    assert _ids(controls) == ["NTC-ELB-DNA", "NTC-HLSAN-DNA"]


async def test_positive_control_uses_its_declared_control(fake_db):
    await _seed_two_preps(fake_db)
    pos = await _insert(
        fake_db,
        "POS-DNA",
        sample_type="positive_ctrl",
        negative_control_sample_ids=["NTC-HLSAN-DNA"],
    )

    controls = await matching_negative_controls(fake_db, pos, {})

    assert _ids(controls) == ["NTC-HLSAN-DNA"]


async def test_explicitly_no_control_returns_empty(fake_db):
    await _seed_two_preps(fake_db)
    sample = await _insert(fake_db, "S-DNA", negative_control_sample_ids=[])

    assert await matching_negative_controls(fake_db, sample, {}) == []


async def test_missing_link_is_an_error(fake_db):
    # Ingest always writes the field on a non-control sample; its absence
    # means the stored data is corrupt, not that the sample has no control.
    await _seed_two_preps(fake_db)
    sample = await _insert(fake_db, "S-DNA")

    with pytest.raises(ControlLinkError, match="no negative_control_sample_ids"):
        await matching_negative_controls(fake_db, sample, {})


@pytest.mark.parametrize(
    "declared",
    [
        ["NTC-GONE"],  # not in the database at all
        ["NTC-ELB-RNA"],  # other nucleic acid
        ["NTC-OTHER-RUN"],  # other analysis
        ["S-OTHER"],  # not a negative control
    ],
)
async def test_unresolvable_link_is_an_error(fake_db, declared):
    # Showing fewer controls than declared would silently drop the taxa those
    # controls carry from contaminant flagging.
    await _seed_two_preps(fake_db)
    await _insert(fake_db, "S-OTHER", negative_control_sample_ids=[])
    sample = await _insert(
        fake_db, "S-DNA", negative_control_sample_ids=["NTC-ELB-DNA", *declared]
    )

    with pytest.raises(ControlLinkError, match=declared[0]):
        await matching_negative_controls(fake_db, sample, {})


async def test_negative_control_sees_the_other_run_controls(fake_db):
    await _seed_two_preps(fake_db)
    ntc = await fake_db["samples"].find_one({"sample_id": "NTC-ELB-DNA"})

    controls = await matching_negative_controls(fake_db, ntc, {})

    assert _ids(controls) == ["NTC-HLSAN-DNA"]
