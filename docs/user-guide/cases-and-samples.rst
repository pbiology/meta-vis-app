====================
Cases and Samples
====================

Understanding the organizational hierarchy
===========================================

**Case** - A single taxonomic profiling run
  A case represents one complete taxprofiler execution. It contains:
  - Sample metadata (IDs, types, materials)
  - Pipeline version and tool versions
  - When the samples were ordered
  - QC metrics aggregated across all samples
  - Review status and reviewer notes

**Sample** - An individual sequencing sample
  A sample is one biological or control sample within a case. Each sample has:
  - Read count and quality metrics
  - Taxonomic profiles from one or more classifiers
  - Sample type (clinical sample, positive control, negative control)
  - Material type (DNA or RNA)

**Classifier** - A taxonomic classification tool
  Common classifiers include Kraken2, Centrifuge, and DIAMOND. Each sample can have:
  - One or more classifier results
  - Different reference databases
  - Different read abundance tables

Viewing cases
=============

The **Case List** shows all cases you have access to.

**Columns:**
- Case ID - Unique identifier
- Order Date - When samples were ordered
- Sample Count - Number of samples in the case
- Status - Reviewed / Not reviewed
- Last Updated - When the case was last modified

**Actions:**
- Click a case to view details
- Click the review checkbox to mark as reviewed/unreviewed (writers only)
- Delete a case (admins only)

Case overview
=============

When you click a case, you see the **Case Detail** page.

**Overview section:**
- Case ID and order date
- Total samples and classifiers
- QC metrics summary table:
  - Read counts
  - Q30 percentage
  - Host removal percentage
- Notes from reviewers (writers can edit)
- Review status toggle (writers can change)

**Tabbed sections:**
- **QC Tables** - Per-classifier quality metrics
- **Krona** - Interactive taxonomy visualization
- **Taxonomy** - Searchable, filterable taxonomy table
- **Provenance** - Pipeline and tool versions

QC Tables
---------

The QC Tables tab shows metrics per classifier:

.. list-table::
   :header-rows: 1
   :widths: 30, 50

   * - Metric
     - Meaning
   * - Unclassified %
     - Reads that couldn't be assigned to any organism
   * - Host %
     - Reads matching the host genome (usually removed)
   * - Species Count
     - Unique species detected
   * - Genera Count
     - Unique genera detected
   * - Top 5 Taxa
     - Most abundant organisms

Switch between classifiers using the tabs.

Viewing samples
===============

Click on a sample name to view the **Sample Detail** page.

**Sample metadata:**
- Sample ID
- Type: sample, positive control, or negative control
- Material: DNA or RNA
- Read counts and quality metrics

**Classifier results:**
- Tabs for each classifier
- Per-classifier QC table
- Taxonomy table (see below)

Taxonomy table
==============

The taxonomy table shows all detected organisms with their abundances.

**Columns:**
- Rank - Taxonomic rank (kingdom, phylum, class, order, family, genus, species, etc.)
- Name - Organism name
- Abundance - Number of classified reads
- %Abundance - Percentage of classified reads

**Filtering:**
- Use the Kingdom dropdown to filter to specific superkingdoms (Bacteria, Archaea, Viruses, Eukaryota, etc.)
- Use the Rank dropdown to show results only at specific taxonomic levels

**Searching:**
- Type in the search box to find organisms by name
- Partial matches work ("Escherichia" finds "Escherichia coli")
- Case-insensitive

**Clicking a taxon:**
- Click the taxon name to view the **Taxa Detail** page
- Shows full taxonomy lineage
- Shows NCBI taxon ID
- If metaval results are available, shows verification status and links to IGV/BLAST results

Metaval-verified taxa
=====================

When metaval results are ingested, verified taxa appear with a blue verification pill:

- **Verified (IGV+BLAST)** - Complete coverage and sequence verification
- **IGV only** - Coverage visualization available
- **BLAST only** - Sequence match available

Click the pill to view the **Metaval Details** page.

Outbreak alerts
===============

If a taxon appears in multiple cases, it may appear with an **Outbreak Alert** indicator:

- **Amber pill** - Viral taxon detected in 2+ cases in the alert window
- Links to the **Alerts** page to view all outbreak flags
- Customizable time window (7, 14, or 30 days)

Tips for effective case review
==============================

1. **Start with QC** - Check read counts, unclassified %, host %
2. **Compare classifiers** - Do results agree across Kraken2, Centrifuge, DIAMOND?
3. **Look for outliers** - Unexpected taxa in controls? Very abundant taxa?
4. **Check metaval** - Are key organisms verified?
5. **Note findings** - Add notes to the case for other reviewers
6. **Mark reviewed** - Toggle the review status when done

Next steps
==========

- :doc:`taxonomy-browser` - Advanced taxonomy searching
- :doc:`metaval-integration` - Working with verified results
- :doc:`outbreak-detection` - Monitoring outbreaks
