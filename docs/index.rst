.. Meta-vis documentation master file

============================
Meta-vis
============================

A web application for reviewing the output of clinical metagenomics
pipelines. It ingests results from
`nf-core/taxprofiler <https://github.com/nf-core/taxprofiler>`_ (shotgun
metagenomics) and Trana (16S amplicon, Emu), and optionally enriches them
with `metaval <https://github.com/genomic-medicine-sweden/metaval>`_
read-level validation.

.. image:: ../assets/logo.svg
   :alt: Meta-vis logo
   :width: 500px
   :align: center

What it is for
==============

A clinical interpretation surface on top of metagenomic profiling.
Pipeline outputs land here as **cases** (one per pipeline run); each case
contains one or more **samples**; each sample carries the taxonomic
profile from one or more **classifiers** (Kraken2, Centrifuge, DIAMOND,
or Emu). Reviewers explore detections, add notes, mark cases reviewed,
and act on cross-case signals.

What the app does
=================

- **Review** cases and samples, with per-classifier QC and interactive
  Krona plots.
- **Investigate** individual detections through a searchable taxonomy
  table, metaval IGV / BLASTN evidence, and BV-BRC reference
  enrichments.
- **Monitor** viral outbreak signals across cases and contamination
  trends across negative controls, with configurable time windows and
  ignorelists.
- **Audit** every clinically significant action — written to MongoDB
  and to structured stdout logs for independent retention.

Authentication is OIDC against an external Keycloak realm; roles
(``reader`` / ``writer`` / ``admin``) drive both the API and the UI.

Who it is for
=============

- **Clinical microbiologists** reviewing metagenomic results, verifying
  organisms, and writing case notes.
- **Lab managers** monitoring NTC quality trends and contamination.
- **Bioinformaticians** running ingest, curating taxonomy notes, and
  supporting clinical teams.

Where to start
==============

Run the app locally
   :doc:`deployment/local-dev` — Docker-first dev stack via ``make up``.

Use the app
   :doc:`user-guide/reviewing-cases` — the day-to-day clinician
   workflow.

Deploy or run it in production
   :doc:`deployment/production` — the single-host compose deployment
   shape.

Read the architecture
   :doc:`developer/architecture` — how the pieces fit together.

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Use the app

   user-guide/reviewing-cases
   user-guide/investigating-detections
   user-guide/monitoring
   user-guide/loading-data
   user-guide/administration

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Deployment

   deployment/local-dev
   deployment/environment
   deployment/object-storage
   deployment/production

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Developer

   developer/architecture
