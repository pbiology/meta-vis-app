# tests/unit/test_blob_store.py

import pytest
from mongomock_motor import AsyncMongoMockClient
from app.blob_store import MongoBlobStore, make_blob_store


@pytest.fixture
def db():
    client = AsyncMongoMockClient()
    return client["test_db"]


@pytest.fixture
def store(db):
    return MongoBlobStore(db)


# ---------------------------------------------------------------------------
# put / get
# ---------------------------------------------------------------------------

class TestPutGet:

    async def test_put_and_get_returns_content(self, store):
        await store.put("krona/abc/kraken2.html", "<html>krona</html>")
        result = await store.get("krona/abc/kraken2.html")
        assert result == "<html>krona</html>"

    async def test_get_missing_key_returns_none(self, store):
        result = await store.get("does/not/exist.html")
        assert result is None

    async def test_put_overwrites_existing_key(self, store):
        await store.put("key", "first")
        await store.put("key", "second")
        assert await store.get("key") == "second"

    async def test_put_multiple_keys_independently(self, store):
        await store.put("key1", "value1")
        await store.put("key2", "value2")
        assert await store.get("key1") == "value1"
        assert await store.get("key2") == "value2"

    async def test_empty_string_content_stored(self, store):
        await store.put("empty", "")
        assert await store.get("empty") == ""

    async def test_html_content_roundtrip(self, store):
        html = "<html><head></head><body><h1>Test</h1></body></html>"
        await store.put("test.html", html)
        assert await store.get("test.html") == html


# ---------------------------------------------------------------------------
# delete_prefix
# ---------------------------------------------------------------------------

class TestDeletePrefix:

    async def test_deletes_matching_keys(self, store):
        await store.put("krona/case1/kraken2.html", "a")
        await store.put("krona/case1/centrifuge.html", "b")
        await store.delete_prefix("krona/case1/")
        assert await store.get("krona/case1/kraken2.html") is None
        assert await store.get("krona/case1/centrifuge.html") is None

    async def test_does_not_delete_non_matching_keys(self, store):
        await store.put("krona/case1/kraken2.html", "a")
        await store.put("krona/case2/kraken2.html", "b")
        await store.delete_prefix("krona/case1/")
        assert await store.get("krona/case2/kraken2.html") == "b"

    async def test_delete_nonexistent_prefix_is_safe(self, store):
        await store.delete_prefix("does/not/exist/")  # should not raise

    async def test_delete_all_keys_under_prefix(self, store):
        for i in range(5):
            await store.put(f"igv/caseX/file{i}.html", f"content{i}")
        await store.delete_prefix("igv/caseX/")
        for i in range(5):
            assert await store.get(f"igv/caseX/file{i}.html") is None


# ---------------------------------------------------------------------------
# make_blob_store factory
# ---------------------------------------------------------------------------

class TestMakeBlobStore:

    def test_returns_mongo_blob_store_when_no_s3_config(self, db):
        from unittest.mock import patch
        from app.config import settings
        with patch.object(settings, "object_storage_endpoint", None):
            store = make_blob_store(db)
        assert isinstance(store, MongoBlobStore)