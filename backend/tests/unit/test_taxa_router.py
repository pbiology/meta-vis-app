# tests/unit/test_taxa_router.py
#
# Tests for the taxa router endpoints, including the new PubMed literature
# and external links endpoints.
#
# External httpx calls are mocked with unittest.mock.patch so no network
# access or new test dependencies are required.
#
# Auth is bypassed via dependency_overrides, following the same pattern as
# the rest of the test suite.

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers.taxa import router as taxa_router, _literature_cache, _links_cache
from app.auth.utils import get_current_user, require_role
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(mock_db=None, role="reader"):
    app = FastAPI()
    app.include_router(taxa_router, prefix="/api/v1")
    db = mock_db or MagicMock()
    user = {"username": "testuser", "role": role}
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return app, db


def make_taxon_doc(taxon_id=12637, name="Dengue virus", **kwargs):
    return {
        "taxon_id": taxon_id,
        "name": name,
        "rank": "species",
        "superkingdom": "Viruses",
        "taxdump_version": "2024-01-01",
        **kwargs,
    }


# ---------------------------------------------------------------------------
# GET /taxa/{taxon_id}
# ---------------------------------------------------------------------------


class TestGetTaxon:
    def test_returns_taxon_doc(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value=make_taxon_doc())

        resp = TestClient(app).get("/api/v1/taxa/12637")

        assert resp.status_code == 200
        assert resp.json()["taxon_id"] == 12637
        assert resp.json()["name"] == "Dengue virus"

    def test_adds_needs_taxonomy_refresh_false_when_taxdump_present(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxdump_version="2024-01-01")
        )

        resp = TestClient(app).get("/api/v1/taxa/12637")

        assert resp.json()["needs_taxonomy_refresh"] is False

    def test_adds_needs_taxonomy_refresh_true_when_taxdump_missing(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxdump_version=None)
        )

        resp = TestClient(app).get("/api/v1/taxa/12637")

        assert resp.json()["needs_taxonomy_refresh"] is True

    def test_returns_404_when_not_found(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value=None)

        resp = TestClient(app).get("/api/v1/taxa/99999")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /taxa/{taxon_id}/clinical_notes
# ---------------------------------------------------------------------------


class TestUpdateClinicalNotes:
    def test_saves_notes_successfully(self):
        app, db = make_app(role="writer")
        db["taxa"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))

        resp = TestClient(app).patch(
            "/api/v1/taxa/12637/clinical_notes",
            json={"clinical_notes": "Associated with dengue fever."},
        )

        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    def test_returns_404_when_taxon_missing(self):
        app, db = make_app(role="writer")
        db["taxa"].update_one = AsyncMock(return_value=MagicMock(matched_count=0))

        resp = TestClient(app).patch(
            "/api/v1/taxa/99999/clinical_notes",
            json={"clinical_notes": "Some note"},
        )

        assert resp.status_code == 404

    def test_clears_notes_with_null(self):
        app, db = make_app(role="writer")
        db["taxa"].update_one = AsyncMock(return_value=MagicMock(matched_count=1))

        resp = TestClient(app).patch(
            "/api/v1/taxa/12637/clinical_notes",
            json={"clinical_notes": None},
        )

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /taxa/{taxon_id}/external_links
# ---------------------------------------------------------------------------


class TestGetExternalLinks:
    def setup_method(self):
        _links_cache.clear()

    def _make_httpx_response(self, json_data: dict, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_links_from_ncbi(self):
        app, _ = make_app()
        ncbi_payload = {
            "tax_id": "12637",
            "wikipedia": "https://en.wikipedia.org/wiki/Dengue_virus",
            "ncbi_taxonomy": "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=12637",
        }
        mock_resp = self._make_httpx_response(ncbi_payload)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/external_links")

        assert resp.status_code == 200
        links = resp.json()["links"]
        # tax_id should be excluded; the two URL fields become links
        assert len(links) == 2
        names = {l["name"] for l in links}
        assert "Wikipedia" in names

    def test_returns_empty_list_on_network_error(self):
        app, _ = make_app()

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/external_links")

        assert resp.status_code == 200
        assert resp.json()["links"] == []

    def test_result_is_cached(self):
        app, _ = make_app()
        ncbi_payload = {
            "tax_id": "12637",
            "wikipedia": "https://en.wikipedia.org/wiki/Dengue_virus",
        }
        mock_resp = self._make_httpx_response(ncbi_payload)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            TestClient(app).get("/api/v1/taxa/12637/external_links")
            TestClient(app).get("/api/v1/taxa/12637/external_links")

            # httpx should only have been called once — second request hits cache
            assert mock_client.get.call_count == 1


# ---------------------------------------------------------------------------
# GET /taxa/{taxon_id}/literature
# ---------------------------------------------------------------------------


class TestGetTaxonLiterature:
    def setup_method(self):
        _literature_cache.clear()

    def _mock_pubmed(self, pmids: list[str], summaries: dict):
        """
        Build a mock httpx AsyncClient whose .get() returns appropriate
        ESearch and ESummary responses depending on the URL called.
        """
        esearch_resp = MagicMock()
        esearch_resp.raise_for_status = MagicMock()
        esearch_resp.json.return_value = {"esearchresult": {"idlist": pmids}}

        esummary_resp = MagicMock()
        esummary_resp.raise_for_status = MagicMock()
        esummary_resp.json.return_value = {"result": summaries}

        # Return esearch response on first call, esummary on second
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[esearch_resp, esummary_resp])
        return mock_client

    def test_returns_articles_from_pubmed(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        summaries = {
            "12345": {
                "title": "Dengue fever outbreak in Southeast Asia",
                "fulljournalname": "The Lancet",
                "pubdate": "2024 Jan",
            }
        }
        mock_client = self._mock_pubmed(["12345"], summaries)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/literature")

        assert resp.status_code == 200
        data = resp.json()
        assert data["article_count"] == 1
        assert data["articles"][0]["pmid"] == "12345"
        assert data["articles"][0]["title"] == "Dengue fever outbreak in Southeast Asia"
        assert data["articles"][0]["journal"] == "The Lancet"
        assert data["articles"][0]["link"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"

    def test_returns_empty_when_no_pmids_found(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        mock_client = AsyncMock()
        esearch_resp = MagicMock()
        esearch_resp.raise_for_status = MagicMock()
        esearch_resp.json.return_value = {"esearchresult": {"idlist": []}}
        mock_client.get = AsyncMock(return_value=esearch_resp)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/literature")

        assert resp.status_code == 200
        assert resp.json()["article_count"] == 0
        assert resp.json()["articles"] == []

    def test_returns_empty_on_network_error(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/literature")

        assert resp.status_code == 200
        assert resp.json()["articles"] == []

    def test_falls_back_to_taxon_id_string_when_taxon_not_in_db(self):
        """If the taxon isn't in our taxa collection, we still query PubMed using the ID."""
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value=None)

        mock_client = AsyncMock()
        esearch_resp = MagicMock()
        esearch_resp.raise_for_status = MagicMock()
        esearch_resp.json.return_value = {"esearchresult": {"idlist": []}}
        mock_client.get = AsyncMock(return_value=esearch_resp)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/literature")

        assert resp.status_code == 200
        # Confirm the ESearch was still called (just with taxon id as name fallback)
        call_args = mock_client.get.call_args
        assert "12637" in str(call_args)

    def test_result_is_cached(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        summaries = {
            "12345": {
                "title": "Test article",
                "fulljournalname": "Test Journal",
                "pubdate": "2024",
            }
        }
        mock_client = self._mock_pubmed(["12345"], summaries)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            TestClient(app).get("/api/v1/taxa/12637/literature")
            TestClient(app).get("/api/v1/taxa/12637/literature")

            # httpx should only be called for the first request
            assert (
                mock_client.get.call_count == 2
            )  # esearch + esummary, only once total

    def test_max_results_param_is_respected(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        mock_client = AsyncMock()
        esearch_resp = MagicMock()
        esearch_resp.raise_for_status = MagicMock()
        esearch_resp.json.return_value = {"esearchresult": {"idlist": []}}
        mock_client.get = AsyncMock(return_value=esearch_resp)

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_client_cls:
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/literature?max_results=10")

        assert resp.status_code == 200
        # Confirm retmax=10 was passed to ESearch
        call_args = mock_client.get.call_args
        assert call_args.kwargs["params"]["retmax"] == 10

    def test_max_results_capped_at_20(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(return_value={"name": "Dengue virus"})

        resp = TestClient(app).get("/api/v1/taxa/12637/literature?max_results=999")

        assert resp.status_code == 422  # FastAPI validation rejects values > 20
