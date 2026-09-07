# tests/unit/test_sample_read_deltas.py
#
# Covers app.sample_read_deltas — the per-sample comparison that tells a
# topped-up sample from one re-delivered unchanged on a re-sequencing.

from bson import ObjectId

from app.sample_read_deltas import attach_read_deltas, read_count


def _taxprofiler_sample(analysis_id, sample_id, reads):
    """A taxprofiler sample doc; ``reads`` of None omits the fastp block."""
    doc = {
        "_id": ObjectId(),
        "analysis_id": analysis_id,
        "case_id": "CASE-1",
        "sample_id": sample_id,
        "sample_type": "sample",
    }
    if reads is not None:
        doc["taxprofiler"] = {"fastp": {"total_reads_before_filtering": reads}}
    return doc


def _trana_sample(analysis_id, sample_id, reads):
    return {
        "_id": ObjectId(),
        "analysis_id": analysis_id,
        "case_id": "CASE-1",
        "sample_id": sample_id,
        "sample_type": "sample",
        "trana": {"nanoplot_unprocessed": {"number_of_reads": reads}},
    }


async def _seed_analyses(db, versions):
    """Insert one case_analysis per version; return {version: ObjectId}."""
    ids = {}
    for v in versions:
        oid = ObjectId()
        await db["case_analysis"].insert_one(
            {
                "_id": oid,
                "case_id": "CASE-1",
                "version": v,
                "is_latest": v == max(versions),
            }
        )
        ids[v] = oid
    return ids


class TestReadCount:
    def test_prefers_trana_nanoplot(self):
        doc = {"trana": {"nanoplot_unprocessed": {"number_of_reads": 42}}}
        assert read_count(doc) == 42

    def test_reads_taxprofiler_fastp(self):
        doc = {"taxprofiler": {"fastp": {"total_reads_before_filtering": 99}}}
        assert read_count(doc) == 99

    def test_missing_qc_is_none_not_zero(self):
        # Zero would make a sample with no QC block look like a failed run.
        assert read_count({"taxprofiler": {"classifiers": {}}}) is None
        assert read_count({}) is None


class TestAttachReadDeltas:
    async def test_first_analysis_gets_no_deltas(self, fake_db):
        # With nothing to compare against, labelling every row would imply
        # each sample had failed to gain data.
        ids = await _seed_analyses(fake_db, [1])
        docs = [_taxprofiler_sample(ids[1], "S1", 1_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 1})
        await attach_read_deltas(fake_db, analysis, docs)

        assert "read_delta" not in docs[0]

    async def test_increased_decreased_and_unchanged(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        await fake_db["samples"].insert_many(
            [
                _taxprofiler_sample(ids[1], "topped-up", 1_000_000),
                _taxprofiler_sample(ids[1], "untouched", 500_000),
                _taxprofiler_sample(ids[1], "shrunk", 800_000),
            ]
        )
        docs = [
            _taxprofiler_sample(ids[2], "topped-up", 2_500_000),
            _taxprofiler_sample(ids[2], "untouched", 500_000),
            _taxprofiler_sample(ids[2], "shrunk", 600_000),
        ]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        by_id = {d["sample_id"]: d["read_delta"] for d in docs}

        assert by_id["topped-up"]["status"] == "increased"
        assert by_id["topped-up"]["delta_reads"] == 1_500_000
        assert by_id["topped-up"]["previous_version"] == 1
        assert by_id["topped-up"]["pct_change"] == 150.0

        assert by_id["untouched"]["status"] == "unchanged"
        assert by_id["untouched"]["delta_reads"] == 0

        assert by_id["shrunk"]["status"] == "decreased"
        assert by_id["shrunk"]["delta_reads"] == -200_000

    async def test_sample_absent_from_earlier_run_is_new(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        await fake_db["samples"].insert_one(_taxprofiler_sample(ids[1], "S1", 1_000))
        docs = [_taxprofiler_sample(ids[2], "S2", 5_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["status"] == "new"
        assert docs[0]["read_delta"]["previous_version"] is None

    async def test_compares_against_most_recent_run_containing_the_sample(
        self, fake_db
    ):
        # Present in v1, missing from v2, back in v3: comparing to v2 would
        # call it new, which is wrong — it is a top-up on top of v1.
        ids = await _seed_analyses(fake_db, [1, 2, 3])
        await fake_db["samples"].insert_many(
            [
                _taxprofiler_sample(ids[1], "S1", 1_000),
                _taxprofiler_sample(ids[2], "other", 9_000),
            ]
        )
        docs = [_taxprofiler_sample(ids[3], "S1", 4_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 3})
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["status"] == "increased"
        assert docs[0]["read_delta"]["previous_version"] == 1
        assert docs[0]["read_delta"]["delta_reads"] == 3_000

    async def test_superseded_analysis_compares_to_its_own_predecessor(self, fake_db):
        # Viewing v2 of three runs must not reach forward into v3.
        ids = await _seed_analyses(fake_db, [1, 2, 3])
        await fake_db["samples"].insert_many(
            [
                _taxprofiler_sample(ids[1], "S1", 1_000),
                _taxprofiler_sample(ids[3], "S1", 9_000),
            ]
        )
        docs = [_taxprofiler_sample(ids[2], "S1", 3_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["previous_version"] == 1
        assert docs[0]["read_delta"]["delta_reads"] == 2_000

    async def test_missing_read_count_is_unknown_not_unchanged(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        await fake_db["samples"].insert_many(
            [
                _taxprofiler_sample(ids[1], "no-previous-qc", None),
                _taxprofiler_sample(ids[1], "no-current-qc", 1_000),
            ]
        )
        docs = [
            _taxprofiler_sample(ids[2], "no-previous-qc", 1_000),
            _taxprofiler_sample(ids[2], "no-current-qc", None),
        ]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        by_id = {d["sample_id"]: d["read_delta"] for d in docs}
        assert by_id["no-previous-qc"]["status"] == "unknown"
        assert by_id["no-current-qc"]["status"] == "unknown"
        # Nothing may be inferred about the size of a change we cannot measure.
        assert by_id["no-previous-qc"]["delta_reads"] is None

    async def test_trana_samples_use_nanoplot_reads(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        await fake_db["samples"].insert_one(_trana_sample(ids[1], "S1", 200))
        docs = [_trana_sample(ids[2], "S1", 350)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["status"] == "increased"
        assert docs[0]["read_delta"]["delta_reads"] == 150

    async def test_other_cases_are_not_compared(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        other_analysis = ObjectId()
        await fake_db["case_analysis"].insert_one(
            {"_id": other_analysis, "case_id": "CASE-2", "version": 1}
        )
        await fake_db["samples"].insert_one(
            _taxprofiler_sample(other_analysis, "S1", 999_999)
        )
        docs = [_taxprofiler_sample(ids[2], "S1", 1_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one(
            {"case_id": "CASE-1", "version": 2}
        )
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["status"] == "new"

    async def test_zero_previous_reads_yields_no_pct_change(self, fake_db):
        ids = await _seed_analyses(fake_db, [1, 2])
        await fake_db["samples"].insert_one(_taxprofiler_sample(ids[1], "S1", 0))
        docs = [_taxprofiler_sample(ids[2], "S1", 5_000)]
        await fake_db["samples"].insert_many([dict(d) for d in docs])

        analysis = await fake_db["case_analysis"].find_one({"version": 2})
        await attach_read_deltas(fake_db, analysis, docs)

        assert docs[0]["read_delta"]["status"] == "increased"
        assert docs[0]["read_delta"]["pct_change"] is None
