================
NTC monitoring
================

A **No Template Control (NTC)** is a sample run through the metagenomic
pipeline with no target organism present. It surfaces contamination from
reagents, kits, equipment, and the lab environment. meta-vis-app collects
all NTCs across cases and tracks contamination patterns over time.

NTCs are samples with ``type=negative_ctrl`` — set during :doc:`ingestion
<ingesting-data>`.

NTC Trends
==========

Sidebar → **NTC Trends**. The page shows what's appearing across all
negative controls in a chosen window, grouped by extraction material.

Filters
-------

- **Material tab** — DNA or RNA. NTCs are tracked separately per material
  because contamination profiles differ between extraction protocols.
- **Minimum reads** — abundance floor for inclusion (1 / 3 / 5 / 10 / 20).
  Higher value = less noise, more chance of missing emerging contaminants.
  Default 3.
- **Minimum case %** — only show taxa present in at least this fraction of
  NTCs in the window (5 / 10 / 20 / 25 / 50%). Default 10%.
- **Time window** — 30 / 90 / 180 days. Default 90.

Charts
------

**Kingdom breakdown.** One bar per NTC, height = classified read count,
colours = superkingdom. Watch for sudden spikes, new kingdoms appearing,
or viruses in NTCs (rare and concerning).

**Total classified reads.** Scatter of total classified reads per NTC over
time. A dashed reference line at 1 000 reads marks a typical "watch this"
threshold; tune to your lab's baseline.

**Recurring taxa.** Line per organism that appears in multiple NTCs in the
window. Flat lines = stable low-level background; upward trends or new
lines = investigate.

Hovering any chart element shows the underlying sample / case / read
count.

Contaminant alert banner
========================

When a taxon on the **Known Contaminants** list exceeds its alert threshold
in any NTC in the window, an orange banner appears at the top of the page:

.. code-block:: text

   ⚠️ Known contaminants detected in NTCs

   Escherichia coli · 3 cases · > 5 reads threshold
   Propionibacterium acnes · 1 case · > 3 reads threshold

The banner links to **NTC Lists** for threshold management.

NTC Lists
=========

Sidebar → **NTC Lists**. Two side-by-side lists:

Ignored taxa
------------

Organisms excluded from NTC analysis entirely — they will not appear in
charts, statistics, or alerts. Use for known environmental background
(skin flora, water organisms, dust) that you have decided not to track.

Each entry: taxon name, kingdom, NCBI taxon id, reason (free text),
who added it, when.

Known contaminants
------------------

Organisms tracked explicitly because their presence indicates a process
problem. Each entry carries an **alert threshold** in reads — if any NTC
in the window exceeds this for the taxon, the contaminant alert banner
fires.

Each entry: taxon name, kingdom, NCBI taxon id, alert threshold (editable),
notes, who added it, when.

Managing entries
----------------

Both lists support adding by NCBI taxon id:

1. Click **+ Add taxon**.
2. Enter the NCBI taxon id (e.g. ``562`` for *E. coli*).
3. **Look up** populates name and kingdom.
4. For known contaminants, set the alert threshold.
5. Optional: add a reason / note.
6. **Add**.

Inline edit: hover the **Reason** (ignored taxa) or **Alert threshold**
(known contaminants) cell, click the pencil, edit, Enter to save.

**Roles:** writers can add and edit. Only admins can remove entries.

Integration with case review
============================

NTC findings flow back into clinical review:

- **Case list** shows an amber pill on cases whose samples contain known
  contaminants. The pill links to a contamination detail view.
- **Sample review** — when interpreting an organism in a sample, check
  whether the same organism also appears in an NTC from the same run. If
  it does, treat as likely artefact and interpret with caution.

How the numbers are computed
============================

- Data source: ``samples`` collection filtered to ``type=negative_ctrl``.
- "Recurring" means present in at least the configured percentage of NTCs
  in the window, with abundance above the configured floor, classified by
  Kraken2.
- Time windows include ±1 day padding to keep query bounds simple.
- Contaminant alert results are cached for one hour. Cache is invalidated
  by any new ingest or any change to the ignored / known-contaminant
  lists.

See also
========

- :doc:`outbreak-detection` — analogous monitoring for clinical samples
- :doc:`cases-and-samples` — reviewing individual cases
