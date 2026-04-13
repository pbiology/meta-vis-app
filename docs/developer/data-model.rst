===========
Data Model
===========

Complete reference for the MongoDB data structures.

Collections overview
====================

.. list-table::
   :header-rows: 1
   :widths: 25, 50, 25

   * - Collection
     - Purpose
     - Documents
   * - ``cases``
     - Pipeline runs
     - One per case
   * - ``samples``
     - Sequencing samples
     - One per sample
   * - ``users``
     - User accounts
     - One per user
   * - ``taxa``
     - Taxonomy reference (NCBI)
     - ~2.4 million
   * - ``blobs``
     - Krona/IGV HTML (if using MongoDB backend)
     - One per blob
   * - ``metaval_results``
     - BLAST results and metadata
     - One per verified organism
   * - ``outbreak_ignorelist``
     - Organisms excluded from alerts
     - Variable

Cases collection
================

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "case_id": "case-001",
     "order_date": ISODate("2026-02-20T00:00:00Z"),
     "samples": [
       "SRR13439790",
       "CTRL-01"
     ],
     "classifiers": [
       "kraken2",
       "centrifuge",
       "diamond"
     ],
     "pipeline_info": {
       "taxprofiler_version": "1.1.0",
       "tools": {
         "kraken2": "2.1.2",
         "centrifuge": "1.0.4",
         "diamond": "2.1.10"
       }
     },
     "reviewed": false,
     "reviewed_by": null,
     "reviewed_at": null,
     "notes": "Initial assessment: multiple viral agents detected",
     "created_at": ISODate("2026-02-20T10:30:00Z"),
     "created_by": "admin",
     "updated_at": ISODate("2026-02-20T14:20:00Z")
   }

**Field reference:**

- **_id** - MongoDB unique ID
- **case_id** - User-friendly case identifier (unique)
- **order_date** - When samples were ordered
- **samples** - List of sample IDs in this case
- **classifiers** - List of classifiers used
- **pipeline_info** - Tool versions and pipeline metadata
- **reviewed** - Boolean, case marked as reviewed?
- **reviewed_by** - Username who marked as reviewed
- **reviewed_at** - Timestamp of review
- **notes** - Reviewer notes (HTML formatted)
- **created_at** - Case creation timestamp
- **created_by** - Username who created case
- **updated_at** - Last update timestamp

Samples collection
==================

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "case_id": "case-001",
     "case_id_str": "case-001",
     "order_date": ISODate("2026-02-20T00:00:00Z"),
     "sample_id": "SRR13439790",
     "type": "sample",
     "material": "DNA",
     "subject_id": "PT-001",
     "qc_metrics": {
       "total_reads": 1500000,
       "read_count_final": 1350000,
       "q30_percentage": 94.2,
       "host_removal_percentage": 35.0
     },
     "profiles": {
       "kraken2": [
         {
           "taxid": 11320,
           "name": "Influenza A virus",
           "rank": "species",
           "superkingdom": "Viruses",
           "abundance": 45000,
           "percentage": 3.33
         },
         {
           "taxid": 562,
           "name": "Escherichia coli",
           "rank": "species",
           "superkingdom": "Bacteria",
           "abundance": 120000,
           "percentage": 8.89
         }
       ],
       "centrifuge": [
         {
           "taxid": 11320,
           "name": "Influenza A virus",
           "rank": "species",
           "superkingdom": "Viruses",
           "abundance": 42000,
           "percentage": 3.11
         }
       ]
     },
     "created_at": ISODate("2026-02-20T10:30:00Z"),
     "created_by": "admin"
   }

**Field reference:**

- **_id** - MongoDB unique ID
- **case_id** - Reference to parent case
- **case_id_str** - Denormalized case_id (for querying)
- **order_date** - Denormalized from case (for querying)
- **sample_id** - Sample identifier
- **type** - "sample", "positive_ctrl", or "negative_ctrl"
- **material** - "DNA" or "RNA"
- **subject_id** - Optional reference to study subject
- **qc_metrics** - Read counts and quality statistics
- **profiles** - Taxonomy by classifier
  - Each classifier has array of organisms
  - Each organism has taxid, name, rank, abundance

Users collection
================

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "username": "analyst1",
     "password_hash": "$2b$12$...",
     "role": "writer",
     "preferences": {
       "preferred_kingdoms": ["Bacteria", "Viruses"]
     }
   }

**Field reference:**

- **_id** - MongoDB unique ID
- **username** - Unique username
- **password_hash** - bcrypt-hashed password (never plaintext)
- **role** - "reader", "writer", or "admin"
- **preferences** - Per-user UI settings (optional, written on first save)

  - **preferred_kingdoms** - Default kingdom filter for taxonomy tables.
    Any subset of ``["Bacteria", "Viruses", "Eukaryota", "Archaea"]``.
    Defaults to ``["Viruses"]`` when the field is absent.

**Security notes:**
- Passwords are hashed with bcrypt
- Never stored in plaintext
- Never transmitted over network (only JWT token)
- Use HTTPS in production

Taxa collection
===============

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "taxid": 11320,
     "name": "Influenza A virus",
     "scientific_name": "Influenza A virus",
     "rank": "species",
     "superkingdom": "Viruses",
     "phylum": "Unassigned",
     "class": "Unassigned",
     "order": "Artipillar",
     "family": "Orthomyxoviridae",
     "genus": "Influenzavirus",
     "species": "Influenza A virus",
     "parent_taxid": 11308,
     "lineage": [
       11,        // all
       10239,     // viruses
       11308,     // influenzavirus
       11320      // influenza A virus
     ],
     "lineage_names": [
       "all",
       "Viruses",
       "Influenzavirus",
       "Influenza A virus"
     ],
     "taxdump_version": "2026-02-01",
     "clinical_notes": "Cause of seasonal/pandemic influenza. Highly contagious respiratory pathogen.",
     "updated_at": ISODate("2026-02-01T00:00:00Z")
   }

**Field reference:**

- **taxid** - NCBI taxonomy ID
- **name** - Organism name
- **scientific_name** - Scientific name variant
- **rank** - Taxonomic rank
- **superkingdom** through **species** - Taxonomic levels
- **parent_taxid** - Parent in hierarchy
- **lineage** - Array of ancestor taxids (for querying)
- **lineage_names** - Names corresponding to lineage
- **taxdump_version** - Date of NCBI taxdump used
- **clinical_notes** - Curator-added clinical information
- **updated_at** - Last update from NCBI

Blobs collection (MongoDB backend only)
========================================

**Document structure:**

.. code-block:: json

   {
     "_id": "krona/507f1f77bcf86cd799439011/kraken2.html",
     "data": BinData(...)
   }

**Field reference:**

- **_id** - Blob path (key)
- **data** - Binary blob data (Krona HTML or IGV report)

**Note:** When using S3 backend, this collection is empty and blobs are in S3 object storage instead.

Metaval results collection
==========================

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "case_id": "case-001",
     "sample_id": "SRR13439790",
     "classifier": "kraken2",
     "taxid": 11320,
     "organism_name": "Influenza A virus",
     "blast_result": {
       "tool": "blastn",
       "identity_percent": 98.5,
       "alignment_length": 2500,
       "evalue": 0.0,
       "subject": "NC_007372.1"
     },
     "igv_report_path": "igv/507f1f77bcf86cd799439011/SRR13439790/kraken2/Influenza-A-virus_report.html",
     "consensus_sequence": "GGACTGATG...",
     "verified_at": ISODate("2026-02-20T10:30:00Z")
   }

**Field reference:**

- **_id** - MongoDB unique ID
- **case_id** - Parent case
- **sample_id** - Parent sample
- **classifier** - Which classifier detected this
- **taxid** - NCBI taxon ID
- **organism_name** - Organism display name
- **blast_result** - BLAST alignment data
  - **identity_percent** - Sequence similarity
  - **alignment_length** - Length of match
  - **evalue** - Statistical significance
  - **subject** - Reference sequence ID
- **igv_report_path** - Path to IGV coverage visualization
- **consensus_sequence** - Derived consensus sequence
- **verified_at** - Timestamp verification completed

Outbreak ignorelist collection
===============================

**Document structure:**

.. code-block:: json

   {
     "_id": ObjectId("..."),
     "taxid": 562,
     "name": "Escherichia coli",
     "reason": "Ubiquitous gut flora, low clinical significance",
     "added_by": "analyst1",
     "added_at": ISODate("2026-02-15T10:30:00Z")
   }

**Field reference:**

- **_id** - MongoDB unique ID
- **taxid** - NCBI taxon ID
- **name** - Organism name
- **reason** - Why this organism is ignored
- **added_by** - Username who added entry
- **added_at** - Timestamp added

Indexes
=======

Key indexes for performance:

**Cases collection:**

.. code-block:: javascript

   db.cases.createIndex({ "case_id": 1 })              // lookups
   db.cases.createIndex({ "order_date": 1 })           // outbreak detection
   db.cases.createIndex({ "created_at": -1 })          // list ordering

**Samples collection:**

.. code-block:: javascript

   db.samples.createIndex({ "case_id": 1 })            // by case
   db.samples.createIndex({ "sample_id": 1 })          // lookups
   db.samples.createIndex({ "order_date": 1 })         // outbreak window
   db.samples.createIndex({ "profiles.*.taxid": 1 })   // organism lookup

**Users collection:**

.. code-block:: javascript

   db.users.createIndex({ "username": 1 }, { unique: true })  // login

**Taxa collection:**

.. code-block:: javascript

   db.taxa.createIndex({ "taxid": 1 }, { unique: true })      // lookups
   db.taxa.createIndex({ "name": "text" })                    // search
   db.taxa.createIndex({ "lineage": 1 })                      // hierarchy

Querying patterns
=================

**Find cases by ID:**

.. code-block:: javascript

   db.cases.findOne({ case_id: "case-001" })

**Get all samples in a case:**

.. code-block:: javascript

   db.samples.find({ case_id: "case-001" })

**Search organisms by name:**

.. code-block:: javascript

   db.taxa.find({ $text: { $search: "influenza" } })

**Find samples with specific organism:**

.. code-block:: javascript

   db.samples.find({
     "profiles.kraken2.taxid": 11320
   })

**Outbreak detection window:**

.. code-block:: javascript

   db.samples.aggregate([
     {
       $match: {
         order_date: {
           $gte: ISODate("2026-02-13"),
           $lte: ISODate("2026-02-20")
         }
       }
     },
     { $unwind: "$profiles.kraken2" },
     {
       $group: {
         _id: "$profiles.kraken2.taxid",
         cases: { $addToSet: "$case_id" },
         samples: { $push: "$sample_id" }
       }
     },
     {
       $match: {
         cases: { $size: { $gte: 2 } }
       }
     }
   ])

Next steps
==========

- :doc:`architecture` - System design overview
- :doc:`contributing` - Development setup
