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

meta-vis-app is a **clinical interpretation tool for metagenomic quality control and pathogen detection**. It transforms complex taxonomic profiling data into actionable intelligence for clinicians and lab teams.

Core Features
-------------

**Organize & Review Cases**

- Ingest taxonomic profiling results from nf-core/taxprofiler with a single command
- Organize results into cases (one per run) with multiple samples
- Review sample-level quality metrics (read counts, host removal, contamination)
- Mark cases as reviewed and add clinical notes

**Interpret Taxonomy Results**

- View organism detection across three classifiers (Kraken2, Centrifuge, DIAMOND)
- Search and filter organisms by name, kingdom, and abundance
- Interactive Krona visualizations for intuitive taxonomy exploration
- Cross-classifier comparison to validate detections

**Verify Findings with Confidence**

- When metaval results available: See IGV coverage plots and BLASTN alignments for detected organisms
- Confirms organisms are truly present in reads (not artifacts)
- Links sequence evidence directly to organism calls
- Reduces false positives and increases confidence in clinical reporting

**Monitor for Outbreaks & Contamination**

- **Outbreak alerts:** Automatically detects when same viral pathogen appears in 2+ cases
- **Quality control:** Track negative test control (NTC) contamination over time
- **Flexible monitoring:** Configurable time windows (7/14/30 days) and abundance thresholds
- **Team communication:** Orange alerts flag problematic patterns for immediate investigation

**Manage Quality Standards**

- Build curated lists of known contaminants to track
- Exclude environmental organisms from alerting
- Assign alert thresholds per organism
- Maintain audit trail of who added/removed list items

Why It Matters
~~~~~~~~~~~~~~

- ✓ **Clinical confidence** — Verification data (IGV + BLASTN) confirms organisms are real
- ✓ **Faster interpretation** — Organized interface reduces review time
- ✓ **Quality assurance** — Built-in contamination monitoring
- ✓ **Early warning** — Outbreak detection catches patterns before they spread
- ✓ **Compliance-ready** — Full audit trail and user-level access control

Who Uses It
~~~~~~~~~~~

- **Clinicians** - Review metagenomic results, verify organisms, make treatment decisions
- **Lab managers** - Monitor quality trends, manage contamination, ensure standards
- **Bioinformaticians** - Organize pipelines, verify results, support clinical teams

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
- :doc:`user-guide/bvbrc-integration`
- :doc:`user-guide/outbreak-detection`
- :doc:`user-guide/ntc-monitoring`

For administrators
==================

- :doc:`deployment/docker-compose`
- :doc:`deployment/environment`
- :doc:`administration/ingestion`
- :doc:`administration/taxonomy-reference`
- :doc:`administration/user-management`
- :doc:`administration/audit-log`
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
   :caption: Administration

   administration/ingestion
   administration/taxonomy-reference
   administration/user-management
   administration/audit-log
   administration/troubleshooting

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: User Guide

   user-guide/cases-and-samples
   user-guide/taxonomy-browser
   user-guide/metaval-integration
   user-guide/bvbrc-integration
   user-guide/outbreak-detection
   user-guide/ntc-monitoring
   user-guide/user-roles

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Reference

   reference/ingest-format
   reference/faq
   reference/changelog

.. toctree::
   :hidden:
   :maxdepth: 2
   :caption: Developer

   developer/architecture
   developer/data-model
   developer/contributing
   developer/performance