===========
Ingestion
===========

Data ingestion is the process of loading taxonomic profiling results into meta-vis-app. The ``ingest.py`` script handles this.

Before you begin
================

You need:

1. **taxprofiler output** (required):
   - ``multiqc_data.json`` from MultiQC
   - Software versions file (``software_versions.yml`` or similar)
   - Classifier files (taxpasta TSV and optional Krona HTML)

2. **metaval output** (optional):
   - IGV/ directory with coverage reports

3. **Database running** - MongoDB must be accessible

4. **Ingest credentials** - Username and password for a writer or admin account

Basic ingest
============

The simplest ingest command:

.. code-block:: bash

   cd backend
   conda activate meta-vis-app

   python ingest.py \
     --case-id my-case-001 \
     --order-date 2026-02-20 \
     --multiqc /path/to/multiqc_data.json \
     --pipeline-info /path/to/software_versions.yml \
     --classifier "kraken2 db=k2_pluspf taxpasta=/path/to/kraken2.tsv krona=/path/to/kraken2.html" \
     --sample "sample_id=SRR001 type=sample material=DNA column_kraken2=SRR001_k2_pluspf.kraken2.kraken2.report" \
     --password yourpassword

This creates a case with one sample and one classifier.

Command-line reference
======================

**Required arguments:**

.. code-block:: text

   --case-id ID             Unique case identifier
   --order-date YYYY-MM-DD  Date samples were ordered
   --multiqc PATH           Path to multiqc_data.json
   --pipeline-info PATH     Path to software_versions.yml or nf_core_*.yml
   --classifier ...         At least one classifier (see below)
   --sample ...             At least one sample (see below)
   --password PASS          Password for ingest user

**Optional arguments:**

.. code-block:: text

   --metaval-igv PATH       Path to metaval igv/ output directory
   --quiet                  Suppress verbose output

**Classifier format:**

.. code-block:: text

   --classifier "<name> db=<database> taxpasta=<path> [krona=<path>]"

- **name** - kraken2, centrifuge, or diamond
- **db** - Database identifier (e.g., k2_pluspf)
- **taxpasta** - Path to the merged TSV file
- **krona** - Optional path to Krona HTML (not applicable for diamond)

**Sample format:**

.. code-block:: text

   --sample "<id>=<sample_id> type=<type> material=<material> [subject_id=<id>] column_<classifier>=<column>"

- **sample_id** - Identifier matching taxpasta column names
- **type** - sample, positive_ctrl, or negative_ctrl
- **material** - DNA or RNA
- **subject_id** - For samples (not controls), optional link to subject
- **column_<classifier>** - Exact column name in taxpasta (one per classifier)

Complete example
================

A realistic multi-classifier, multi-sample case:

.. code-block:: bash

   python ingest.py \
     --case-id outbreak-2026-02 \
     --order-date 2026-02-20 \
     --multiqc /data/outbreak/multiqc_data.json \
     --pipeline-info /data/outbreak/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml \
     \
     --classifier "kraken2 db=k2_pluspf taxpasta=/data/outbreak/taxpasta/kraken2_k2_pluspf.tsv krona=/data/outbreak/krona/kraken2_k2_pluspf.html" \
     --classifier "centrifuge db=p_compressed+h+v taxpasta=/data/outbreak/taxpasta/centrifuge_p_compressed+h+v.tsv krona=/data/outbreak/krona/centrifuge_p_compressed+h+v.html" \
     --classifier "diamond db=diamond taxpasta=/data/outbreak/taxpasta/diamond_diamond.tsv" \
     \
     --sample "sample_id=patient-001 type=sample material=DNA subject_id=PT-001 column_kraken2=patient-001_k2_pluspf.kraken2.kraken2.report column_centrifuge=patient-001_p_compressed+h+v.centrifuge column_diamond=patient-001_diamond.diamond" \
     --sample "sample_id=patient-002 type=sample material=DNA subject_id=PT-002 column_kraken2=patient-002_k2_pluspf.kraken2.kraken2.report column_centrifuge=patient-002_p_compressed+h+v.centrifuge column_diamond=patient-002_diamond.diamond" \
     --sample "sample_id=control-pos type=positive_ctrl material=DNA column_kraken2=control-pos_k2_pluspf.kraken2.kraken2.report column_centrifuge=control-pos_p_compressed+h+v.centrifuge column_diamond=control-pos_diamond.diamond" \
     --sample "sample_id=control-neg type=negative_ctrl material=DNA column_kraken2=control-neg_k2_pluspf.kraken2.kraken2.report column_centrifuge=control-neg_p_compressed+h+v.centrifuge column_diamond=control-neg_diamond.diamond" \
     \
     --metaval-igv /data/outbreak/metaval/igv \
     \
     --password mypassword

Understanding taxpasta column names
===================================

taxprofiler appends suffixes to column names based on classifier and database:

**Kraken2:**

.. code-block:: text

   <sample_id>_<db>.kraken2.kraken2.report

   Example: patient-001_k2_pluspf.kraken2.kraken2.report

**Centrifuge:**

.. code-block:: text

   <sample_id>_<db>.centrifuge

   Example: patient-001_p_compressed+h+v.centrifuge

**DIAMOND:**

.. code-block:: text

   <sample_id>_<db>.diamond

   Example: patient-001_diamond.diamond

Check the taxpasta TSV header to confirm exact names.

Including metaval results
==========================

If metaval has been run on the same case:

.. code-block:: bash

   python ingest.py \
     ... \
     --metaval-igv /path/to/metaval/igv \
     ...

The metaval output directory must be a subdirectory of the metaval root:

.. code-block:: text

   metaval/
   ├── igv/          ← Pass this path
   ├── blast/
   └── extracted_reads/

IGV HTML files are extracted and stored in the blob store during ingest.

Re-ingesting a case
====================

Each case_id must be unique. To re-ingest a case:

1. Delete the existing case via the UI (Admin panel) or API
2. Run the ingest command again

Deleting via the UI:
- Go to Sidebar → Admin (admins only)
- Find the case
- Click Delete
- Blobs are automatically removed from storage

Bulk ingestion
==============

To ingest multiple cases, create a shell script:

.. code-block:: bash

   #!/bin/bash

   cases=(
     "case-001:2026-02-01"
     "case-002:2026-02-05"
     "case-003:2026-02-10"
   )

   for case_info in "${cases[@]}"; do
       IFS=':' read -r case_id order_date <<< "$case_info"

       python ingest.py \
         --case-id "$case_id" \
         --order-date "$order_date" \
         --multiqc "/data/$case_id/multiqc_data.json" \
         --pipeline-info "/data/$case_id/pipeline_info/software_versions.yml" \
         ... other arguments ...

       if [ $? -eq 0 ]; then
           echo "✓ Ingested $case_id"
       else
           echo "✗ Failed to ingest $case_id"
       fi
   done

Troubleshooting ingestion
=========================

**"Case already exists"**
  Delete the case first via the UI or API, then re-ingest.

**"Column not found in taxpasta"**
  Check the taxpasta TSV header. Column names are case-sensitive.

**"File not found"**
  All paths must be absolute. Check that files exist and paths are correct.

**"Connection refused"**
  MongoDB isn't running. Start with ``docker compose up -d`` in the backend directory.

**"Authentication failed"**
  Check username/password. Must be a valid writer or admin account.

**"Krona HTML upload failed"**
  Check that object storage is configured correctly. For MongoDB backend, ensure space is available.

Performance notes
=================

- Ingestion is I/O bound (reading files, uploading blobs)
- Krona HTML files (1–2 MB) are uploaded concurrently
- Large cases (many samples/classifiers) take longer
- Progress is logged to stdout
- Can be run in background: ``nohup python ingest.py ... > ingest.log 2>&1 &``

For very large pipelines (100+ samples):
- Consider splitting into multiple cases
- Run ingestion during off-peak hours
- Monitor disk I/O and network usage

Next steps
==========

- :doc:`taxonomy-reference` - Load NCBI taxonomy data
- :doc:`user-management` - Manage ingest user accounts
