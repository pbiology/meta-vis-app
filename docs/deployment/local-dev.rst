================================
Local development environment
================================

The repo ships a Docker-first dev stack driven by a top-level ``Makefile``.
``make up`` brings up MongoDB, MinIO, the FastAPI backend (with auto-reload),
and the Vite frontend in one go. Keycloak runs in a separate compose stack
so you only start it when you want a fully-offline login.

.. warning::

   This stack is for **development only**. MongoDB runs as a single container
   with no replication, all data lives in Docker volumes, and ``make reset``
   (or ``docker compose down -v``) destroys everything. Never point this at
   production data.

Prerequisites
=============

- Docker Engine + Compose v2
- A clone of this repo
- ``backend/.env`` (gitignored — your secrets)
- ``frontend/.env`` (gitignored — Vite OIDC config)

The committed defaults live in ``backend/.env.dev`` (loaded automatically by
compose) and ``frontend/.env.example`` (template). The two gitignored files
are the only things you maintain by hand. See :doc:`environment` for the full
list of variables.

First-run setup
===============

.. code-block:: bash

   # Backend secrets (MongoDB passwords + JWT_SECRET)
   cp backend/.env.example backend/.env
   # Edit backend/.env and set at minimum:
   #   MONGO_ROOT_PASSWORD=<pick-something>
   #   MONGODB_PASSWORD=<pick-something>
   #   JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
   # For bare-metal dev, also set MONGODB_HOST=localhost. In Docker, the
   # compose file overrides this to point at the `mongodb` service.

   # Frontend OIDC config
   cp frontend/.env.example frontend/.env
   # The defaults work against the Clinical Genomics stage Keycloak (see
   # backend/.env.dev). For a fully-offline setup, see "Local Keycloak" below.

Day-to-day workflow
===================

Everything is one ``make`` target away. ``make help`` lists them all.

.. code-block:: bash

   make up          # Start the full stack in the background
   make ps          # See what's running
   make logs        # Follow logs from all services
   make down        # Stop containers, keep volumes (data preserved)
   make reset       # Stop containers AND remove volumes (data destroyed)

Foreground variants — handy when you want to see logs in your terminal:

.. code-block:: bash

   make dev         # Same as `make up` but in the foreground
   make dev-build   # Rebuild images first, then run in the foreground

Once everything is up:

================  =========================================================
Service           URL
================  =========================================================
Frontend          http://localhost:5173
Backend API       http://localhost:8000 (Swagger UI at ``/docs``)
MongoDB           ``mongodb://localhost:27017`` (admin via ``MONGO_ROOT_PASSWORD``)
MinIO API         http://localhost:9000
MinIO console     http://localhost:9001
Keycloak (opt.)   http://localhost:8081
================  =========================================================

Useful shells and helpers
=========================

.. code-block:: bash

   make backend-shell    # bash inside the backend container
   make frontend-shell   # sh inside the frontend container
   make mongo-shell      # mongosh as the admin user
   make minio-logs       # follow only MinIO logs

   make load-taxonomy    # Download + load NCBI taxonomy into the taxa collection
   make test             # Run pytest inside the backend container
   make lint             # ruff + mypy
   make format           # ruff --fix

Authentication: pick a Keycloak
================================

The app authenticates via Keycloak/OIDC. Two options for local dev:

**Option A — Clinical Genomics stage Keycloak (default)**
   ``backend/.env.dev`` and ``frontend/.env.example`` point at
   ``keycloak-stage.cg-orchestration.sys.scilifelab.se``. You need an account
   on that realm. No extra setup — ``make up`` and log in.

**Option B — Local Keycloak (fully offline)**
   Start a containerised Keycloak that imports the bundled
   ``keycloak/realm-export.json``:

   .. code-block:: bash

      make keycloak-up        # Keycloak on :8081, realm `meta-vis`
      make keycloak-logs      # follow KC logs
      make keycloak-down      # stop, keep state
      make keycloak-reset     # stop and re-import the realm on next up

   Then override the two KC URLs in ``backend/.env``:

   .. code-block:: ini

      KEYCLOAK_ISSUER=http://localhost:8081/realms/meta-vis
      KEYCLOAK_JWKS_URL=http://host.docker.internal:8081/realms/meta-vis/protocol/openid-connect/certs

   And in ``frontend/.env``:

   .. code-block:: ini

      VITE_OIDC_AUTHORITY=http://localhost:8081/realms/meta-vis

   Log in with the seeded account:

   - Username: ``dev-admin``
   - Password: ``dev-admin``

Smoke-testing with a sample ingest
==================================

The repo ships a small ``trana`` test bundle. Ingest it to verify the stack is
healthy end-to-end:

.. code-block:: bash

   python ingest.py trana \
       --case-id smoke-test \
       --pipeline-info backend/test-data/16S_trana/pipeline_info/software_versions.yml \
       --sample "sample_id=X1 type=sample material=DNA \
   abundance_path=backend/test-data/16S_trana/results/1234567890AB_downsampled.fastq_rel-abundance.tsv" \
       --password dev-admin

The ``--password`` flag uses Keycloak's password grant against the local
realm. If you're authenticating against the stage realm instead, use your
own account credentials.

Refer to :doc:`../user-guide/loading-data` for the full ingest CLI reference.

Resetting state
===============

.. code-block:: bash

   make reset             # wipe MongoDB + MinIO volumes
   make keycloak-reset    # wipe Keycloak volume (re-imports realm on next up)

.. danger::

   ``make reset`` and ``docker compose down -v`` permanently delete the
   ``audit_log`` collection along with everything else. Never run them
   against a deployment that holds data you need to keep.

Next steps
==========

- :doc:`environment` — every environment variable the app reads
- :doc:`object-storage` — when and how to switch to S3-compatible storage
- :doc:`production` — deploying to a real server
