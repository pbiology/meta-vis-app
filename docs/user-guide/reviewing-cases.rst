==================
Reviewing cases
==================

The clinician-facing workflow. Once data is loaded (see
:doc:`loading-data`), case review happens entirely in the UI.

Core concepts
=============

**Case**
   One pipeline run. Holds the run's QC, the list of samples, the order
   date, review state, and reviewer notes.

**Sample**
   One sequencing sample inside a case. Has its own metadata (type,
   material, subject id) and the per-classifier taxonomic profile.

**Subject**
   A patient/research subject. One subject can span many cases; each
   clinical case belongs to exactly one subject. Browse subjects and
   drill into their cases from the **Subjects** sidebar entry.

**Classifier**
   A taxonomic classification tool. For taxprofiler cases that's
   typically Kraken2, Centrifuge, and/or DIAMOND; for Trana cases it's
   Emu. A sample can carry results from more than one classifier; the
   UI tabs between them.

Case list
=========

Sidebar → **Cases**. One row per case, with the case id, order date,
sample count, review status, last-updated time, and any per-case warning
pills (outbreak detection or known-contaminant hits — see
:doc:`monitoring`).

- Click a row to open the case.
- The review checkbox is editable inline by writers and admins.
- Delete is admin-only.

Case detail
===========

Top of the page: case id, order date, sample summary, review status
toggle, notes. Notes are editable by writers and admins; multiple notes
are supported and timestamped per author.

Below, a tabbed view:

**QC tables**
   Per-classifier quality metrics, one table per classifier. Columns
   include read counts, unclassified %, host removal %, species count,
   genera count, top taxa.

**Krona**
   Interactive Krona plot, per classifier. Useful for a quick visual
   sense of what dominates each sample.

**Taxonomy**
   The searchable taxonomy table — your main investigation surface.
   Covered in :doc:`investigating-detections`.

**Provenance**
   Pipeline name, version, and per-tool versions from the
   ``pipeline_info`` files captured at ingest.

Sample detail
=============

Click a sample name from the case to open the sample page. You get:

- Sample metadata (id, type, material, subject id).
- Read counts and quality metrics.
- One tab per classifier, each with that classifier's QC summary and a
  taxonomy table for the sample.

Subjects
========

Sidebar → **Subjects**. One row per subject, showing the subject id,
sex, and the number of shotgun and amplicon analyses (cases) associated
with that subject. The list is searchable by subject id.

- Click a row to open the subject page.
- The subject page shows the basic subject info (id, sex) and a table
  of every case the subject appears in, with the same core stats as the
  case list (date, analysis type, platform, samples, review status).
- Click a case row to open it in a new tab.

Notes
=====

Cases support a free-text note field, edited inline. Anyone with the
writer role or higher can edit. Edits are recorded as audit events
(see :doc:`administration`).

There are no per-case access restrictions — every user with any role
sees every case.

See also
========

- :doc:`investigating-detections` — investigating a single detection
- :doc:`monitoring` — outbreak and contamination signals across cases
- :doc:`administration` — roles and the audit trail
