==================
Ingesting data
==================

The ``ingest.py`` CLI loads pipeline output into meta-vis-app. It supports
two pipelines, each with its own subcommand:

- ``taxprofiler`` — nf-core/taxprofiler shotgun metagenomics output
- ``trana`` — Trana 16S amplicon (ONT, Emu) output

Run ``python ingest.py --help`` for the full reference.

How it works
============

The CLI packages every referenced input file into a single ``tar.gz`` bundle
and posts it as multipart upload to the backend. The server materialises the
bundle in a temp directory and runs the ingestion orchestrator against those
files. Every file is parsed into a Pydantic model before any database write —
malformed input fails fast with a validation error.

This shape means the CLI can run anywhere with network access to the backend
(your laptop, a CI job, a pipeline post-processing step) — it does not need
direct database access.

Authentication
==============

The CLI obtains a Keycloak access token before each run. Two grants are
supported and auto-selected from the environment:

- **client_credentials** (preferred for automation) — used when
  ``KEYCLOAK_CLIENT_SECRET`` is set. The CLI's Keycloak client must be
  confidential with service accounts enabled. The service account must
  hold the ``admin`` (or at minimum ``writer``) role on the role client
  configured in ``KEYCLOAK_ROLE_CLIENT``.
- **password grant** (fallback for local dev) — used when
  ``KEYCLOAK_USERNAME`` and ``KEYCLOAK_PASSWORD`` (or ``--password``)
  are set instead of a client secret.

Environment variables:

.. code-block:: text

   KEYCLOAK_URL              base URL, e.g. https://<kc-host>
   KEYCLOAK_REALM            realm name
   KEYCLOAK_CLI_CLIENT_ID    confidential client (default: meta-vis-cli)
   KEYCLOAK_ROLE_CLIENT      client whose roles drive authz (default: meta-vis-frontend)
   KEYCLOAK_CLIENT_SECRET    enables client_credentials when set
   KEYCLOAK_USERNAME         password-grant fallback
   KEYCLOAK_PASSWORD         password-grant fallback
   META_VIS_API              backend base URL, e.g. https://<backend-host>

The defaults target the local-dev stack (``http://localhost:8081``, realm
``meta-vis``, backend ``http://localhost:8000``). For a fully-local smoke
test, ``make keycloak-up && make up`` and use ``--password dev-admin`` — no
environment variables required.

taxprofiler ingest
==================

A minimal command:

.. code-block:: bash

   python ingest.py taxprofiler \
       --case-id my-case-001 \
       --multiqc /path/to/multiqc_data.json \
       --pipeline-info /path/to/software_versions.yml \
       --classifier "kraken2 db=k2_pluspf taxpasta=/path/kraken2.tsv krona=/path/kraken2.html" \
       --sample "sample_id=PE-04-28 subject_id=SUBJ-01 sex=F type=sample material=DNA column_kraken2=PE-04-28_k2_pluspf" \
       --password dev-admin

**Required arguments**

==========================  =============================================================
``--case-id``               Unique case identifier
``--multiqc``               Path to ``multiqc_data.json``
``--pipeline-info``         Path to ``software_versions.yml`` (or nf-core equivalent)
``--classifier`` (≥ 1)      One per classifier — see the format below
``--sample`` (≥ 1)          One per sample — see the format below
==========================  =============================================================

**Optional arguments**

==========================  =============================================================
``--order-date YYYY-MM-DD`` Date samples were ordered (defaults to today)
``--metaval-igv PATH``      Path to a metaval ``igv/`` output directory
``--quiet``                 Suppress progress output
==========================  =============================================================

**Classifier spec** — one ``--classifier`` per tool:

.. code-block:: text

   --classifier "<name> db=<db> taxpasta=<path> [krona=<path>]"

- ``name`` — ``kraken2``, ``centrifuge``, or ``diamond``
- ``db`` — database identifier (e.g. ``k2_pluspf``)
- ``taxpasta`` — merged TSV from taxpasta
- ``krona`` — optional Krona HTML (not applicable to DIAMOND)

**Sample spec** — one ``--sample`` per sample:

.. code-block:: text

   --sample "sample_id=<id> [subject_id=<id>] [sex=<F|M|unknown>] \
             type=<sample|positive_ctrl|negative_ctrl> \
             material=<DNA|RNA> \
             column_<classifier>=<taxpasta-column>"

The ``column_<classifier>=`` mapping is mandatory because taxprofiler
appends classifier/db suffixes to taxpasta column names, and the CLI cannot
derive them reliably. Inspect the TSV header to find the exact name.

trana ingest
============

The Trana pipeline produces per-sample Emu rel-abundance files plus optional
NanoPlot stats:

.. code-block:: bash

   python ingest.py trana \
       --case-id trana-run-001 \
       --pipeline-info /path/to/software_versions.yml \
       --sample "sample_id=S1 subject_id=SUBJ-01 sex=F type=sample material=DNA \
                 abundance_path=/path/to/S1_rel-abundance.tsv \
                 nanoplot_path=/path/to/S1_NanoStats.txt" \
       --password dev-admin

The ``--sample`` spec carries the file paths inline. ``nanoplot_path=`` is
optional; ``abundance_path=`` is required.

Re-ingesting a case
===================

``case_id`` is unique. To re-ingest, delete the existing case first (Admin
panel in the UI, or the API), then run the ingest command again. Blobs are
removed from object storage as part of case deletion.

Bulk ingestion
==============

Wrap the CLI in a shell loop and re-use the same environment:

.. code-block:: bash

   for case in case-001 case-002 case-003; do
       python ingest.py taxprofiler --case-id "$case" \
           --multiqc "/data/$case/multiqc_data.json" \
           --pipeline-info "/data/$case/pipeline_info/software_versions.yml" \
           ...
   done

The CLI exits non-zero on any validation failure, so checking ``$?`` after
each call works for error handling.

When things go wrong
====================

The server validates input with Pydantic before any write. Most issues
surface as a 4xx response with the failing field in the body — read the
response, fix the input, retry.

Common ones:

- **"Case already exists"** — delete the case first, then re-ingest.
- **"Column not found"** — the ``column_<classifier>=`` value does not match
  any column in the taxpasta TSV. Column names are case-sensitive.
- **"File not found"** — every path in ``--classifier`` / ``--sample`` /
  ``--multiqc`` etc. must exist when the CLI runs (the bundle is built
  client-side).
- **401 / "Invalid or expired token"** — the Keycloak credentials in the
  environment can't obtain a token. Check ``KEYCLOAK_URL``, ``KEYCLOAK_REALM``,
  and either ``KEYCLOAK_CLIENT_SECRET`` or username/password.

See also
========

- :doc:`taxonomy-reference` — load the NCBI taxonomy reference data
- :doc:`audit-log` — every ingest is recorded as an audit event
- :doc:`../developer/architecture` — what happens server-side
