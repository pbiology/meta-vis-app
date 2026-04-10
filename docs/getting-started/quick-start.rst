===========
Quick Start
===========

After completing the :doc:`installation` steps, you should have:

- A running backend at ``http://localhost:8000``
- A running frontend at ``http://localhost:5173``
- An admin account created

Log in to the app
=================

1. Navigate to ``http://localhost:5173`` in your browser
2. Log in with your admin credentials
3. You should see an empty case list

Load sample data
================

meta-vis-app includes test data. To ingest it:

.. code-block:: bash

   cd backend
   conda activate meta-vis-app

   python ingest.py \
     --case-id test-case-001 \
     --order-date 2026-02-20 \
     --multiqc test-data/multiqc_data.json \
     --pipeline-info test-data/pipeline_info/nf_core_pipeline_software_mqc_versions.yml \
     --classifier "kraken2 db=k2_pluspf taxpasta=test-data/kraken2_k2_pluspf.tsv krona=test-data/kraken2_k2_pluspf.html" \
     --classifier "centrifuge db=p_compressed+h+v taxpasta=test-data/centrifuge_p_compressed+h+v.tsv krona=test-data/centrifuge_p_compressed+h+v.html" \
     --sample "sample_id=SRR13439790 type=sample material=DNA column_kraken2=SRR13439790_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR13439790_p_compressed+h+v.centrifuge" \
     --password yourpassword

Explore the app
===============

1. **Go to the case list** - You should see "test-case-001" with QC metrics
2. **Click the case** - View per-classifier QC tables and Krona plots
3. **Click a sample** - See the taxonomy table with search and filtering
4. **Explore taxonomy** - Search for taxa, filter by kingdom, view details

What to try next
================

- **Load more classifiers** - See how the UI handles multiple taxonomic analyses
- **Test metaval integration** - If you have metaval results, see :doc:`../user-guide/metaval-integration`
- **Explore outbreak detection** - Check the Alerts page (if multiple cases exist)
- **Test user roles** - Create a writer account and see what they can do

More information
================

- :doc:`../user-guide/cases-and-samples` - Full guide to cases and samples
- :doc:`../user-guide/taxonomy-browser` - How to search and filter taxonomy
- :doc:`../administration/ingestion` - Detailed ingest.py reference
