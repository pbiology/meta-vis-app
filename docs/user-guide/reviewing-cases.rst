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
   nucleic acid, subject id) and the per-classifier taxonomic profile.
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

The top bar holds the case id, the review status and, for writers and
admins, the **Mark reviewed** button. The sidebar on the left switches
between the case's sections (see `Case sections`_). Notes live under
**Comments**; they are editable by writers and admins, and each note is
timestamped per author.

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

Case sections
-------------

**Overview**
   The case summary (order date, reviewer, ticket, status, sample count,
   analysis type, platform, pipeline) with any warning pills, the samples
   table, the two most recent comments, and known-pathogen hits across
   the case's samples.

**Samples**
   The samples table, then the classifier results (see `Classifier
   results`_). Click a sample row, here or on the overview, to open its
   sample page (see `Sample detail`_).

**MultiQC**
   The run's MultiQC report, embedded and downloadable. Only shown when a
   report was uploaded with the run.

**Report**
   The report draft for this analysis.

**Comments**
   All notes on the case.

**Provenance**
   Pipeline name, version, and per-tool versions from the
   ``pipeline_info`` files captured at ingest.

Sample QC columns
-----------------

The samples table puts each sample's QC side by side with its negative
controls. Hover a column header to see which tool the number comes from.

- **taxprofiler:** **Passed** (share of raw reads passing fastp),
  **Host** (reads removed as host by bowtie2), **Non-host reads** and
  **Q30**.
- **TRANA:** **Passed** (reads left after processing), **Mean Q** and
  **N50**, from NanoPlot.

**Host** here is the host-removal rate *before* classification. It is not
the same number as the per-classifier human share on the sample page,
which divides human reads by what the classifier processed.

.. _which-samples-were-topped-up:

Which samples were topped up
----------------------------

A case is often delivered twice on purpose: a partial dataset first, so
analysis can start sooner, then a top-up for any sample that had not
reached the agreed data amount. From the second analysis onwards, a
**vs previous run** column next to **Total reads** in the samples table
says how each sample compares to the most recent earlier run it appeared
in:

``▲ +5.2M``
   Topped up — this sample gained data since that run.

``no top-up``
   Re-delivered with exactly the same read count. Nothing was added, so
   the sample is still at whatever depth it had before.

``▼ −0.4M``
   Fewer reads than before. Not expected on a top-up; worth asking about.

``new``
   Not present in any earlier run of this case.

``?``
   The read count is missing on one side, so the two cannot be compared.
   Shown rather than assumed unchanged.

Hover any marker for the exact before/after counts. A case's first
analysis has nothing to compare against, so the column is not shown.

Negative controls
-----------------

Contaminant flagging compares a sample against the negative controls from
the **same run and the same nucleic acid**. When an analysis has no usable
control for a nucleic acid — none was loaded, or the one loaded produced no
classifier data — an amber banner says so above the samples table, and
the affected sample pages repeat it. Without a control the taxonomy table
shows no NTC column and flags no contaminants, which otherwise looks
identical to a run whose control came back clean.

Classifier results
------------------

Below the samples table in the **Samples** section, one tab per
classifier. Each tab shows the classifier's database, a table with one
row per sample, and below it an interactive Krona plot for a quick sense
of what dominates each sample.

For taxprofiler the table columns are **Unclassified**, **Host**,
**Species**, **Genera**, **Positive control** and **Top taxa**. For TRANA
they are **Reads (raw)** and **Top taxa**, under the heading *Taxonomic
profile*.

**Host** is the share of everything the classifier processed —
classified plus unclassified reads — that landed on *Homo sapiens*. The
percentages beside **Top taxa** use a different denominator: the
non-host classified reads, matching the taxonomy table. See
:doc:`investigating-detections`.

.. note::

   The **Host** figure was previously divided by host plus unclassified
   reads, which left out the rest of the run and overstated host
   content, often by a wide margin. It now divides by all processed
   reads, so the column reads lower than it used to for the same data.
   Figures quoted in reports written before this change do not compare
   like for like.

Sample detail
=============

Click a sample name from the case to open the sample page. You get:

- Sample metadata (id, type, nucleic acid, subject id).
- A one-line QC summary. **Details** opens the full set, including raw
  read count and Q20. To compare QC across samples, use the QC columns of
  the case's samples table instead.
- One tab per classifier, each with a taxonomy table for the sample.

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
