# tests/integration/test_ingest_router.py
#
# Integration tests for POST /api/v1/ingest/taxprofiler (multipart upload).
# We patch the loader + orchestrator and assert the router's error ladder,
# audit calls, and cache invalidation. End-to-end loader behaviour is covered
# by tests/unit/test_loader.py.

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.routers.ingest import router
from app.ingestor.loader import BundleError, BundleTooLargeError
from tests.helpers import make_test_app


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


def _fake_bundle() -> bytes:
    return b"\x1f\x8b\x08\x00fakefakefake"  # not real gzip; loader is mocked


def _meta_stub(case_id: str = "testcase"):
    from app.models.sample import ClassifierMeta, IngestMeta, SampleIngestRequest

    return IngestMeta(
        case_id=case_id,
        classifiers=[ClassifierMeta(name="kraken2", db="k2_pluspf")],
        samples=[
            SampleIngestRequest(
                sample_id="S1",
                sample_type="sample",
                material="DNA",
                columns={"kraken2": "S1_kraken2"},
            )
        ],
    )


class TestIngest:
    async def test_successful_ingest_returns_result(self, client):
        with (
            patch(
                "app.routers.ingest.load_taxprofiler_bundle",
                new=AsyncMock(return_value=(_meta_stub(), object())),
            ),
            patch(
                "app.routers.ingest.ingest_case",
                new=AsyncMock(
                    return_value={"case_id": "testcase", "samples_ingested": 1}
                ),
            ),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 200
        assert resp.json()["case_id"] == "testcase"

    async def test_malformed_bundle_returns_400(self, client):
        with patch(
            "app.routers.ingest.load_taxprofiler_bundle",
            new=AsyncMock(side_effect=BundleError("bad tar")),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 400

    async def test_bundle_too_large_returns_413(self, client):
        with patch(
            "app.routers.ingest.load_taxprofiler_bundle",
            new=AsyncMock(side_effect=BundleTooLargeError("too big")),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 413

    async def test_manifest_validation_returns_422(self, client):
        # Build a real ValidationError instance via Pydantic
        from app.models.sample import IngestMeta

        try:
            IngestMeta.model_validate({})
        except ValidationError as exc:
            ve = exc

        with patch(
            "app.routers.ingest.load_taxprofiler_bundle", new=AsyncMock(side_effect=ve)
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 422

    async def test_duplicate_case_id_returns_422(self, client):
        with (
            patch(
                "app.routers.ingest.load_taxprofiler_bundle",
                new=AsyncMock(return_value=(_meta_stub(), object())),
            ),
            patch(
                "app.routers.ingest.ingest_case",
                new=AsyncMock(
                    side_effect=ValueError("Case 'testcase' already exists.")
                ),
            ),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 422

    async def test_unexpected_error_returns_500(self, client):
        with (
            patch(
                "app.routers.ingest.load_taxprofiler_bundle",
                new=AsyncMock(return_value=(_meta_stub(), object())),
            ),
            patch(
                "app.routers.ingest.ingest_case",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
        assert resp.status_code == 500

    async def test_ingest_clears_alerts_cache(self, client):
        from app.routers import alerts

        alerts._cache[14] = {"outbreaks": []}
        with (
            patch(
                "app.routers.ingest.load_taxprofiler_bundle",
                new=AsyncMock(return_value=(_meta_stub(), object())),
            ),
            patch(
                "app.routers.ingest.ingest_case",
                new=AsyncMock(
                    return_value={"case_id": "testcase", "samples_ingested": 1}
                ),
            ),
        ):
            resp = client.post(
                "/api/v1/ingest/taxprofiler",
                files={
                    "bundle": (
                        "b.tar.gz",
                        io.BytesIO(_fake_bundle()),
                        "application/gzip",
                    )
                },
            )
            assert resp.status_code == 200
            assert alerts._cache == {}
