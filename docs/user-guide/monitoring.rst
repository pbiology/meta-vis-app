===========================
Monitoring across cases
===========================

Two views surface patterns that span more than one case: **outbreak
alerts** (clinical samples) and **NTC monitoring** (negative controls).
Both compute on a sliding time window and cache results for one hour,
invalidating on new ingest.

Outbreak alerts
===============

The app flags viral taxa that appear in two or more cases within a
chosen time window. Useful for catching emerging clusters early.

Inclusion criteria
------------------

- Superkingdom *Viruses*.
- Rank species, no-rank, or serotype.
- More than one classified read.
- Not on the **outbreak ignorelist**.

How to find them
----------------

Outbreak alerts appear in three places:

- **Alerts page** (Sidebar → Alerts) — the dashboard. Lists every
  flagged taxon with case count, sample count, latest case, and a link
  to add the taxon to the ignorelist.
- **Case list** — cases containing a flagged taxon carry an amber
  warning indicator.
- **Taxonomy table** — flagged organisms get an amber pill next to the
  name when the case is part of an active alert.

Time window
-----------

Adjustable on the Alerts page: 7, 14, or 30 days. Narrower windows
focus on very recent events; wider windows catch slow-build clusters.

Outbreak ignorelist
-------------------

Excludes taxa from outbreak detection. Typical entries: known
environmental contaminants, ubiquitous organisms, and previously
investigated taxa that produced consistent false alarms.

- Writers can add entries (Alerts page → *Add to ignorelist*).
- Admins can remove entries.
- Each entry is timestamped and attributed to its author; reasons are
  free text and visible in the list.

Adding to or removing from the ignorelist invalidates the alert cache,
so the next page load reflects the change immediately.

What the feature does and does not do
-------------------------------------

It finds organisms in common across cases. It does not look at patient
location, department, symptoms, or temporal patterns finer than the
window. Treat alerts as a prompt to investigate, not as a confirmed
outbreak. Always cross-check abundance, classifier agreement, and (if
available) metaval evidence before escalating.

NTC monitoring
==============

A **No Template Control (NTC)** is a sample run through the pipeline
with no target organism present — it surfaces contamination from
reagents, kits, equipment, and the lab environment. Samples flagged
``type=negative_ctrl`` during :doc:`ingest <loading-data>` feed this
view.

NTC Trends page
---------------

Sidebar → **NTC Trends**. Shows what is appearing across all NTCs in a
chosen window, grouped by extraction material.

**Filters**

- **Material tab** — DNA or RNA. NTCs are tracked separately because
  contamination profiles differ between extraction protocols.
- **Minimum reads** — abundance floor (1 / 3 / 5 / 10 / 20). Default 3.
- **Minimum case %** — only show taxa present in at least this share of
  NTCs in the window (5 / 10 / 20 / 25 / 50%). Default 10%.
- **Time window** — 30 / 90 / 180 days. Default 90.

**Charts**

- **Kingdom breakdown** — one bar per NTC, height = classified reads,
  colours = superkingdom.
- **Total classified reads** — scatter of total classified reads per
  NTC over time, with a dashed reference line at 1 000 reads.
- **Recurring taxa** — one line per organism appearing in multiple
  NTCs in the window.

Hovering any chart element shows the underlying sample, case, and read
count.

Contaminant alert banner
~~~~~~~~~~~~~~~~~~~~~~~~

When a taxon on the known-contaminants list exceeds its alert
threshold in any NTC in the window, an orange banner appears at the
top of the page listing the taxon, the affected NTC count, and the
threshold. The banner links to **NTC Lists** for management.

NTC Lists page
--------------

Sidebar → **NTC Lists**. Two side-by-side lists.

**Ignored taxa**
   Excluded from NTC analysis entirely — they won't show in charts,
   statistics, or alerts. Use for known environmental background
   (skin flora, water organisms, dust) you have decided not to track.

**Known contaminants**
   Organisms tracked explicitly because their presence indicates a
   process problem. Each entry carries an alert threshold in reads —
   exceeding it in any NTC fires the contaminant banner.

For both lists each entry stores taxon name, kingdom, NCBI taxon id,
who added it, when, and either a reason (ignored) or notes + threshold
(known contaminants).

Adding by NCBI taxon id:

1. **+ Add taxon**.
2. Enter the taxon id (e.g. ``562`` for *E. coli*).
3. **Look up** populates name and kingdom.
4. For known contaminants, set the threshold.
5. Optional notes/reason.
6. **Add**.

Inline edit: hover the *Reason* or *Alert threshold* cell, click the
pencil, edit, Enter to save.

**Roles**: writers can add and edit entries; only admins can remove.

Integration with case review
----------------------------

NTC findings inform clinical interpretation:

- **Case list** shows an amber pill on cases whose samples contain
  known contaminants.
- When interpreting a detection in a clinical sample, check whether
  the same organism also appears in an NTC from the same run. If it
  does, treat the clinical detection as likely artefact and document
  accordingly.

How the numbers are computed
============================

Both monitoring views run a MongoDB aggregation bounded by the time
window, cluster the results in Python, and cache for one hour. The
cache is invalidated by any new case ingest, any ignorelist edit, and
any known-contaminants edit. Query time is bounded by cases in the
window, not by total case count, so both views stay fast as the
database grows.

See also
========

- :doc:`reviewing-cases` — opening individual cases
- :doc:`investigating-detections` — what to do with a flagged organism
- :doc:`administration` — the audit log of ignorelist and contaminant changes
