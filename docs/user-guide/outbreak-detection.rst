===================
Outbreak Detection
===================

meta-vis-app continuously monitors for concerning viral taxa appearing across multiple cases. This feature helps identify potential outbreak situations early.

How it works
============

The app tracks viral organisms across cases and flags those appearing in multiple samples within a time window:

1. **Window** - Customizable time range (7, 14, or 30 days)
2. **Detection** - Identifies viral taxa appearing in 2+ cases
3. **Filtering** - Only includes:
   - Organisms with > 1 classified read
   - Viral superkingdom (Viruses)
   - Species/no-rank/serotype level
   - Taxa not on the ignorelist
4. **Display** - Shows matching cases and sample details
5. **Caching** - Results cached for 1 hour, refreshed on new ingestion

Accessing alerts
================

**Three places to see outbreak alerts:**

1. **Alerts page** - Dedicated view of all current alerts
   - Sidebar → Alerts
   - Shows all flagged taxa with case counts
   - Customize time window and review ignorelist

2. **Case list** - Amber warning indicator on cases with flagged taxa
   - Quick visual identification of concerning cases
   - Click to view details

3. **Taxonomy table** - Amber pill on outbreak-flagged organisms
   - Shows directly on the organism row
   - Context-aware (only shows if case is part of outbreak)

Alerts page
===========

The **Alerts** page is your dashboard for outbreak monitoring.

**Top section:**
- Time window selector (7, 14, 30 days)
- Alert summary (total taxa flagged, total affected cases)

**Main table:**
- **Taxon** - Organism name
- **Superkingdom** - Always "Viruses"
- **Cases** - Number of cases containing this taxon
- **Samples** - Total samples affected
- **Latest** - Most recent case with this organism
- **Actions** - View details, add to ignorelist

**Clicking a taxon row:**
- Opens taxon details
- Shows all cases with this organism
- Shows sample-level data
- Links to individual cases

Time window settings
====================

Switch the time window to change which cases are included:

- **7-day window** - Recent 2-week span (covers a few days of testing)
- **14-day window** - Recent month (better for weekly testing patterns)
- **30-day window** - Full month (for longer-term tracking)

**Interpretation:**
- Narrow window (7d) - Focus on very recent alerts
- Wide window (30d) - Catch slowly emerging patterns

Ignorelist management
=====================

The **ignorelist** excludes taxa from outbreak detection. Common reasons:

- Known environmental contaminants
- Ubiquitous organisms with little clinical significance
- Testing artifacts appearing across sites

**Adding to ignorelist:**
1. Go to Alerts page
2. Click the organism's "Add to ignorelist" button
3. Optionally enter a reason (e.g., "environmental contaminant")
4. Confirm

**Managing ignorelist:**
- Admins can remove entries
- Writers can add entries
- Search the list to check if a taxon is already ignored
- Review reasons regularly to see why entries were added

**Best practices:**
- Document why you're ignoring something
- Review ignorelist quarterly
- Don't ignore clinically relevant organisms

Alert indicators
================

**On the case list:**
- Amber warning icon - Case contains outbreak-flagged taxa
- Hover to see which organisms are flagged
- Click to go to case details

**On the taxonomy table:**
- Amber pill next to organism name
- Click to view outbreak context
- Shows other cases with same organism

**On the Alerts page:**
- Full list of current alerts
- Customizable view and filters
- Detailed case information

Interpreting outbreak alerts
=============================

**Step 1: Assess the alert**

- Is the organism clinically relevant?
- How many cases are affected?
- What's the time span?

**Step 2: Review the organisms**

- Go to Alerts page
- Click the taxon
- Check individual cases and samples
- Look for patterns:
  - Geographic clustering?
  - Same department?
  - Similar symptoms?

**Step 3: Check validation**

- Do metaval results confirm presence?
- Consistent across classifiers?
- High abundance or rare?

**Step 4: Decide on action**

- **False positive** - Add to ignorelist
- **Real outbreak signal** - Escalate to infection control
- **Uncertain** - Monitor over next few days

**Example outbreak assessment:**

.. code-block:: text

   Alert: Monkeypox virus in 5 cases (14-day window)
   
   Case 1: 2% abundance, Kraken2+Centrifuge, metaval verified
   Case 2: 1.8% abundance, all classifiers, metaval verified
   Case 3: 0.5% abundance, Kraken2 only, no metaval
   Case 4: 3% abundance, all classifiers, metaval verified
   Case 5: 0.1% abundance, Kraken2 only, no metaval
   
   Assessment:
   - 4 high-confidence cases (1, 2, 4) at consistent abundance
   - 1 low-confidence case (3, 5) at very low abundance
   - Consistent detection across classifiers
   - metaval confirms 3/5
   → PROBABLE OUTBREAK: Escalate to infection control

Monitoring workflow
===================

**Daily:**
- Check Alerts page
- Review new alerts in 7-day window
- Note any unusual patterns

**Weekly:**
- Review 14-day trends
- Check for geographic/department clustering
- Update ignorelist as needed

**Monthly:**
- Full 30-day review
- Identify sustained alerts
- Review ignorelist for stale entries

Integration with infection control
==================================

**Recommended workflow:**

1. meta-vis-app flags outbreak potential
2. Clinician reviews metaval evidence
3. If high confidence:
   a. Documents findings in case notes
   b. Escalates to infection control
   c. Requests epidemiologic investigation
4. Infection control:
   a. Interviews patients
   b. Reviews timeline
   c. Implements measures if confirmed
5. Follow-up monitoring in next 7–30 days

**Communication:**
- Document alert findings in case notes
- Flag concerns clearly for infection control team
- Include organism name, confidence, and metaval evidence
- Provide direct comparison links to affected cases

Limitations and caveats
=======================

**Outbreak detection finds patterns, not proof of outbreaks.**

Limitations:
- Only tracks by organism, not by patient or location
- Relies on presence/absence, not phenotype
- No access to patient metadata (location, dept, etc.)
- Detection thresholds might miss emerging patterns or flag false alarms

What could cause false positives:
- Environmental organism widely present in samples
- Technical contamination batch across samples
- Migration of samples from same source/reagent batch
- Organism name variations in databases

What could cause false negatives:
- Very rare organisms missed by alert thresholds
- Organisms on the ignorelist
- Cases without order dates (excluded from analysis)
- Multi-step infections with different timing

**Always investigate alerts manually before escalating.**

Performance and caching
=======================

Alerts are cached for efficiency:

- **Query time** - Bounded by time window, not total case count
- **Cache lifetime** - 1 hour
- **Invalidation** - Refreshed automatically on new case ingest or ignorelist changes

For large deployments (500+ cases/month):
- 30-day window queries ~1,000 cases
- Still completes in seconds
- Designed to scale efficiently

Next steps
==========

- :doc:`cases-and-samples` - Review individual cases
- :doc:`metaval-integration` - Validate organisms
- :doc:`user-roles` - User permissions for alerts
