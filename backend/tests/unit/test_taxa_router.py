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

from app.routers.taxa import (
    router as taxa_router,
    _literature_cache,
    _links_cache,
    _bvbrc_genomes_cache,
    _bvbrc_specialty_cache,
)
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


# ---------------------------------------------------------------------------
# GET /taxa/{taxon_id}/bvbrc/genomes
# ---------------------------------------------------------------------------


def _make_bvbrc_response(json_data, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_bvbrc_client(responses):
    """Return a mock AsyncClient whose .get() yields each response in order."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    return mock_client


class TestGetBvbrcGenomes:
    def setup_method(self):
        _bvbrc_genomes_cache.clear()

    def test_returns_aggregated_summary(self):
        app, _ = make_app()
        genomes = [
            {
                "genome_id": "1",
                "isolation_source": "Blood",
                "isolation_country": "Sweden",
                "antimicrobial_resistance": ["Isoniazid"],
            },
            {
                "genome_id": "2",
                "isolation_source": "Blood",
                "isolation_country": "Norway",
                "antimicrobial_resistance": ["Isoniazid", "Rifampicin"],
            },
            {
                "genome_id": "3",
                "isolation_source": "Sputum",
                "isolation_country": "Sweden",
                "antimicrobial_resistance": [],
            },
        ]
        mock_resp = _make_bvbrc_response(genomes)
        mock_client = _mock_bvbrc_client([mock_resp])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_genomes"] == 3

        # Isolation sources: Blood (2), Sputum (1)
        sources = {s["source"]: s["count"] for s in data["isolation_sources"]}
        assert sources["Blood"] == 2
        assert sources["Sputum"] == 1

        # Countries: Sweden (2), Norway (1)
        countries = {c["country"]: c["count"] for c in data["countries"]}
        assert countries["Sweden"] == 2
        assert countries["Norway"] == 1

        # AMR: Isoniazid (2 genomes), Rifampicin (1 genome)
        amr = {a["antibiotic"]: a["count"] for a in data["amr_phenotypes"]}
        assert amr["Isoniazid"] == 2
        assert amr["Rifampicin"] == 1

        # Sorted descending by count
        assert data["isolation_sources"][0]["source"] == "Blood"
        assert data["amr_phenotypes"][0]["antibiotic"] == "Isoniazid"

        assert "bvbrc_url" in data

    def test_returns_empty_on_no_genomes(self):
        app, _ = make_app()
        mock_resp = _make_bvbrc_response([])
        mock_client = _mock_bvbrc_client([mock_resp])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_genomes"] == 0
        assert data["isolation_sources"] == []
        assert data["countries"] == []
        assert data["amr_phenotypes"] == []

    def test_returns_empty_on_network_error(self):
        app, _ = make_app()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")

        assert resp.status_code == 200
        assert resp.json()["total_genomes"] == 0

    def test_caches_result(self):
        app, _ = make_app()
        mock_resp = _make_bvbrc_response(
            [
                {
                    "genome_id": "1",
                    "isolation_source": "Blood",
                    "isolation_country": "Sweden",
                    "antimicrobial_resistance": [],
                }
            ]
        )
        mock_client = _mock_bvbrc_client([mock_resp])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")
            TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")

            # httpx should only have been called once — second request hits cache
            assert mock_client.get.call_count == 1

    def test_isolation_sources_capped_at_ten(self):
        app, _ = make_app()
        genomes = [
            {
                "genome_id": str(i),
                "isolation_source": f"Source {i}",
                "isolation_country": None,
                "antimicrobial_resistance": [],
            }
            for i in range(15)
        ]
        mock_resp = _make_bvbrc_response(genomes)
        mock_client = _mock_bvbrc_client([mock_resp])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/genomes")

        assert resp.status_code == 200
        assert len(resp.json()["isolation_sources"]) <= 10


# ---------------------------------------------------------------------------
# GET /taxa/{taxon_id}/bvbrc/specialty_genes
# ---------------------------------------------------------------------------


class TestGetBvbrcSpecialtyGenes:
    def setup_method(self):
        _bvbrc_specialty_cache.clear()

    def _make_sg_response(self, genes):
        return _make_bvbrc_response(genes)

    def _make_amr_response(self, records):
        return _make_bvbrc_response(records)

    def test_returns_amr_and_virulence_for_bacteria(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=1773, superkingdom="Bacteria")
        )

        sg_genes = [
            {
                "gene": "katG",
                "property": "Antibiotic Resistance",
                "source": "CARD",
                "mechanism": "target alteration",
                "product": "catalase-peroxidase",
            },
            {
                "gene": "mmpL3",
                "property": "Virulence Factor",
                "source": "VFDB",
                "mechanism": None,
                "product": "mycolic acid transporter",
            },
        ]
        amr_records = [
            {
                "antibiotic": "Isoniazid",
                "resistant_phenotype": "Resistant",
                "evidence": "AMR",
            },
            {
                "antibiotic": "Isoniazid",
                "resistant_phenotype": "Susceptible",
                "evidence": "AMR",
            },
            {
                "antibiotic": "Rifampicin",
                "resistant_phenotype": "Resistant",
                "evidence": "AMR",
            },
        ]

        mock_sg = self._make_sg_response(sg_genes)
        mock_amr = self._make_amr_response(amr_records)
        mock_client = _mock_bvbrc_client([mock_sg, mock_amr])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_viral"] is False

        assert len(data["amr_genes"]) == 1
        assert data["amr_genes"][0]["gene"] == "katG"
        assert data["amr_genes"][0]["source"] == "CARD"

        assert len(data["virulence_factors"]) == 1
        assert data["virulence_factors"][0]["gene"] == "mmpL3"

        # Isoniazid: 1 resistant, 1 susceptible; Rifampicin: 1 resistant
        phenotypes = {p["antibiotic"]: p for p in data["amr_phenotypes"]}
        assert phenotypes["Isoniazid"]["resistant"] == 1
        assert phenotypes["Isoniazid"]["susceptible"] == 1
        assert phenotypes["Rifampicin"]["resistant"] == 1

    def test_skips_bvbrc_calls_for_viruses(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=12637, superkingdom="Viruses")
        )

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/12637/bvbrc/specialty_genes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_viral"] is True
        assert data["amr_genes"] == []
        assert data["virulence_factors"] == []
        assert data["amr_phenotypes"] == []
        # BV-BRC was never called
        mock_client.get.assert_not_called()

    def test_deduplicates_genes(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=1773, superkingdom="Bacteria")
        )

        sg_genes = [
            {
                "gene": "katG",
                "property": "Antibiotic Resistance",
                "source": "CARD",
                "mechanism": "target alteration",
                "product": "catalase-peroxidase",
            },
            # Duplicate — same gene + property combination
            {
                "gene": "katG",
                "property": "Antibiotic Resistance",
                "source": "NDARO",
                "mechanism": "target alteration",
                "product": "catalase-peroxidase",
            },
        ]
        mock_sg = self._make_sg_response(sg_genes)
        mock_amr = self._make_amr_response([])
        mock_client = _mock_bvbrc_client([mock_sg, mock_amr])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")

        assert resp.status_code == 200
        # Duplicate should be removed
        assert len(resp.json()["amr_genes"]) == 1

    def test_aggregates_amr_phenotypes_by_antibiotic(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=1773, superkingdom="Bacteria")
        )

        amr_records = [
            {
                "antibiotic": "Isoniazid",
                "resistant_phenotype": "Resistant",
                "evidence": "AMR",
            },
            {
                "antibiotic": "Isoniazid",
                "resistant_phenotype": "Resistant",
                "evidence": "AMR",
            },
            {
                "antibiotic": "Isoniazid",
                "resistant_phenotype": "Susceptible",
                "evidence": "AMR",
            },
            {
                "antibiotic": "Rifampicin",
                "resistant_phenotype": "Resistant",
                "evidence": "AMR",
            },
        ]
        mock_sg = self._make_sg_response([])
        mock_amr = self._make_amr_response(amr_records)
        mock_client = _mock_bvbrc_client([mock_sg, mock_amr])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")

        assert resp.status_code == 200
        phenotypes = {p["antibiotic"]: p for p in resp.json()["amr_phenotypes"]}
        assert phenotypes["Isoniazid"]["resistant"] == 2
        assert phenotypes["Isoniazid"]["susceptible"] == 1
        assert phenotypes["Rifampicin"]["resistant"] == 1

        # Sorted by resistant count descending: Isoniazid (2) before Rifampicin (1)
        order = [p["antibiotic"] for p in resp.json()["amr_phenotypes"]]
        assert order.index("Isoniazid") < order.index("Rifampicin")

    def test_returns_empty_on_network_error(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=1773, superkingdom="Bacteria")
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            resp = TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["amr_genes"] == []
        assert data["virulence_factors"] == []
        assert data["amr_phenotypes"] == []

    def test_caches_result(self):
        app, db = make_app()
        db["taxa"].find_one = AsyncMock(
            return_value=make_taxon_doc(taxon_id=1773, superkingdom="Bacteria")
        )

        mock_sg = self._make_sg_response([])
        mock_amr = self._make_amr_response([])
        # Provide extra responses so the mock doesn't run out on second request
        mock_client = _mock_bvbrc_client([mock_sg, mock_amr, mock_sg, mock_amr])

        with patch("app.routers.taxa.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")
            TestClient(app).get("/api/v1/taxa/1773/bvbrc/specialty_genes")

            # Only 2 httpx calls (sg + amr) for the first request; second hits cache
            assert mock_client.get.call_count == 2
