=========
Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on `Keep a Changelog <https://keepachangelog.com/>`_, and this project adheres to `Semantic Versioning <https://semver.org/>`_.

[Unreleased]
============

Added
-----
- User preferences page (``/preferences``) accessible by clicking the username in the
  sidebar. Currently exposes default taxonomy kingdom filter selection.
- ``GET /api/v1/users/me/preferences`` and ``PATCH /api/v1/users/me/preferences``
  endpoints to read and persist per-user UI preferences in MongoDB.
- Taxonomy table in sample detail now initialises the kingdom filter from the user's
  saved preference instead of always defaulting to *Viruses*.

Changed
-------
- Username in the sidebar bottom-left is now a link to the Preferences page.

Fixed
-----
- Bug fixes

[0.1.0] - 2026-02-20
====================

Initial public release.

Added
-----
- Case and sample organization with QC metrics
- Multi-classifier taxonomy visualization (Kraken2, Centrifuge, DIAMOND)
- Interactive Krona plots per classifier
- Searchable, filterable taxonomy tables
- metaval integration with IGV coverage and BLAST results
- Outbreak detection with configurable time windows
- User authentication with role-based access (reader, writer, admin)
- Case review tracking and notes
- Taxonomy reference data from NCBI
- MongoDB and S3-compatible object storage backends
- Docker Compose for local development and testing
- Comprehensive REST API with interactive documentation
- Full documentation with getting started, user guides, and developer guides

Features
--------

**Backend (FastAPI + Motor + MongoDB)**
- Async API for efficient concurrent requests
- User authentication with JWT tokens
- Multi-user support with role-based permissions
- Outbreak detection with MongoDB aggregation pipelines
- Support for MongoDB or S3-compatible blob storage
- Bulk ingest via ``ingest.py`` script
- Support for taxprofiler and metaval output formats

**Frontend (React + Vite + Tailwind CSS)**
- Case and sample browsing with sorting/filtering
- Per-classifier QC metrics tables
- Interactive Krona visualizations
- Full-text search in taxonomy tables
- Kingdom and rank filtering
- Metaval results viewing (IGV coverage, BLAST results)
- Outbreak alerts with configurable time windows
- Case review status tracking
- User authentication and role display
- Admin panel for user management

**Supported Data**
- nf-core/taxprofiler v1.1+
- Taxonomic classifiers:
  - Kraken2 with taxpasta output
  - Centrifuge with taxpasta output
  - DIAMOND with taxpasta output
- metaval post-processing results (optional)
- NCBI taxonomy reference data
- MultiQC QC metrics
- Sample types: clinical samples, positive controls, negative controls

Known Limitations
-----------------

- No per-case access control (all users see all cases)
- No formal audit logging
- Taxonomy updates require reloading data (no incremental updates)
- Outbreak detection is signal-only (not epidemiologically validated)
- No built-in SSO/LDAP (can be added via custom middleware)
- No de-duplication of organisms across name variations

Future Roadmap
==============

Potential features for future releases:

**User Experience**
- Advanced filtering (multiple criteria, save filters)
- Export functionality (PDF reports, data tables)
- Batch operations (mark multiple cases reviewed)
- Customizable dashboard
- Comparison tools (case-to-case, sample-to-sample)

**Data**
- Resistance gene detection integration
- Virulence factor databases
- Clinical significance scoring
- Phylogenetic analysis and tree visualization
- Strain-level identification

**Administration**
- LDAP/Active Directory integration (SSO)
- Audit logging of all actions
- Database migration tools
- Bulk import/export
- API rate limiting and usage tracking

**Performance**
- Distributed caching (Redis)
- Database sharding for large deployments
- Full-text search optimization
- Asynchronous job queue for heavy operations

**Infrastructure**
- Kubernetes deployment templates
- Horizontal auto-scaling configuration
- Multi-region deployment support
- Database replication and failover
- Backup/disaster recovery automation

Contributing
============

To contribute to meta-vis-app, see :doc:`../developer/contributing`.

Report bugs, request features, and discuss enhancements on GitHub (once public).

Support and Feedback
====================

- **Bugs and issues** - Create GitHub issue with steps to reproduce
- **Feature requests** - Discuss in GitHub issues or with the development team
- **Questions** - See documentation or ask the team
- **Feedback** - We value your input on usability and functionality

Version History
===============

.. list-table::
   :header-rows: 1
   :widths: 20, 20, 60

   * - Version
     - Release Date
     - Notes
   * - 0.1.0
     - 2026-02-20
     - Initial public release

Thanks
======

meta-vis-app is developed by the bioinformatics team at Genomic Medicine Sweden.

Special thanks to:
- nf-core team for taxprofiler pipeline
- NCBI for taxonomy data
- All contributors and testers

License
=======

See LICENSE file in repository for full license terms.

Changelog format notes
======================

**For future releases, use the following structure:**

.. code-block:: text

   [VERSION] - YYYY-MM-DD
   =======================

   Added
   -----
   - New feature 1
   - New feature 2

   Changed
   -------
   - Change to existing feature

   Fixed
   -----
   - Bug fix 1
   - Bug fix 2

   Deprecated
   ----------
   - Feature that will be removed soon

   Removed
   -------
   - Feature that was removed

   Security
   --------
   - Security vulnerability fixes

Keep all versions in one file for full history.
