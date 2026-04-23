===
FAQ
===

Frequently asked questions and answers.

General questions
=================

**Q: What is meta-vis-app?**

A: meta-vis-app is a web-based clinical interpretation tool for visualizing and reviewing results from nf-core/taxprofiler metagenomics pipeline runs. It displays taxonomic classification results, quality metrics, and optional metaval verification data.

**Q: Who should use meta-vis-app?**

A: Clinicians, microbiologists, and bioinformaticians reviewing metagenomic data. Requires basic understanding of:
- Metagenomics and taxonomy
- Taxonomic classification tools (Kraken2, Centrifuge, DIAMOND)
- Quality control metrics

**Q: Can meta-vis-app call organisms?**

A: No. meta-vis-app visualizes and reviews results from existing taxonomic classifiers. It doesn't run classification itself. For that, use nf-core/taxprofiler.

**Q: Is meta-vis-app secure?**

A: Yes. It includes:
- User authentication (username/password with JWT tokens)
- Role-based access control
- Password hashing (bcrypt)
- HTTPS support (configure in production)

For sensitive data, host behind firewall and use institutional authentication (LDAP/SSO integration can be added).

Installation and deployment
============================

**Q: Can I use meta-vis-app without Docker?**

A: Yes. Docker is used for MongoDB and optional MinIO. You can:
- Use a managed MongoDB service (Atlas, AWS, Azure)
- Use a managed S3 service (AWS S3, Azure Storage)
- Then run backend and frontend without Docker

**Q: What are the minimum system requirements?**

A:
- **Development:** 4 GB RAM, 2 CPU cores, 50 GB disk
- **Production (small):** 8 GB RAM, 4 CPU cores, 500 GB disk
- **Production (large):** 16+ GB RAM, 8+ CPU cores, 2+ TB disk

**Q: Can I run this on Windows?**

A: Yes, with WSL2 (Windows Subsystem for Linux 2):
- Install WSL2
- Install Docker Desktop for Windows
- Follow standard installation in WSL2 terminal

Or use managed services for MongoDB and S3, run app natively.

**Q: How do I update meta-vis-app?**

A:
1. Pull latest code: ``git pull origin main``
2. Stop services: ``docker compose down``
3. Update dependencies:
   - Backend: ``pip install -e backend/``
   - Frontend: ``npm install``
4. Migrate database if needed (follow release notes)
5. Start services: ``docker compose up -d``
6. Verify: Check frontend loads, try logging in

Data ingestion
==============

**Q: How long does ingestion take?**

A: Depends on case size:
- Small (5 samples, 1 classifier): 1–2 minutes
- Medium (20 samples, 3 classifiers): 5–10 minutes
- Large (100+ samples): 15–30 minutes

Bottlenecks:
- File reading
- Krona/IGV upload to object storage
- MongoDB inserts

**Q: Can I ingest data while the app is running?**

A: Yes. Ingestion is separate. The app continues running. Just don't query the same case being ingested (wait a few seconds after ingest completes).

**Q: What if ingest fails halfway?**

A: Delete the partially-ingested case (Admin panel) and retry. No partial data remains.

**Q: Can I re-ingest a case?**

A: Yes:
1. Delete the existing case (Admin panel)
2. Run ingest again with same case_id

**Q: How do I ingest data with custom samples I sequenced?**

A: Run taxprofiler with your samples first, then use ingest.py on the output.

See :doc:`../administration/ingestion` for details.

Usage and interpretation
========================

**Q: What's the difference between the classifiers?**

A: Each uses a different reference database and algorithm:

- **Kraken2** - k-mer based, fast, good for genus/species
- **Centrifuge** - k-mer + BWA, comprehensive, good for rare organisms
- **DIAMOND** - BLAST-like protein alignment, good for distant homology

Agreement across classifiers = high confidence. Disagreement = verify with metaval.

**Q: Which classifier should I trust?**

A: None singularly. Check:
1. Do all classifiers agree?
2. Is the organism abundant?
3. Does metaval confirm it?
4. Is it clinically expected?

**Q: What does "unclassified %" mean?**

A: Percentage of reads that couldn't be assigned to any organism. Common causes:
- Low-complexity reads
- Non-pathogenic organisms not in database
- Contamination
- Degraded RNA/DNA

**Q: What does "host removal %" mean?**

A: Percentage of reads that matched the host genome (usually human DNA). These are removed before classification. High values (> 50%) suggest:
- Low sample quality
- High host contamination
- Need to check sample preparation

**Q: What's a good read count?**

A: Depends on your application:
- Viral detection: > 500K reads needed
- Bacterial detection: > 100K reads adequate
- Quality assessment: ideally > 1M reads

Too few reads = low sensitivity. Too many = wasted sequencing.

**Q: How do I identify contamination?**

A: Check:
1. **Negative controls** - What's in them?
2. **Positive controls** - Are expected organisms present?
3. **Abundance** - Contaminants usually rare (< 0.1%)
4. **Patterns** - Do multiple cases have same organism unexpectedly?

Use Alerts page to spot patterns.

Outbreak detection
==================

**Q: How sensitive is outbreak detection?**

A: Very sensitive (will flag 2+ cases with any viral taxon > 1 read). This catches real signals but also technical artifacts. Always investigate alerts.

**Q: Can I exclude organisms from outbreak detection?**

A: Yes. Admins and writers can add organisms to the ignorelist on the Alerts page. Admins can remove them.

**Q: Why don't I see any alerts?**

A: Possible reasons:
1. No viral taxa in 2+ cases within the time window
2. Cases don't have order dates (required)
3. Organisms are on the ignorelist
4. No cases exist yet

Try widening the time window (30 days) to see if matches appear.

**Q: Can I change the alert time window?**

A: Yes, on the Alerts page:
- 7 days - Recent alerts (few days of testing)
- 14 days - Week-level patterns
- 30 days - Month-level patterns

**Q: Is outbreak detection a real epidemiologic tool?**

A: No. It's an early signal system. Always verify with:
1. Manual case review
2. Metaval confirmation
3. Patient interview (infection control)
4. Epidemiologic investigation

Metaval integration
===================

**Q: What does "verified" mean?**

A: The organism has IGV coverage visualization and BLAST sequence confirmation. This doesn't mean infection/disease—just that the organism's genetic material was found.

**Q: If metaval shows high coverage, does it mean the organism is there?**

A: Probably yes, but not certainly. High coverage indicates:
- Many reads mapped to reference
- Reference matched well
- Organism was in the sample

But:
- Could be contamination
- Could be part of normal flora
- Requires clinical context

**Q: Why doesn't my case have metaval results?**

A: metaval output wasn't provided during ingest. Options:
1. Run metaval separately on the raw reads
2. Re-ingest case with ``--metaval-igv`` flag
3. Or run metaval and re-ingest

**Q: Can I view BLAST results?**

A: Yes. On Metaval Details page. Shows:
- % sequence identity
- Alignment length
- E-value (statistical significance)

> 98% identity + full alignment = high confidence match

**Q: IGV plot is blank. Why?**

A: IGV HTML upload might have failed. Try:
1. Re-ingest case (delete and re-ingest)
2. Check object storage is working
3. Check logs for upload errors

User management
===============

**Q: How do I add users?**

A: Admins only. Go to Admin panel (sidebar) and click "Create User".

Need admin to create users? Can't perform this alone.

**Q: How do I reset a user's password?**

A: Admins can't directly reset. Instead:
1. Delete the user account
2. Create new account with same username and temporary password
3. User changes password on first login

**Q: Can I set up single sign-on (SSO)?**

A: Not built-in, but can be added. Contact development team to discuss:
- LDAP integration
- OAuth 2.0
- SAML

**Q: What's the difference between writer and admin?**

A: Writers can:
- Review cases and add notes
- Mark cases as reviewed
- Add to ignorelist

Admins can also:
- Manage users
- Delete cases
- Remove from ignorelist

**Q: Do users have per-case access control?**

A: No. All users see all cases. If you need per-case permissions, contact development team.

Technical questions
===================

**Q: What database is used?**

A: MongoDB. Stores cases, samples, user accounts, taxonomy reference, and optionally Krona/IGV files.

**Q: Can I export my data?**

A: Yes. MongoDB tools:

.. code-block:: bash

   mongodump --uri="mongodb://user:pass@host/meta-vis" --out=/backup/

Or export individual cases via REST API (contact dev team).

**Q: Can I backup my data?**

A: Yes:

.. code-block:: bash

   # MongoDB
   mongodump --uri="..." --out=/backups/$(date +%Y%m%d)

   # S3 (if using)
   aws s3 sync s3://bucket-name /backups/$(date +%Y%m%d)

**Q: Where is my data stored?**

A: By default:
- MongoDB: Docker volume (on host filesystem)
- Krona/IGV: MongoDB blob collection

Can configure:
- MongoDB: Managed service (Atlas, AWS, etc.)
- S3: MinIO or AWS S3

**Q: Can I migrate between backends?**

A: Switching from MongoDB blobs to S3:
1. Cases ingested with MongoDB have blobs in database
2. Switch to S3 backend (set env vars)
3. New cases go to S3
4. Old cases still in MongoDB (blobs not found)

Solution: Delete old cases and re-ingest.

Troubleshooting
===============

**Q: "Connection refused" when starting backend**

A: MongoDB not running:

.. code-block:: bash

   docker compose up -d mongodb

**Q: Taxonomy table is very slow**

A: Sample has many organisms (> 10,000):
1. Use search/filters to narrow results
2. Or switch to a different classifier
3. Or contact admin to optimize database

**Q: "Case not found" after ingesting**

A: Wait a few seconds for database to commit. Or:
1. Refresh browser
2. Check ingest completed without errors
3. Check case_id spelling

**Q: Can't mark case as reviewed**

A: Only writers and admins can do this. Check:
1. Your role (click profile → "My Role")
2. Ask admin if need higher role

**Q: Krona plot won't load**

A: Object storage issue:
1. Check MinIO is running: ``docker ps | grep minio``
2. Check S3 credentials if using AWS
3. Try re-ingesting case

**Q: User can't log in**

A: Check:
1. Username spelled correctly (case-sensitive)
2. Password correct
3. Account exists (ask admin)
4. Retry after a minute (no lockout, but might be rate-limited)

Next steps
==========

Still have questions?

- Check :doc:`../administration/troubleshooting` for more issues
- Review relevant guide section (user guide, admin, developer)
- Contact the development team
