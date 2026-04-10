=======================
What is meta-vis-app?
=======================

meta-vis-app is a web-based clinical interpretation tool for metagenomics data. It enables clinicians and researchers to visualize, review, and annotate the results from `nf-core/taxprofiler <https://github.com/nf-core/taxprofiler>`_ pipeline runs.

Core concept: Cases and Samples
================================

The app organizes data hierarchically:

**Case**
  A single taxprofiler pipeline run. Contains metadata about when the samples were ordered, notes from reviewers, and review status.

**Sample**
  An individual sequencing sample within a case. Each sample has taxonomic profiles from one or more classifiers (Kraken2, Centrifuge, DIAMOND).

**Classifier**
  A taxonomic classification tool (Kraken2, Centrifuge, or DIAMOND). Each sample can have results from multiple classifiers, which can be compared and cross-referenced.

Key features
============

**Interactive taxonomy visualization**
  - Krona plots for interactive exploration of taxonomic hierarchies
  - Searchable taxonomy tables with kingdom filtering
  - Per-rank taxonomy summaries

**Quality metrics**
  - Read count and quality statistics per sample
  - Unclassified and host read percentages
  - Species and genera counts per classifier

**Metaval integration** (optional)
  When metaval results are available, verified taxa show:
  - IGV coverage visualizations
  - BLASTN sequence alignment results
  - Confidence indicators

**Outbreak detection**
  Automatic monitoring of viral taxa appearing across multiple cases within a configurable time window. Helpful for early identification of potential outbreak situations.

**Collaboration features**
  - Role-based access control (reader, writer, admin)
  - Case review status tracking
  - Clinician-editable notes on cases

Technology stack
================

.. list-table::
   :header-rows: 1
   :widths: 20, 40

   * - Layer
     - Technology
   * - Backend
     - FastAPI + Motor (async MongoDB)
   * - Database
     - MongoDB 7.0 (Docker)
   * - Object storage
     - MinIO (Docker) — optional
   * - Frontend
     - React 18 + Vite + Tailwind CSS
   * - Runtime
     - Python 3.11+ (conda), Node.js ≥18

Why this stack?
  - **FastAPI**: Modern, performant, auto-generated API docs
  - **Motor**: Async MongoDB driver for efficient I/O
  - **React + Vite**: Fast frontend builds, excellent developer experience
  - **MongoDB**: Flexible schema suits diverse bioinformatics data structures
  - **Docker**: Reproducible, containerized services

Next steps
==========

- :doc:`installation` - Set up the app on your system
- :doc:`quick-start` - Get the app running with sample data
