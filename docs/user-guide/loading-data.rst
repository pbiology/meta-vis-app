===============
Loading data
===============

Two CLIs load data into the app: ``ingest.py`` for case ingest, and
``load_taxonomy.py`` for the NCBI taxonomy reference. Both run against
a backend reachable over the network — they do not require direct
database access.

Case ingest
===========

``ingest.py`` packages every referenced input file into a single
``tar.gz`` bundle and posts it as multipart upload to the backend. The
server materialises the bundle in a temp directory and runs the
ingestion orchestrator against those files. Every file is parsed into
a Pydantic model before any database write — malformed input fails
fast with a validation error.

Two supported pipelines, each with its own subcommand:

- ``taxprofiler`` — nf-core/taxprofiler shotgun metagenomics output
- ``trana`` — Trana 16S amplicon (ONT, Emu) output

Run ``python ingest.py --help`` for the authoritative reference.

Authentication
--------------

The CLI obtains a Keycloak access token before each run. Two grants
are supported and auto-selected from the environment:

- **client_credentials** (preferred for automation) — used when
  ``KEYCLOAK_CLIENT_SECRET`` is set. The CLI's Keycloak client must be
  confidential with service accounts enabled. The service account
  needs the ``admin`` (or at minimum ``writer``) role on the role
  client in ``KEYCLOAK_ROLE_CLIENT``.
- **password grant** (fallback for local dev) — used when
  ``KEYCLOAK_USERNAME`` and ``KEYCLOAK_PASSWORD`` (or ``--password``)
  are set instead of a client secret.

Environment variables::

   KEYCLOAK_URL              base URL, e.g. https://<kc-host>
   KEYCLOAK_REALM            realm name
   KEYCLOAK_CLI_CLIENT_ID    confidential client (default: meta-vis-cli)
   KEYCLOAK_ROLE_CLIENT      client whose roles drive authz (default: meta-vis-frontend)
   KEYCLOAK_CLIENT_SECRET    enables client_credentials when set
   KEYCLOAK_USERNAME         password-grant fallback
   KEYCLOAK_PASSWORD         password-grant fallback
   META_VIS_API              backend base URL, e.g. https://<backend-host>

The defaults target the local-dev stack (``http://localhost:8081``,
realm ``meta-vis``, backend ``http://localhost:8000``). For a fully
local smoke test, ``make keycloak-up && make up`` and use
``--password dev-admin``.

taxprofiler ingest
------------------

.. code-block:: bash

   python ingest.py taxprofiler \
       --case-id my-case-001 \
       --multiqc /path/to/multiqc_data.json \
       --pipeline-info /path/to/software_versions.yml \
       --classifier "kraken2 db=k2_pluspf taxpasta=/path/kraken2.tsv krona=/path/kraken2.html" \
       --sample "sample_id=PE-04-28 subject_id=SUBJ-01 sex=F type=sample material=DNA column_kraken2=PE-04-28_k2_pluspf" \
       --password dev-admin

**Required**

==========================  ===============================================================
``--case-id``               Unique case identifier
``--multiqc``               Path to ``multiqc_data.json``
``--pipeline-info``         Path to ``software_versions.yml`` (or nf-core equivalent)
``--classifier`` (≥ 1)      One per classifier — format below
``--sample`` (≥ 1)          One per sample — format below
==========================  ===============================================================

**Optional**

==========================  ===============================================================
``--order-date YYYY-MM-DD`` Date samples were ordered (defaults to today)
``--metaval-igv PATH``      Path to a metaval ``igv/`` output directory
``--quiet``                 Suppress progress output
==========================  ===============================================================

**Classifier spec** — one per tool::

   --classifier "<name> db=<db> taxpasta=<path> [krona=<path>]"

- ``name`` — ``kraken2``, ``centrifuge``, or ``diamond``
- ``db`` — database identifier (e.g. ``k2_pluspf``)
- ``taxpasta`` — merged TSV from taxpasta
- ``krona`` — optional Krona HTML (not applicable to DIAMOND)

**Sample spec** — one per sample::

   --sample "sample_id=<id> [subject_id=<id>] [sex=<F|M|unknown>] \
             type=<sample|positive_ctrl|negative_ctrl> \
             material=<DNA|RNA> \
             column_<classifier>=<taxpasta-column>"

The ``column_<classifier>=`` mapping is mandatory because taxprofiler
appends classifier/db suffixes to taxpasta column names, and the CLI
cannot derive them reliably. Inspect the TSV header to find the exact
name.

trana ingest
------------

.. code-block:: bash

   python ingest.py trana \
       --case-id trana-run-001 \
       --pipeline-info /path/to/software_versions.yml \
       --sample "sample_id=S1 subject_id=SUBJ-01 sex=F type=sample material=DNA \
                 abundance_path=/path/to/S1_rel-abundance.tsv \
                 nanoplot_path=/path/to/S1_NanoStats.txt" \
       --password dev-admin

The ``--sample`` spec carries file paths inline. ``nanoplot_path=`` is
optional; ``abundance_path=`` is required.

Re-ingesting and bulk ingest
----------------------------

``case_id`` is unique. To re-ingest, delete the existing case first
(Admin panel or API), then run the command again — case deletion
removes blobs from object storage as part of the cleanup.

For bulk loads, wrap the CLI in a shell loop and re-use the same
environment. The CLI exits non-zero on validation failure, so checking
``$?`` after each call works for error handling.

Common errors
-------------

- **"Case already exists"** — delete first, then re-ingest.
- **"Column not found"** — ``column_<classifier>=`` does not match a
  column in the taxpasta TSV. Names are case-sensitive.
- **"File not found"** — every path passed to the CLI must exist when
  the bundle is built (client-side).
- **401 / "Invalid or expired token"** — Keycloak credentials cannot
  obtain a token. Check ``KEYCLOAK_URL``, ``KEYCLOAK_REALM``, and
  either ``KEYCLOAK_CLIENT_SECRET`` or username/password.

Taxonomy reference
==================

NCBI taxonomy provides organism names, lineages, and ranks. The app
ships ``load_taxonomy.py`` to populate or refresh the ``taxa``
collection.

In the dev stack:

.. code-block:: bash

   make load-taxonomy

That runs ``python load_taxonomy.py`` inside the backend container.
On bare metal:

.. code-block:: bash

   conda activate meta-vis-app
   cd backend
   python load_taxonomy.py

What happens:

1. Downloads ``new_taxdump.tar.gz`` (~110 MB) from NCBI.
2. Parses the taxonomy dump.
3. Bulk-upserts ~2.4 million records into the ``taxa`` collection.
4. Takes 10–20 minutes depending on disk and network.

Safe to re-run — existing entries are updated; clinical notes on
existing taxa are preserved.

Scheduling
----------

NCBI publishes a new taxonomy dump on the 1st of each month. A simple
monthly cron run is enough:

.. code-block:: text

   0 3 2 * *  cd /path/to/meta-vis-app && /path/to/conda/envs/meta-vis-app/bin/python backend/load_taxonomy.py

Run at 03:00 on the 2nd of the month — that gives NCBI's mirrors time
to settle after the 1st-of-month publish.

Stale records and clinical notes
--------------------------------

Taxa first seen during ingest, before any ``load_taxonomy.py`` run,
are stored with ``taxdump_version: null``. The taxon detail page shows
a "Created before official taxonomy load" banner for these; running
the loader fills in the missing fields.

Each taxon entry has a free-text ``clinical_notes`` field that admins
can edit from the taxon detail page. Notes live on the taxon document,
not on the imported NCBI record, and are preserved across taxonomy
updates.

Failure modes:

- **Download fails** — NCBI's FTP mirror is occasionally unreachable.
  Retry.
- **Disk space** — the loader needs ~1 GB temp space for the download
  and extraction.
- **MongoDB unreachable** — same fix as for the API; the script reads
  the same ``backend/.env``.

See also
========

- :doc:`reviewing-cases` — what the ingested data looks like in the UI
- :doc:`investigating-detections` — where the taxonomy reference shows up
- :doc:`administration` — every ingest is recorded in the audit log
