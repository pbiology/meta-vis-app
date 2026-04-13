==============
Architecture
==============

High-level overview of meta-vis-app's design.

System components
=================

.. code-block:: text

   ┌─────────────────────────────────────────┐
   │      Frontend (React 18 + Vite)        │
   │     http://localhost:5173              │
   └──────────────────┬──────────────────────┘
                      │
                      │ HTTP/REST
                      │ CORS enabled
                      │
   ┌──────────────────▼──────────────────────┐
   │      Backend (FastAPI + Uvicorn)       │
   │      http://localhost:8000             │
   │      - Authentication (JWT)            │
   │      - API endpoints                   │
   │      - Business logic                  │
   └──────────────────┬──────────────────────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
          │           │           │
          ▼           ▼           ▼
      MongoDB      MinIO/S3    NCBI FTP
      (localhost)  (optional)  (taxonomy)
      (Docker)     (Docker)

   External APIs (on-demand, cached 24 h):
      NCBI Datasets API   — external links per taxon
      NCBI E-Utilities    — PubMed literature per taxon
      BV-BRC API          — genome summary, AMR genes, virulence factors per taxon

Frontend architecture
=====================

**Technology:**
- React 18 (UI framework)
- Vite (build tool, dev server)
- Tailwind CSS (styling)
- Axios (HTTP client)
- React Router (navigation)

**Key directories:**

.. code-block:: text

   frontend/src/
   ├── api/           - API client modules
   ├── components/    - Reusable React components
   ├── context/       - React Context (auth state)
   ├── pages/         - Full-page components
   ├── App.jsx        - Main app component
   └── main.jsx       - Entry point

**Data flow:**

1. User interacts with UI (click, type, submit)
2. Component calls API function (e.g., ``getCases()``)
3. API function makes HTTP request to backend
4. Backend responds with JSON
5. Component updates state with response
6. React re-renders component

**Authentication:**
- JWT token stored in localStorage
- Included in all API requests as ``Authorization: Bearer <token>``
- Refreshed on login
- Cleared on logout

Backend architecture
====================

**Technology:**
- FastAPI (web framework)
- Motor (async MongoDB driver)
- Pydantic (data validation)
- PyYAML (config parsing)
- Boto3 (S3 client)

**Key directories:**

.. code-block:: text

   backend/app/
   ├── main.py              - FastAPI app setup
   ├── config.py            - Configuration
   ├── database.py          - MongoDB client
   ├── blob_store.py        - S3/blob storage
   ├── auth/                - Authentication utils
   ├── ingestor/            - Ingestion logic
   ├── models/              - Pydantic models
   └── routers/             - API endpoints
       ├── auth.py          - Login/logout
       ├── cases.py         - Case operations
       ├── samples.py       - Sample operations
       ├── taxonomy/        - Taxonomy operations
       ├── metaval.py       - metaval integration
       ├── alerts.py        - Outbreak detection
       ├── users.py         - User management
       └── ingest.py        - Ingest endpoint

**Async design:**
- All I/O operations are async (database, file uploads)
- Uses ``asyncio`` for concurrent operations
- Motor driver provides async MongoDB access
- Faster response times, handles more concurrent requests

**API design:**
- RESTful endpoints (GET, POST, PUT, DELETE)
- JSON request/response format
- Pydantic models for validation
- OpenAPI/Swagger docs at ``/docs``

Database design
===============

**MongoDB:**
- Document-oriented (JSON-like data)
- No fixed schema (flexible)
- Indexes on frequently queried fields

**Collections:**

.. code-block:: text

   cases/            - One doc per pipeline run
   samples/          - One doc per sample
   blobs/            - Krona HTML, IGV reports (if using MongoDB backend)
   metaval_results/  - BLAST results, metadata
   users/            - User accounts, hashed passwords
   taxa/             - NCBI taxonomy reference
   outbreak_ignorelist/  - Ignored taxa for alerts

**Key fields:**

Cases collection:

.. code-block:: javascript

   {
     _id: ObjectId,
     case_id: "case-001",
     order_date: ISODate,
     samples: [sample_id_list],
     classifiers: ["kraken2", "centrifuge"],
     reviewed: false,
     notes: "...",
     created_at: ISODate,
     created_by: "admin"
   }

Samples collection:

.. code-block:: javascript

   {
     _id: ObjectId,
     case_id: "case-001",
     sample_id: "SRR001",
     type: "sample",
     material: "DNA",
     qc_metrics: {
       read_count: 1000000,
       q30_percentage: 95.5,
       host_removal_percentage: 42.1
     },
     profiles: {
       kraken2: [...]  // taxonomy data
     }
   }

Authentication flow
===================

**Login:**

.. code-block:: text

   1. User submits username + password
   2. Backend hashes password, compares to stored hash
   3. If match, generates JWT token
   4. Returns token to frontend
   5. Frontend stores in localStorage
   6. Subsequent requests include token

**JWT token:**
- Signed with JWT_SECRET from .env
- Contains user info (username, role)
- Expires after configured time
- Used for API authentication

**Password hashing:**
- Using bcrypt (industry standard)
- Salted and iterated for security
- No plaintext passwords stored

Ingestion pipeline
==================

**High-level flow:**

.. code-block:: text

   1. User runs ingest.py with parameters
   2. Script reads input files:
      - MultiQC JSON (QC metrics)
      - Software versions YAML (pipeline info)
      - taxpasta TSV (taxonomy)
      - Krona HTML (visualization)
      - metaval results (optional)
   3. Parses and validates data
   4. Creates Case and Sample documents
   5. Uploads Krona/IGV HTML to blob store
   6. Inserts documents into MongoDB
   7. Invalidates outbreak alert cache

**Key components:**

.. code-block:: text

   ingest.py                - CLI entry point
   orchestrator.py          - Orchestrates ingest steps
   multiqc_reader.py        - Parses MultiQC output
   pipeline_info_reader.py  - Parses version files
   taxpasta_reader.py       - Parses taxonomy TSV
   metaval_reader.py        - Parses metaval results

Outbreak detection
==================

**Architecture:**

1. **MongoDB aggregation** - Runs query entirely in database
2. **Sliding window** - In-memory clustering by order_date
3. **Caching** - Results cached for 1 hour
4. **Invalidation** - Cache cleared on new ingest or ignorelist change

**Query flow:**

.. code-block:: text

   1. Get time window (7, 14, or 30 days)
   2. MongoDB aggregation:
      a. Match cases in time window
      b. Unwind sample arrays
      c. Filter to qualifying viral taxa
      d. Group by taxon, collect cases
      e. Filter to taxa in 2+ cases
   3. Return to Python
   4. Cluster cases by order_date
   5. Cache for 1 hour
   6. Return to API

**Performance:**
- Query time O(n) where n = cases in window
- Caching makes repeated queries instant
- Bounded by time window, not total case count

Object storage
==============

**Two backends:**

1. **MongoDB** (default)
   - Stores blobs in ``blobs`` collection
   - Simple, no external service
   - Limited for large deployments

2. **S3-compatible** (recommended for production)
   - MinIO (local Docker) or AWS S3
   - Key structure: ``meta-vis/krona/{case_id}/{classifier}.html``
   - Keeps MongoDB lean and fast

**Abstraction:**

``blob_store.py`` provides unified interface:

.. code-block:: python

   async def upload_blob(path: str, data: bytes) -> None
   async def download_blob(path: str) -> bytes

Automatically chooses MongoDB or S3 based on config.

Error handling
==============

**Strategy:**
- Validation at API boundaries (Pydantic models)
- Try/except around I/O operations
- Log errors with context
- Return appropriate HTTP status codes
- Frontend displays errors to user

**Status codes:**
- 200 OK - Success
- 400 Bad Request - Validation failed
- 401 Unauthorized - Not authenticated
- 403 Forbidden - Not authorized
- 404 Not Found - Resource doesn't exist
- 500 Internal Server Error - Server error

Testing
=======

**Structure:**

.. code-block:: text

   tests/
   ├── unit/           - Unit tests (isolated functions)
   ├── integration/    - Integration tests (with database)
   └── conftest.py     - Pytest fixtures

**Running tests:**

.. code-block:: bash

   pytest tests/                    # All tests
   pytest tests/unit/               # Unit only
   pytest tests/integration/        # Integration only
   pytest -v                        # Verbose
   pytest --cov                     # Coverage report

**Mocking:**
- ``mongomock`` for MongoDB
- Fixtures for common test data
- See ``conftest.py`` for setup

External API integrations
=========================

Several ``/taxa/{id}/`` sub-routes proxy requests to external databases, aggregate the
results, and return them to the frontend. All use the same pattern:

- **httpx.AsyncClient** for async HTTP calls with a 15-second timeout
- **In-memory cache** keyed by ``taxon_id`` (and any query params), TTL 24 hours
- **Graceful degradation** — any network error returns an empty result rather than a 500

.. code-block:: text

   Endpoint                               External service         Cache TTL
   ─────────────────────────────────────────────────────────────────────────
   GET /taxa/{id}/external_links          NCBI Datasets API        24 h
   GET /taxa/{id}/literature              NCBI E-Utilities PubMed  24 h
   GET /taxa/{id}/bvbrc/genomes           BV-BRC genome API        24 h
   GET /taxa/{id}/bvbrc/specialty_genes   BV-BRC sp_gene           24 h
                                          + genome_amr APIs

**BV-BRC (Bacterial and Viral Bioinformatics Resource Center)**
  Public REST API at ``https://www.bv-brc.org/api/``. No API key required.
  Uses NCBI taxon IDs natively, so the local ``taxon_id`` maps directly.

  Two routes:

  ``GET /taxa/{id}/bvbrc/genomes``
    Queries ``/api/genome/`` with ``eq(taxon_lineage_ids, {id})`` to capture all
    strain-level genomes under a species. Aggregates isolation sources, countries,
    and AMR genome counts (top 10 each, bounded at 1 000 genomes fetched).

  ``GET /taxa/{id}/bvbrc/specialty_genes``
    Fires two concurrent requests via ``asyncio.gather`` using ``eq(taxon_id, {id})``
    (exact taxon match — unlike the genomes endpoint, lineage IDs are not supported here):

    - ``/api/sp_gene/`` with ``limit(500)`` — returns specialty gene records.
      The ``property`` field is filtered client-side to *Antibiotic Resistance* and
      *Virulence Factor* because BV-BRC's SOLR ``in()`` operator does not handle
      multi-word text values correctly; all records are fetched and filtered in Python.
      Results are deduplicated by ``(gene, property)``.
    - ``/api/genome_amr/`` with ``limit(1000)`` — aggregated into per-antibiotic
      resistant/susceptible counts.

  Cache keys: ``_bvbrc_genomes_cache`` and ``_bvbrc_specialty_cache`` in
  ``app/routers/taxa.py``.

Scaling considerations
======================

**Horizontal scaling:**
- Multiple backend instances behind load balancer
- Shared MongoDB (managed service recommended)
- Shared object storage (MinIO cluster or AWS S3)
- No local state on backend

**Vertical scaling:**
- Increase server RAM
- More backend workers: ``--workers 8``
- MongoDB index optimization
- SSD storage for better I/O

**Caching:**
- Outbreak alerts cached in-memory
- Could be distributed (Redis) for multi-instance

**Database optimization:**
- Indexes on frequently queried fields
- Periodic index rebuild
- Archive old cases to separate database
- Monitor query performance

Next steps
==========

- :doc:`data-model` - Detailed data structure reference
- :doc:`contributing` - Development setup and workflow
- :doc:`performance` - Performance tuning and optimization
