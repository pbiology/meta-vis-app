====================
Taxonomy Reference
====================

The app uses reference taxonomy data for detailed organism information. This guide covers loading and maintaining that data.

What is taxonomy data?
======================

The taxonomy data includes:

- **Full lineage** - Complete taxonomic hierarchy (kingdom → species)
- **Organism names** - Scientific and common names
- **NCBI taxon IDs** - Standard identifiers
- **Rank information** - Kingdom, phylum, class, order, family, genus, species, etc.
- **Relationships** - Parent/child relationships in the taxonomy tree
- **Clinical notes** - Curator-added information about clinically relevant organisms

This data is sourced from NCBI and updated monthly.

Loading taxonomy data
=====================

To load or update the taxonomy database:

.. code-block:: bash

   cd backend
   conda activate meta-vis-app
   python load_taxonomy.py

**What happens:**
1. Downloads new_taxdump.tar.gz (~110 MB) from NCBI
2. Extracts and parses taxonomy files
3. Bulk-upserts ~2.4 million records into the database
4. Takes 10–20 minutes depending on system performance

**Safe to re-run** - Existing data is updated, clinical notes are preserved.

Scheduling updates
==================

It's recommended to update taxonomy data monthly (NCBI publishes on the 1st of each month).

**Using cron (Linux/Mac):**

.. code-block:: bash

   0 3 2 * * cd /path/to/meta-vis-app/backend && conda run -n meta-vis-app python load_taxonomy.py

This runs at 3 AM on the 2nd of each month.

**Using Windows Task Scheduler:**

1. Create a batch file (e.g., ``load_taxonomy.bat``):

   .. code-block:: batch

      cd C:\path\to\meta-vis-app\backend
      call conda activate meta-vis-app
      python load_taxonomy.py

2. Create a scheduled task to run monthly

**Using Docker:**

.. code-block:: bash

   docker run --rm \
     --env-file /path/to/.env \
     meta-vis-app:latest \
     python load_taxonomy.py

Stale data
==========

Taxa records created before the first ``load_taxonomy.py`` run have ``taxdump_version: null``.

**Why this matters:**
- These entries are incomplete
- NCBI links might not work
- Clinical notes field is available for manual curation

**How to identify stale records:**
- Check the taxon detail page
- Banner: "Created before official taxonomy load"
- See the NCBI taxon ID (if available)

**Recommended action:**
- Run ``load_taxonomy.py`` to update all records
- Or link to NCBI manually to find the organism

Clinical notes
==============

Curators can add clinical notes to organisms. These notes are preserved during updates.

**Adding notes (curator role needed):**

1. Go to a taxon detail page
2. Edit the "Clinical notes" field
3. Add relevant information:
   - Pathogenicity
   - Treatment guidelines
   - Transmission routes
   - Diagnostic considerations
   - Links to resources

**Example notes:**

.. code-block:: text

   Influenza A virus:
   - Cause of seasonal/pandemic influenza
   - Highly contagious respiratory pathogen
   - Treatment: neuraminidase inhibitors
   - See CDC guidance for outbreak response
   - NCBI: https://www.ncbi.nlm.nih.gov/taxonomy/11320

Managing taxonomy performance
=============================

For very large databases:

**Query performance:**
- Taxonomy queries are indexed on taxon ID and name
- Searches are fast (<100ms typically)
- Lineage traversal uses cached paths

**Disk usage:**
- Taxonomy collection: ~500 MB for full 2.4M records
- Indexes: ~200 MB
- Total: ~700 MB

**Optimization:**
- Let MongoDB handle indexing (automatic)
- No manual tuning usually needed
- Monitor with ``db.stats()`` if concerned

When taxonomy loads fail
========================

**"Download failed"**
  Check network connectivity to NCBI FTP site. The FTP server occasionally has downtime. Retry in a few minutes.

**"Parse error"**
  NCBI format might have changed. Check NCBI FTP for new file formats. Might need code updates.

**"Disk space"**
  Loading requires temporary disk space. Ensure ``/tmp`` or equivalent has >1 GB free.

**"Database connection failed"**
  MongoDB isn't running. Start with ``docker compose up -d``.

Troubleshooting
===============

**Old taxon data even after loading**

Check that:
1. ``load_taxonomy.py`` ran successfully (check for error messages)
2. You're querying the right database (check ``.env`` for database name)
3. Give MongoDB a minute to commit the data

**Missing clinical notes after update**

Clinical notes are preserved during updates. If missing:
1. Check if the organism was merged/renamed in NCBI taxonomy
2. Re-add the notes manually (they're now on the new taxon entry)

**Very slow taxonomy queries**

If queries are slow (>1 second):
1. Check MongoDB performance (``db.stats()``)
2. Look for missing indexes
3. Consider archiving very old cases to a separate database

**Inconsistent taxon names between classifiers**

Different versions of NCBI taxonomy might be in use. Solution:
1. Ensure all classifiers use current databases
2. Update taxonomy regularly with ``load_taxonomy.py``
3. Consider normalizing names if mixing old/new taxonomy versions

Best practices
==============

1. **Keep taxonomy current** - Update monthly with NCBI releases
2. **Add clinical notes** - Document important organisms
3. **Monitor storage** - Check disk usage monthly
4. **Test procedures** - Verify restore procedures work
5. **Document changes** - Note any taxonomy schema changes
6. **Archive data** - Archive old cases periodically to manage database size

Next steps
==========

- :doc:`ingestion` - Load case data
- :doc:`user-management` - Manage users who can curate notes
- :doc:`troubleshooting` - Debug common issues
