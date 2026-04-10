================
NTC Monitoring
================

Understanding and managing No Template Controls (NTCs) for quality assurance.

What is an NTC?
===============

A **No Template Control (NTC)** is a sample intentionally run through your metagenomic pipeline containing no target organisms. It serves as a critical quality control measure to:

- Detect contamination in reagents, kits, or equipment
- Identify contaminating organisms introduced during sample preparation or sequencing
- Monitor environmental contamination in your lab
- Track trends in contamination over time

When NTCs show unexpected taxa, it indicates a problem with your workflow that could affect the reliability of your clinical results.

NTC Trends Page
===============

The **NTC Trends** page provides real-time monitoring of contamination patterns across all negative controls.

Access
------

- Sidebar → **NTC Trends**
- Or from **NTC Lists** → back button

Overview Section
----------------

At the top of the page, a summary shows:

- **Total NTCs** in the selected time window
- **Recurring taxa** count - how many organisms appear in multiple NTCs
- **Status indicator**:
  - 🟢 Green: No recurring taxa (normal)
  - 🟡 Amber: Recurring taxa detected (investigate)

Filters and Controls
--------------------

**Material tabs** (top right):

- **DNA** - NTCs from DNA-based protocols
- **RNA** - NTCs from RNA-based protocols

Switch tabs to compare contamination patterns between extraction methods.

**Minimum reads threshold**:

- Filter out very low-abundance organisms
- Options: 1, 3, 5, 10, 20 reads
- Default: 3 reads
- Lower threshold → more sensitivity (catches rare contaminants)
- Higher threshold → more specificity (ignores noise)

**Minimum case percentage**:

- Show only organisms in ≥ X% of NTCs
- Options: 5%, 10%, 20%, 25%, 50%
- Default: 10%
- Higher percentage → only persistent problems
- Lower percentage → catches emerging issues

**Time window**:

- **30d** - Recent trends (most sensitive)
- **90d** - Monthly patterns (default)
- **180d** - Long-term trends (stable view)

Charts and Visualizations
--------------------------

1. Kingdom Breakdown
~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** Classified reads per NTC, stacked by superkingdom.

**How to read it:**

- Each bar = one NTC
- Height = total classified reads
- Colors = Bacteria (blue), Viruses (red), Eukaryota (green), Archaea (amber), Other (gray)
- X-axis = week number (W1, W2, etc.)
- Y-axis = read count

**What to look for:**

- Consistent kingdom composition → stable baselines
- Sudden spikes → potential contamination event
- New kingdoms appearing → new contamination source
- Viruses in NTC → significant concern (should be rare)

**Hover action:** Mouse over a bar to see detailed breakdown per sample.

2. Total Classified Reads
~~~~~~~~~~~~~~~~~~~~~~~~~~

**What it shows:** Total reads classified per NTC over time (scatter plot).

**How to read it:**

- Each dot = one NTC
- Y-position = total classified reads
- Red dashed line = 1,000 reads threshold
- Below threshold: acceptable baseline
- Above threshold: concerning (too many reads = contamination)

**What to look for:**

- Clusters above 1,000 reads → possible contamination batch
- Upward trend → worsening contamination over time
- One-off spikes → isolated incident (possibly handling error)
- Baseline consistency → good quality control

**Hover action:** Show sample ID, case ID, and date.

3. Recurring Taxa
~~~~~~~~~~~~~~~~~

**What it shows:** Line chart of organisms appearing in multiple NTCs.

**How to read it:**

- Each colored line = one organism
- Y-position = abundance (read count)
- X-axis = time (weeks)
- "×N" in legend = appears in N different NTCs

**What to look for:**

- Flat lines → stable low-level contamination (acceptable)
- Upward trends → worsening contamination (investigate)
- Recurring peaks → episodic source (check reagent batches)
- New organism appearing → new contamination source

**Hover action:** Show organism name, taxon ID, abundance, and date.

Contaminant Alerts Banner
==========================

If **Known Contaminants** exceed their alert threshold in any NTC:

- **Orange alert box** appears at top of page
- Lists each contaminating organism
- Shows which NTCs triggered the alert
- Includes alert threshold (min reads)
- **"Manage lists"** link to configure thresholds

Example alert:

.. code-block:: text

   ⚠️ Known contaminants detected in NTCs

   Escherichia coli · 3 cases · > 5 reads threshold
   Propionibacterium acnes · 1 case · > 3 reads threshold

This means you should investigate these NTCs and potentially retract or re-examine associated clinical samples.

Troubleshooting with NTC Trends
===============================

"Too many reads in NTCs"
------------------------

**Problem:** NTCs showing > 1,000 classified reads consistently.

**Causes:**

- Contaminated reagents (new kit/batch?)
- Lab environment contamination
- Cross-contamination during sample prep
- Sequencer contamination

**Action:**

1. Check reagent batch dates
2. Review lab notebook for unusual events
3. Inspect extraction equipment/workspace
4. Consider running positive controls to verify equipment function
5. Contact kit supplier if batch is new

"Sudden spike in one NTC"
-------------------------

**Problem:** One NTC shows very high reads, others are normal.

**Causes:**

- Handling error (dropped tube, air exposure)
- Sample mislabeling
- One-off contamination during prep
- Sequencer issue with that run

**Action:**

1. Review lab notes for that day
2. Check if other samples from same batch affected
3. If isolated: likely handling error (accept and move on)
4. If systematic: investigate batch or equipment

"Organism keeps appearing"
--------------------------

**Problem:** Same organism in multiple NTCs over weeks.

**Causes:**

- Persistent lab contamination (workspace, hood, tools)
- Recurring reagent contamination
- Environmental organism (dust, air)

**Action:**

1. Identify when contamination started
2. Review what changed around that time
3. Deep-clean lab workspace/equipment
4. Check reagent storage/handling
5. Consider running sequential controls to isolate source
6. Add to **Known Contaminants** list to track threshold

"New organism appearing"
------------------------

**Problem:** Organism never seen before appears in multiple NTCs.

**Causes:**

- New reagent batch contaminated
- Environmental change (new equipment, location moved)
- Lab staffing change (different handling technique)

**Action:**

1. Note when it started
2. Correlate with any lab changes
3. Add to **Known Contaminants** to monitor
4. Increase monitoring frequency
5. Investigate source

NTC Lists Page
==============

The **NTC Lists** page provides two management tools:

Ignored Taxa
------------

**Purpose:** Exclude organisms from NTC analysis entirely.

**When to use:**

- Known environmental contaminants (dust, water, air)
- Organisms you don't care about
- DNA/RNA extraction kit contaminants
- Organisms you've verified as benign

**Properties:**

- **Taxon** - Organism name
- **Kingdom** - Superkingdom classification
- **Taxon ID** - NCBI identifier
- **Reason** - Why it's ignored (editable)
- **Added by** - Which user added it
- **Date added** - When it was added

**Ignored taxa are:**

- Excluded from NTC Trends charts
- Not counted in statistics
- Not flagged as alerts

**Example:** *Staphylococcus aureus* on skin flora → ignored → won't trigger alerts

Known Contaminants
-------------------

**Purpose:** Track organisms that indicate problems.

**When to use:**

- Organisms that indicate workflow problems
- Contamination you want to actively monitor
- Organisms requiring investigation
- Taxa that should trigger alerts when detected

**Properties:**

- **Taxon** - Organism name
- **Kingdom** - Superkingdom
- **Taxon ID** - NCBI identifier
- **Alert threshold** - Minimum reads to trigger (editable)
- **Notes** - Context about the contamination
- **Added by** - Which user added it
- **Date added** - When it was added

**Known contaminants:**

- Appear on NTC Trends as line chart
- Trigger orange alert box if threshold exceeded
- Flag cases with amber warning
- Show on case list with warning indicator

**Example:** *Propionibacterium acnes* threshold=5 reads → If found with >5 reads, alerts appear

Adding to Lists
~~~~~~~~~~~~~~~

Both lists support adding organisms via NCBI taxon ID lookup:

1. Click **+ Add taxon**
2. Enter NCBI Taxon ID (e.g., 562 for *E. coli*)
3. Click **Look up** - retrieves name and kingdom
4. (For Known Contaminants) Set alert threshold in reads
5. (Optional) Add notes explaining why
6. Click **Add**

Editing Lists
~~~~~~~~~~~~~

**Ignored Taxa:**

- Hover over "Reason" cell → click edit icon
- Edit the reason (why it's ignored)
- Press Enter to save or Escape to cancel

**Known Contaminants:**

- Hover over "Alert threshold" cell → click edit icon
- Change the minimum reads trigger
- Press Enter to save or Escape to cancel

Removing from Lists
~~~~~~~~~~~~~~~~~~~

**Admin role only** - Click "Remove" button to delete.

After removal:

- Organism no longer tracked
- Previous alerts clear
- Future occurrences treated as new

**Note:** Only admins can remove; writers can add and edit.

Best Practices
==============

Setup
-----

1. **Start baseline:** Run 5–10 NTCs over a week
2. **Establish normal:** What organisms appear regularly at low levels?
3. **Create ignorelist:** Add known environmental contaminants
4. **Create known contaminants:** Add any organisms that indicate problems

Monitoring
----------

1. **Check daily:** Look at recent NTCs
2. **Review trends:** Use the Trends page weekly
3. **Set thresholds:** Base on your lab's typical values
4. **Document changes:** Add notes when you make list changes

Response
--------

1. **Recurring contamination:** Deep-clean affected equipment
2. **Batch contamination:** Contact supplier, test new batch
3. **Persistent issue:** Involves senior staff, may need procedure review
4. **New organism:** Add to Known Contaminants, monitor closely

Documentation
--------------

- Document all contamination events in lab notebook
- Record when you clean/replace equipment
- Note any procedural changes
- Track batch numbers of reagents
- Keep history of list changes (why items added/removed)

Integration with Case Review
=============================

NTC Trends and Known Contaminants inform clinical interpretation:

Case Warning Indicators
------------------------

On the **Case List**, cases containing known contaminants show:

- 🟡 **Amber pill** - Known contaminant detected in sample
- Clickable pill links to contamination details
- Reviewer should note if contamination is true positive or artifact

During Sample Review
---------------------

**When reviewing a sample:**

1. Check if sample contains known contaminants
2. Check if contamination co-occurs with NTC contamination
3. If contamination appears in both: likely artifact
4. If contamination in sample only: likely true organism

**Example scenario:**

- *E. coli* appears in patient sample
- *E. coli* also found in NTC from same batch
- Conclusion: Likely contamination artifact, interpret with caution

Technical Details
=================

Data Sources
------------

NTC Trends uses:

- **Negative control samples** from the ``samples`` collection
- Filter: ``type='negative_ctrl'``
- **Taxonomy data** from samples' ``profiles`` collection
- **Known contaminants list** from ``ntc_known_contaminants`` collection

Calculations
------------

**Recurring taxa** require:

- Present in ≥ (min case %) of NTCs in window
- Abundance > (min reads threshold)
- Classified by Kraken2 classifier
- Superkingdom not restricted

**Kingdom breakdown** shows:

- All classified reads per superkingdom
- Host organisms excluded
- Structural organisms excluded

**Read count chart** displays:

- Total classified reads = all reads assigned to any organism
- Excludes unclassified and host reads

Caching
-------

- Contaminant alert results cached for 1 hour
- Cache invalidated when:
  - New case ingested
  - Known Contaminants list changed
  - Ignorelist changed

Time Window
-----------

- 30-day window: ±1 day padding (covers 32 days of data)
- 90-day window: ±1 day padding
- 180-day window: ±1 day padding
- Bounding prevents full database scans

Alerts and Monitoring
=====================

Types of Alerts
---------------

1. **Contaminant Alert** (orange banner)
   - Known contaminant found above threshold
   - Appears on Trends page
   - Links to management page

2. **Case Warning** (amber pill)
   - Case contains known contaminated sample
   - Visible on case list
   - Reviewer can note in case

3. **Trend Alert** (visual inspection)
   - Upward trend in charts
   - Spikes or clusters
   - New organisms appearing

Setting Up Monitoring
---------------------

1. **Regular review:** Check Trends page daily
2. **Set thresholds:** Based on your baselines
3. **Establish triggers:** When to investigate vs. accept
4. **Document decisions:** Why items are on lists

FAQ
===

**Q: Should all environmental organisms be ignored?**

A: Not necessarily. Ignore truly ubiquitous background (dust, water organisms). Track lab-specific contaminants as Known Contaminants to monitor trends.

**Q: How do I know if contamination is from reagents vs. lab environment?**

A: Reagent contamination appears in all NTCs using that batch. Environmental appears sporadically. Compare across batches.

**Q: Can I export NTC data?**

A: Not currently via UI. Contact admin for database access if needed.

**Q: How often should I review NTC trends?**

A: Daily during normal operations, weekly for trend review, immediately if alerts appear.

**Q: What read count is "too much" for an NTC?**

A: Baseline depends on your workflow. Typical: 10–100 reads. Concerning: > 1,000 reads. Very concerning: > 5,000 reads.

Next Steps
==========

- Visit **NTC Trends** to see current contamination patterns
- Review **NTC Lists** to set up monitoring for your lab
- Add known contaminants relevant to your workflow
- Check trends weekly as part of quality assurance routine

See Also
========

- :doc:`outbreak-detection` - Similar monitoring for clinical samples
- :doc:`cases-and-samples` - Reviewing individual cases