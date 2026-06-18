====================
Taxonomy reference
====================

The app uses NCBI taxonomy as reference data for organism names, lineages,
and ranks. Reference data is populated by ``load_taxonomy.py`` and updated
periodically as NCBI publishes new releases.

Loading taxonomy data
=====================

In the dev stack:

.. code-block:: bash

   make load-taxonomy

That runs ``python load_taxonomy.py`` inside the backend container. On bare
metal:

.. code-block:: bash

   conda activate meta-vis-app
   cd backend
   python load_taxonomy.py

What it does:

1. Downloads ``new_taxdump.tar.gz`` (~110 MB) from NCBI.
2. Parses the taxonomy dump.
3. Bulk-upserts ~2.4 million records into the ``taxa`` collection.
4. Takes 10–20 minutes depending on disk and network.

Safe to re-run — existing entries are updated; clinical notes on existing
taxa are preserved.

Scheduling updates
==================

NCBI publishes a new taxonomy dump on the 1st of each month. A simple
monthly cron run is enough:

.. code-block:: text

   0 3 2 * *  cd /path/to/meta-vis-app && /path/to/conda/envs/meta-vis-app/bin/python backend/load_taxonomy.py

Run at 03:00 on the 2nd of each month — that gives NCBI's mirrors time to
settle after the 1st-of-month publish.

Stale records
=============

Taxa first seen during ingest, before any ``load_taxonomy.py`` run, are
stored with ``taxdump_version: null``. The taxon detail page shows a
"Created before official taxonomy load" banner for these. Running
``load_taxonomy.py`` fills in the missing fields.

Clinical notes
==============

Each taxon entry has a free-text ``clinical_notes`` field that curators
(admin role) can edit from the taxon detail page. Notes are preserved
across taxonomy updates — they live on the taxon document, not on the
imported NCBI record.

Typical content:

- Pathogenicity and clinical relevance
- Treatment / first-line therapy
- Transmission notes
- Links to authoritative resources

Failure modes
=============

- **Download fails** — NCBI's FTP mirror is occasionally unreachable. Retry.
- **Disk space** — ``load_taxonomy.py`` needs ~1 GB temp space for the
  download + extraction. Free up ``/tmp`` if it fails partway.
- **MongoDB unreachable** — same fix as for the API itself; the script reads
  the same ``backend/.env``.

See also
========

- :doc:`ingesting-data` — load case data
- :doc:`taxonomy-browser` — how the reference data appears in the UI
