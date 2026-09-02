==================
Reviewing cases
==================

The clinician-facing workflow. Once data is loaded (see
:doc:`loading-data`), case review happens entirely in the UI.

Core concepts
=============

**Case**
   One clinical case — a patient, an order, a ticket. Holds the order
   date, the subject, and the notes. A case can be sequenced more than
   once, so it may have several analyses.

**Analysis**
   One pipeline run of a case. Holds that run's QC, samples, classifiers,
   report draft and review state. When a case is re-sequenced the new
   analysis becomes the current one and the earlier run is marked
   *superseded* — it is kept, not replaced.

**Sample**
   One sequencing sample inside an analysis. Has its own metadata (type,
   material, subject id) and the per-classifier taxonomic profile.
   Re-sequencing produces a fresh set of samples belonging to the new
   analysis.

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

Sidebar → **Cases**. One row per clinical case, showing its **current
analysis**: case id, order date, sample count, review status,
last-updated time, and any per-case warning pills (outbreak detection or
known-contaminant hits — see :doc:`monitoring`).

A case that has been sequenced more than once shows a version badge
(``v2``) and a ``latest`` marker, with an arrow to the left of the case
id:

- Click the arrow to reveal the earlier analyses, indented and greyed
  beneath the current one. **Expand all** / **Collapse all** in the
  toolbar does the same for every multi-run case on the page.
- Each row keeps its own review status. An earlier analysis that was
  reviewed still reads *Reviewed* — the record of who signed it off is
  not rewritten by a later run.
- Click any row to open that analysis. Rows open in a new tab, which is
  the intended way to compare two runs: put them side by side.
- Delete is admin-only. On the current row it deletes the whole case; on
  a superseded row it deletes just that analysis.

Counts in the toolbar (pending / reviewed / total) count current analyses
only, so a re-sequenced case is counted once and an unreviewed run that
has since been superseded does not sit in the pending queue forever.

Case detail
===========

Top of the page: case id, order date, sample summary, review status
toggle, notes. Notes are editable by writers and admins; multiple notes
are supported and timestamped per author.

Notes belong to the **case**, not to a single run, so they are visible and
writable from every analysis of that case and survive re-sequencing.
Marking reviewed applies to the **analysis** you are looking at.

If the case has more than one analysis, a ``v2 of 3`` pill next to the
case id lists them all, each with its date and review status. Selecting
one opens it in a new tab — there is no side-by-side diff view, so
comparison is done by arranging two tabs on screen.

Opening an earlier analysis shows a banner saying it has been superseded,
with a link to the current one. The page is otherwise fully usable: the
older run's QC, taxonomy and Krona plots are all still there.

When a case is re-sequenced, the new analysis starts with an empty report
draft. If the earlier run had one, the **Report** tab offers to copy its
selections across. This is never automatic — a taxon picked against one
run's data should not silently enter another run's report — and anything
that no longer applies (a sample or taxon absent from the new run) is
dropped and listed.

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
