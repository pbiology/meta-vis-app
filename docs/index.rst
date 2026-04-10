.. meta-vis-app documentation master file

========================================
meta-vis-app Documentation
========================================

A web application for visualising and reviewing the output of `nf-core/taxprofiler <https://github.com/nf-core/taxprofiler>`_ metagenomics runs, with optional integration of `metaval <https://github.com/genomic-medicine-sweden/metaval>`_ post-processing results.

.. image:: ../assets/logo.svg
   :alt: meta-vis logo
   :width: 600px
   :align: left

What the app does
=================

meta-vis-app organises taxprofiler output into **cases** — one per pipeline run — each containing one or more **samples**. For each case the app provides:

- A case overview with per-sample general QC metrics (read counts, Q30, host removal)
- Per-classifier QC tables (unclassified %, host %, species count, genera count, top taxa) with tabs to switch between classifiers
- Krona interactive taxonomy plots, tabbed per classifier
- A taxonomy table per classifier with search, kingdom filter, and rank display
- A provenance section showing pipeline and tool versions (taxprofiler and metaval)
- Case-level review status (mark as reviewed / unmark)
- Case-level notes, allowing reviewers to record observations while viewing the data

When metaval output is also ingested, taxa in the taxonomy table that have been verified by metaval gain a clickable pill linking to a details page showing IGV coverage reports and BLASTN results.

The app also includes an **outbreak detection** feature that monitors viral taxa appearing across multiple cases within a configurable time window.

The app also includes **NTC Trends** and **Quality Control** monitoring for negative test controls to track contamination patterns and ensure sample quality.

Quick start
===========

1. **New users**: Start with :doc:`getting-started/overview`
2. **Installation**: Follow :doc:`getting-started/installation`
3. **First run**: Check out :doc:`getting-started/quick-start`

For clinicians
==============

- :doc:`user-guide/cases-and-samples`
- :doc:`user-guide/taxonomy-browser`
- :doc:`user-guide/metaval-integration`
- :doc:`user-guide/outbreak-detection`
- :doc:`user-guide/ntc-monitoring`

For administrators
==================

- :doc:`deployment/docker-compose`
- :doc:`deployment/environment`
- :doc:`administration/ingestion`
- :doc:`administration/taxonomy-reference`
- :doc:`administration/user-management`
- :doc:`administration/troubleshooting`

For developers
==============

- :doc:`developer/architecture`
- :doc:`developer/data-model`
- :doc:`developer/contributing`
- :doc:`developer/performance`

Reference
=========

- :doc:`reference/ingest-format`
- :doc:`reference/faq`
- :doc:`reference/changelog`

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Getting Started

   getting-started/overview
   getting-started/installation
   getting-started/quick-start

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Deployment

   deployment/docker-compose
   deployment/environment
   deployment/object-storage
   deployment/production

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: User Guide

   user-guide/cases-and-samples
   user-guide/taxonomy-browser
   user-guide/metaval-integration
   user-guide/outbreak-detection
   user-guide/ntc-monitoring
   user-guide/user-roles

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Administration

   administration/ingestion
   administration/taxonomy-reference
   administration/user-management
   administration/troubleshooting

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Developer

   developer/architecture
   developer/data-model
   developer/contributing
   developer/performance

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Reference

   reference/ingest-format
   reference/faq
   reference/changelog