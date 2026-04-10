==============
Ingest Format
==============

Detailed reference for the ``ingest.py`` command-line tool.

Command syntax
==============

.. code-block:: bash

   python ingest.py \
     --case-id ID \
     --order-date YYYY-MM-DD \
     --multiqc PATH \
     --pipeline-info PATH \
     --classifier NAME [--classifier ...] \
     --sample ID [--sample ...] \
     --password PASS \
     [--metaval-igv PATH] \
     [--quiet]

Required arguments
==================

**--case-id ID**

Unique identifier for this case. Will be displayed in the UI.

- Must be unique (can't reuse)
- Alphanumeric, hyphens allowed
- Examples: ``case-001``, ``outbreak-2026-02``, ``patient-XYZ``
- Cannot contain spaces or special characters (except hyphens)

**--order-date YYYY-MM-DD**

Date the samples were ordered/collected.

- Format: ISO 8601 (``2026-02-20``)
- Used for outbreak detection time windows
- Used for sorting and filtering in UI

**--multiqc PATH**

Absolute path to MultiQC output file.

- Usually: ``multiqc_data.json``
- Located in: MultiQC output directory
- Must be readable file

**--pipeline-info PATH**

Absolute path to software versions file.

- Usually: ``software_versions.yml`` or ``nf_core_taxprofiler_software_mqc_versions.yml``
- Located in: ``pipeline_info/`` directory of taxprofiler output
- Contains tool versions and pipeline metadata

**--classifier NAME [--classifier ...]**

At least one classifier. Multiple allowed. Format:

.. code-block:: text

   --classifier "<name> db=<database> taxpasta=<path> [krona=<path>]"

Fields:

- **name** (required) - ``kraken2``, ``centrifuge``, or ``diamond``
- **db** (required) - Database identifier (e.g., ``k2_pluspf``)
- **taxpasta** (required) - Path to taxpasta merged TSV
- **krona** (optional, not for diamond) - Path to Krona HTML visualization

Examples:

.. code-block:: text

   --classifier "kraken2 db=k2_pluspf taxpasta=/data/kraken2.tsv krona=/data/kraken2.html"
   
   --classifier "centrifuge db=p_compressed+h+v taxpasta=/data/centrifuge.tsv krona=/data/centrifuge.html"
   
   --classifier "diamond db=diamond taxpasta=/data/diamond.tsv"

**--sample ID [--sample ...]**

At least one sample. Multiple allowed. Format:

.. code-block:: text

   --sample "<id>=<sample_id> type=<type> material=<material> [subject_id=<id>] column_<classifier>=<column> ..."

Fields:

- **sample_id** (required) - Identifier matching taxpasta column prefixes
- **type** (required) - ``sample``, ``positive_ctrl``, or ``negative_ctrl``
- **material** (required) - ``DNA`` or ``RNA``
- **subject_id** (optional) - Subject identifier (samples only, not controls)
- **column_<classifier>** (required for each classifier) - Exact column name in taxpasta TSV

Examples:

.. code-block:: text

   --sample "sample_id=SRR001 type=sample material=DNA subject_id=PT-001 column_kraken2=SRR001_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR001_p_compressed+h+v.centrifuge"
   
   --sample "sample_id=ctrl-pos type=positive_ctrl material=DNA column_kraken2=ctrl-pos_k2_pluspf.kraken2.kraken2.report"
   
   --sample "sample_id=ctrl-neg type=negative_ctrl material=DNA column_kraken2=ctrl-neg_k2_pluspf.kraken2.kraken2.report"

**--password PASS**

Password for authentication. The user running ingest must exist and have writer or admin role.

- Case-sensitive
- Required for all ingests

Optional arguments
==================

**--metaval-igv PATH**

Path to metaval output ``igv/`` directory. Includes metaval results in case.

- Path must be to ``igv/`` subdirectory
- Parent directory must contain ``blast/`` and ``extracted_reads/``
- Optional but recommended if metaval was run

Example:

.. code-block:: bash

   --metaval-igv /data/metaval/igv

**--quiet**

Suppress verbose logging output. Useful for batch ingestion.

Example:

.. code-block:: bash

   --quiet

Understanding taxpasta column names
===================================

taxprofiler creates merged TSV files with standardized column naming.

**Kraken2:**

.. code-block:: text

   Format: <sample_id>_<db>.kraken2.kraken2.report
   
   Example: SRR001_k2_pluspf.kraken2.kraken2.report

**Centrifuge:**

.. code-block:: text

   Format: <sample_id>_<db>.centrifuge
   
   Example: SRR001_p_compressed+h+v.centrifuge

**DIAMOND:**

.. code-block:: text

   Format: <sample_id>_<db>.diamond
   
   Example: SRR001_diamond.diamond

To find exact column names:

.. code-block:: bash

   # View header
   head -1 taxpasta_merged.tsv
   
   # Count columns
   head -1 taxpasta_merged.tsv | tr '\t' '\n' | nl

Interpreting error messages
===========================

**"Case already exists: case-001"**

The case_id is already in the database. Solution:
- Use a different case_id
- Delete the existing case first (Admin panel or API)

**"Column not found: SRR001_k2_pluspf.kraken2.kraken2.report"**

Column name doesn't match the taxpasta header. Check:
1. Exact column name in TSV header (case-sensitive)
2. Database suffix matches (e.g., ``k2_pluspf``)
3. Sample ID prefix is correct

**"File not found: /data/multiqc_data.json"**

Path is wrong or file doesn't exist:
1. Check file exists: ``ls -la /data/multiqc_data.json``
2. Use absolute path (``/data/...`` not ``./data/...``)
3. Check permissions: file must be readable

**"Invalid type: sample"**

Type must be one of: ``sample``, ``positive_ctrl``, ``negative_ctrl``

**"Invalid material: genome"**

Material must be: ``DNA`` or ``RNA``

**"metaval path doesn't contain igv/ subdirectory"**

metaval output structure issue:
1. Path must be to ``igv/`` subdirectory
2. Parent must have ``blast/`` and ``extracted_reads/``

Correct structure:

.. code-block:: text

   metaval/
   ├── igv/          ← Pass this path
   ├── blast/
   └── extracted_reads/

Complete working examples
=========================

**Minimal case (1 sample, 1 classifier):**

.. code-block:: bash

   python ingest.py \
     --case-id minimal-001 \
     --order-date 2026-02-20 \
     --multiqc /data/multiqc_data.json \
     --pipeline-info /data/software_versions.yml \
     --classifier "kraken2 db=k2_pluspf taxpasta=/data/kraken2.tsv krona=/data/kraken2.html" \
     --sample "sample_id=SRR001 type=sample material=DNA subject_id=PT-001 column_kraken2=SRR001_k2_pluspf.kraken2.kraken2.report" \
     --password mypassword

**Complex case (3 samples, 3 classifiers, metaval):**

.. code-block:: bash

   python ingest.py \
     --case-id outbreak-2026-02 \
     --order-date 2026-02-15 \
     --multiqc /outbreak/multiqc_data.json \
     --pipeline-info /outbreak/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml \
     \
     --classifier "kraken2 db=k2_pluspf taxpasta=/outbreak/taxpasta/kraken2_k2_pluspf.tsv krona=/outbreak/krona/kraken2_k2_pluspf.html" \
     --classifier "centrifuge db=p_compressed+h+v taxpasta=/outbreak/taxpasta/centrifuge_p_compressed+h+v.tsv krona=/outbreak/krona/centrifuge_p_compressed+h+v.html" \
     --classifier "diamond db=diamond taxpasta=/outbreak/taxpasta/diamond_diamond.tsv" \
     \
     --sample "sample_id=patient-001 type=sample material=DNA subject_id=PT-001 column_kraken2=patient-001_k2_pluspf.kraken2.kraken2.report column_centrifuge=patient-001_p_compressed+h+v.centrifuge column_diamond=patient-001_diamond.diamond" \
     --sample "sample_id=patient-002 type=sample material=DNA subject_id=PT-002 column_kraken2=patient-002_k2_pluspf.kraken2.kraken2.report column_centrifuge=patient-002_p_compressed+h+v.centrifuge column_diamond=patient-002_diamond.diamond" \
     --sample "sample_id=patient-003 type=sample material=DNA subject_id=PT-003 column_kraken2=patient-003_k2_pluspf.kraken2.kraken2.report column_centrifuge=patient-003_p_compressed+h+v.centrifuge column_diamond=patient-003_diamond.diamond" \
     \
     --sample "sample_id=control-positive type=positive_ctrl material=DNA column_kraken2=control-positive_k2_pluspf.kraken2.kraken2.report column_centrifuge=control-positive_p_compressed+h+v.centrifuge column_diamond=control-positive_diamond.diamond" \
     \
     --sample "sample_id=control-negative type=negative_ctrl material=DNA column_kraken2=control-negative_k2_pluspf.kraken2.kraken2.report column_centrifuge=control-negative_p_compressed+h+v.centrifuge column_diamond=control-negative_diamond.diamond" \
     \
     --metaval-igv /outbreak/metaval/igv \
     \
     --password mypassword

**Batch ingest script:**

.. code-block:: bash

   #!/bin/bash
   set -e
   
   # Array of cases: (case_id:order_date:data_path)
   cases=(
     "case-001:2026-02-01:/data/case-001"
     "case-002:2026-02-05:/data/case-002"
     "case-003:2026-02-10:/data/case-003"
   )
   
   for case_spec in "${cases[@]}"; do
       IFS=':' read -r case_id order_date data_path <<< "$case_spec"
       
       echo "Ingesting $case_id..."
       
       python ingest.py \
         --case-id "$case_id" \
         --order-date "$order_date" \
         --multiqc "$data_path/multiqc_data.json" \
         --pipeline-info "$data_path/pipeline_info/software_versions.yml" \
         --classifier "kraken2 db=k2_pluspf taxpasta=$data_path/kraken2.tsv krona=$data_path/kraken2.html" \
         --sample "sample_id=sample1 type=sample material=DNA column_kraken2=sample1_k2_pluspf.kraken2.kraken2.report" \
         --password mypassword \
         --quiet
       
       echo "✓ $case_id ingested"
   done

Tips for reliable ingestion
============================

1. **Use absolute paths** - Never relative paths
2. **Verify files exist** - Check all paths before running
3. **Check column names** - Use ``head -1 file.tsv`` to see headers
4. **Use descriptive case IDs** - Include date or identifier
5. **Document your ingest** - Save ingest command for reproducibility
6. **Test with minimal case first** - Get one working, then scale
7. **Monitor logs** - Watch for errors
8. **Verify in UI** - Check data appears correctly
9. **Backup database** - Before bulk ingestion
10. **Run during off-hours** - Large ingestions take time

Next steps
==========

- :doc:`../administration/ingestion` - Ingestion guide
- :doc:`../administration/taxonomy-reference` - Load taxonomy data
