==============
Architecture
==============

A working overview of how Meta-vis is structured. The goal of this page
is that a new developer can read it once and know where to look next; the
specifics live in the code.

System overview
===============

.. code-block:: text

   ┌─────────────────────────────────────────────┐
   │  Frontend — React 18 + TypeScript + Vite    │
   │  Auth: OIDC (PKCE) against Keycloak         │
   └──────────────────┬──────────────────────────┘
                      │ HTTPS, JSON, Bearer token
                      ▼
   ┌─────────────────────────────────────────────┐
   │  Backend — FastAPI + Motor (async)          │
   │  Auth: validates Bearer tokens (Keycloak    │
   │  JWKS); roles read from resource_access     │
   └─┬──────────┬─────────────┬──────────────────┘
     │          │             │
     ▼          ▼             ▼
   MongoDB   MinIO / S3    External APIs
   (cases,   (Krona HTML,  (on-demand, 24 h cache):
   samples,  IGV reports — NCBI Datasets, NCBI
   audit,    optional;     E-Utilities (PubMed),
   blobs…)   falls back    BV-BRC genome / sp_gene
             to MongoDB    / genome_amr
             ``blobs``
             collection)

The frontend is a single-page app served as a static bundle. The backend
exposes a JSON API under ``/api/v1``; everything except a couple of public
health probes requires a Keycloak-issued Bearer token.

Frontend
========

Stack: React 18, TypeScript (``.tsx`` / ``.ts``), Vite, Tailwind CSS,
React Router, Axios, ``oidc-client-ts`` for the auth flow.

Layout::

   frontend/src/
   ├── api/           Axios modules per backend resource (cases.ts, samples.ts, …)
   ├── components/    Reusable UI (Badge, Layout, MetricCard, …)
   ├── context/       AuthContext.tsx — token + user, localStorage-backed
   ├── hooks/         Custom React hooks
   ├── lib/           Small utilities
   ├── oidc.ts        OIDC client setup (issuer, client, redirect URIs)
   ├── pages/         Full-page route components
   ├── App.tsx        Routes
   └── main.tsx       Entry point

Authentication is OIDC against Keycloak with PKCE. The SPA redirects to the
realm, gets an access token, and includes it as ``Authorization: Bearer …``
on every API call. The token's ``resource_access[<role_client>].roles``
claim drives UI authz (``reader`` / ``writer`` / ``admin``) — there are no
local credentials.

The Vite-bundled OIDC config (authority, client id, redirect URIs) is
**baked into the build**. Changing it means rebuilding the image. See
:doc:`../deployment/environment` for which ``VITE_*`` variables matter.

Backend
=======

Stack: FastAPI, Motor (async MongoDB), Pydantic v2, PyJWT (with
``PyJWKClient``), Boto3 (S3), httpx (external APIs).

Layout::

   backend/app/
   ├── main.py             FastAPI app, CORS, router registration
   ├── config.py           Pydantic Settings (.env, outbreak configs)
   ├── database.py         Motor client, index creation, blob store init
   ├── blob_store.py       S3 / MongoDB blob abstraction
   ├── audit.py            Append-only audit-log writes
   ├── cache.py            Per-collection in-memory caches (e.g. outbreak alerts)
   ├── db_utils.py         Shared Mongo query helpers
   ├── middleware.py       Request-scoped context (request id, user)
   ├── logging_config.py   Structured JSON-line logging
   ├── taxonomy_utils.py   Shared taxonomy helpers (ranks, parents)
   ├── constants.py
   ├── auth/
   │   └── utils.py        Keycloak token validation, role extraction
   ├── ingestor/           See "Ingest" below
   ├── models/             Pydantic models — case, sample, qc, taxonomy, …
   └── routers/            Resource-shaped API endpoints

Routers, one file per resource: ``auth``, ``cases``, ``samples``,
``subjects``, ``ingest``, ``metaval``, ``alerts``, ``taxa``, ``ntc``,
``users``, ``config``, ``health``.

Everything is async — Motor for the database, httpx for outbound HTTP, and
asyncio-aware blob uploads. The event loop is never blocked by I/O.

Validation at every boundary
----------------------------

This is the load-bearing rule. The app handles clinical data and must fail
loudly on bad input rather than silently corrupting state:

- Every API request and response body is a Pydantic model in ``app/models/``.
- Every ingest file (MultiQC JSON, taxpasta TSV, Emu rel-abundance TSV,
  pipeline-info YAML, metaval JSON) is parsed *into* a Pydantic model before
  any database write — see ``app/ingestor/inputs.py`` and the per-reader
  modules.
- The same models are reused for response bodies, so the shape that comes
  out of the API matches the shape that went in.

Configuration is itself a Pydantic ``Settings`` class — a malformed or
incomplete ``.env`` fails fast at startup with a validation error, not a
500 mid-request.

Authentication
==============

Keycloak / OIDC. The backend has no user store of its own and no password
hashing — both lived in earlier versions and are gone.

On every protected request:

1. ``Authorization: Bearer …`` is extracted (FastAPI dependency).
2. The token's signature is verified against the realm's JWKS (cached via
   ``PyJWKClient`` — handles key rotation through the ``kid`` header).
3. ``iss`` must equal ``KEYCLOAK_ISSUER``; ``azp`` must be in
   ``KEYCLOAK_CLIENT_IDS``.
4. The user's role is the highest of
   ``resource_access[KEYCLOAK_ROLE_CLIENT].roles`` intersected with
   ``{admin, writer, reader}`` — see ``ROLE_PRIORITY`` in
   ``app/auth/utils.py``.

The CLI follows the same model: ``ingest.py`` obtains a token from Keycloak
(client-credentials grant for automation, password grant for local dev) and
posts the bundle to ``/api/v1/ingest/...`` with that token.

The ``users`` MongoDB collection still exists, but it holds app-side
metadata (display name, last seen) keyed on the Keycloak ``sub``. It is
not an identity source.

Database
========

MongoDB 7.0. Document-oriented; we lean into that — the per-sample
taxonomic profile is embedded directly in the sample document.

==========================  ========================================================
Collection                  Purpose
==========================  ========================================================
``cases``                   One doc per pipeline run (unique index on ``case_id``)
``samples``                 One doc per sample, with the full taxonomic profile
``subjects``                Patient/subject metadata shared across cases
``blobs``                   Krona HTML / IGV reports — fallback when S3 is unset
``metaval_results``         BLASTN alignments + IGV metadata per detection
``users``                   App-side user metadata, keyed by Keycloak ``sub``
``taxa``                    NCBI taxonomy reference (populated by ``load_taxonomy.py``)
``outbreak_ignorelist``     Taxa excluded from outbreak alerts
``known_pathogens``         Curated pathogen reference list
``ntc_ignorelist``          Taxa excluded from NTC tracking
``ntc_known_contaminants``  Known contaminants tracked in NTC QC
``audit_log``               Append-only event log (see :doc:`../user-guide/administration`)
==========================  ========================================================

Indexes are created in ``database.py::_ensure_indexes()`` and run at every
startup — the function is idempotent, so it's safe to point the backend at
a new database without a separate migration step.

For prod deployments the recommended topology is a replica set so
multi-document transactions (used by the ingest orchestrator for
case-level atomicity) work. With ``MONGODB_USE_TRANSACTIONS=false`` a
mid-ingest failure can leave partial writes behind. See
:doc:`../deployment/production`.

Blob storage
============

Krona HTML and IGV reports are large (can be > 100 MB each). ``app/blob_store.py``
abstracts over two backends:

- **MongoDB** (default if ``OBJECT_STORAGE_ENDPOINT`` is unset) — blobs go
  into the ``blobs`` collection. Zero setup; bloats the working set.
- **S3-compatible** (MinIO, AWS S3, …) — preferred for production. Keys are
  hierarchical: ``meta-vis/krona/{case_oid}/{classifier}.html``,
  ``meta-vis/igv/{case_oid}/{sample}/{classifier}/{organism}.html``.

The backend chooses based on environment alone; no code change is required
to switch. Blobs ingested under one backend are not visible to the other —
switching production backends means re-ingestion. See
:doc:`../deployment/object-storage`.

Ingest
======

Two supported pipelines, each with its own CLI subcommand and reader
modules. The CLI runs anywhere with network access to the backend; the
heavy lifting is server-side.

::

   python ingest.py taxprofiler --case-id … --multiqc … --classifier … --sample …
   python ingest.py trana       --case-id … --pipeline-info … --sample …

Wire flow:

1. **CLI** (``ingest.py``) packages every referenced file into a tar.gz and
   POSTs it as multipart to ``/api/v1/ingest/{taxprofiler,trana}``.
2. **Loader** (``app/ingestor/loader.py``) materialises the bundle into a
   tmp dir and constructs the Pydantic ``IngestInputs`` model.
3. **Orchestrator** (``app/ingestor/orchestrator.py``) drives the
   per-pipeline reader chain:

   - taxprofiler: ``multiqc_reader`` (QC stats), ``taxpasta_reader``
     (per-classifier profiles), ``pipeline_info_reader``, optional
     ``metaval_reader``.
   - trana: ``emu_reader`` (16S abundance), optional ``nanoplot_reader``
     (ONT QC), ``pipeline_info_reader``.

4. Each reader returns Pydantic models. The orchestrator wraps the Mongo
   inserts in a single transaction (when transactions are enabled) so a
   case is either fully ingested or not at all.
5. On success the outbreak-alert cache is invalidated.

Sample-name normalisation is the known fragile spot — taxprofiler appends
classifier/db suffixes to sample names, so the CLI requires explicit
``column_*=`` mappings per sample. See ``TECHNICAL_DEBT.md``.

Outbreak detection
==================

Surfaced via the ``alerts`` router. Mostly Mongo aggregation, then a small
Python pass:

1. Pull configurable time window (7 / 14 / 30 days) and per-taxon thresholds
   from ``settings.outbreak_configs`` (loaded once from
   ``outbreak_configs.json``).
2. Aggregation pipeline: match cases in window → unwind sample profiles →
   filter to qualifying viral taxa → group by taxon → keep taxa in ≥ 2
   cases.
3. Python: cluster the matching cases by ``order_date`` (sliding window) to
   produce the alerts list.
4. Result is cached in-memory for one hour. Cache is invalidated on any
   new ingest or ignorelist change.

The hot path is bounded by the time window, not the total case count, so
the dataset can grow without slowing alerts.

Audit log
=========

``app/audit.py`` writes append-only events to the ``audit_log`` collection
for every state-changing action: logins (success and failure), case
ingest, case mutation, ignorelist edits, user-role changes. Events carry
the request id, user ``sub``, action name, and a structured payload.

The same events are also emitted as structured JSON log lines, so a log
aggregator (Loki / ELK / Splunk) holds a second independent copy. If the
DB write fails, the log line includes ``"message": "Failed to write audit
event to database"`` so you can alert on it. See
:doc:`../user-guide/administration`.

External API integrations
=========================

Several ``/taxa/{id}/`` sub-routes aggregate data from public sources. All
follow the same pattern: ``httpx.AsyncClient`` with a 15-second timeout,
in-memory cache keyed by taxon id (and any query params, TTL 24 h), and
graceful degradation — a network error returns an empty result, never a
500.

==========================================  ===================================  =======
Endpoint                                    External service                     Cache
==========================================  ===================================  =======
``GET /taxa/{id}/external_links``           NCBI Datasets API                    24 h
``GET /taxa/{id}/literature``               NCBI E-Utilities (PubMed)            24 h
``GET /taxa/{id}/bvbrc/genomes``            BV-BRC ``/api/genome/``              24 h
``GET /taxa/{id}/bvbrc/specialty_genes``    BV-BRC ``sp_gene`` + ``genome_amr``  24 h
==========================================  ===================================  =======

The BV-BRC genomes route uses ``eq(taxon_lineage_ids, {id})`` to capture
strain-level genomes under a species (bounded at 1 000 records). The
specialty-genes route fires two concurrent requests via
``asyncio.gather``; the ``property`` field is filtered client-side
because BV-BRC's SOLR ``in()`` operator does not handle multi-word text
values correctly. Caches live in module-level dicts in
``app/routers/taxa.py``.

Testing
=======

``pytest`` with ``asyncio_mode = "auto"``. MongoDB is mocked via
``mongomock-motor``; tests live under ``backend/tests/`` mirroring the
source tree (``unit/`` and ``integration/``). Fixtures are in
``tests/conftest.py``.

Test inputs are inline or built into ``tmp_path`` — tests must not depend
on real pipeline output files on disk.

Where to look next
==================

- :doc:`../deployment/local-dev` — get the stack running
- :doc:`../deployment/environment` — every config knob
- :doc:`../user-guide/administration` — what the audit log captures
- ``CLAUDE.md`` — short notes on conventions and known fragility
