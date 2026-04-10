===================
Taxonomy Browser
===================

The taxonomy table is your main tool for exploring taxonomic results. This guide covers advanced features for finding and analyzing organisms.

Quick navigation
================

**On the taxonomy table:**

1. **Search box** - Type organism names
2. **Kingdom dropdown** - Filter to superkingdoms
3. **Rank dropdown** - Filter to specific taxonomic levels
4. **Columns** - Name, Abundance, %Abundance

Searching organisms
===================

The search feature uses partial matching and is case-insensitive.

**Examples:**
- Search "Escherichia" → finds "Escherichia coli", "Escherichia fergusonii", etc.
- Search "phage" → finds all phage entries across any organism name
- Search "virus" → finds all entries with "virus" in the name
- Search "species:2562" → searches by NCBI taxon ID

Search tips
-----------

- **Exact matches** - Search for the full organism name for best results
- **Common names** - Works with both scientific and common names
- **Prefix search** - Type the start of a name to narrow results
- **Clear search** - Leave the box empty to see all organisms

Filtering by kingdom
====================

Use the **Kingdom** dropdown to focus on specific domains:

- **All** - Show everything
- **Bacteria** - Bacterial organisms (superkingdom Bacteria)
- **Archaea** - Archaeal organisms
- **Viruses** - Viral organisms
- **Eukaryota** - Eukaryotic organisms (fungi, protists, plants, animals)
- **Unclassified** - Organisms not assigned to a kingdom

**Common use cases:**
- Filter to **Viruses** when looking for viral agents
- Filter to **Bacteria** or **Archaea** for standard clinical samples
- Check **Unclassified** for low-confidence assignments

Filtering by rank
=================

Use the **Rank** dropdown to show only specific taxonomic levels:

- **All** - Show all ranks
- **Genus** - Group organisms by genus
- **Species** - Show species-level assignments
- **Family**, **Order**, **Class**, **Phylum** - Higher-level groupings
- **No rank** - Entries without a specific rank assignment
- **Serotype** - Subtype classifications (common for viruses)

**Common patterns:**
- Start with **Genus** to see major organisms
- Switch to **Species** for specific identifications
- Use **No rank** to find entries needing curator attention

Combining filters
=================

Filters work together. For example:

- Kingdom: **Viruses**, Rank: **Species**
  → Shows all detected viral species

- Kingdom: **Bacteria**, Rank: **Genus**
  → Shows bacterial genera

- Kingdom: **Unclassified**, Leave Rank as **All**
  → Shows all unclassified entries (potential QC issues)

Abundance interpretation
=========================

Two columns show organism abundance:

**Abundance (read count)**
  The number of sequencing reads assigned to this organism. Higher = more genetic material detected.

**%Abundance (percentage)**
  The percentage of all classified reads assigned to this organism. Useful for comparing across samples with different total read counts.

**Interpretation:**
- > 1% → Likely significant organism
- 0.1–1% → Might be contamination or low-abundance colonizer
- < 0.1% → Possibly technical noise or very rare organism

**Context matters:**
- What's expected in a negative control?
- Is this organism clinically relevant?
- Does it appear consistently across replicates?

Viewing taxon details
=====================

Click on any organism name to open the **Taxon Detail** page.

**Shows:**
- Full taxonomic lineage (kingdom → species)
- NCBI taxon ID
- Rank and superkingdom
- Abundance information
- Metaval verification status (if available)

**Metadata:**
- Clinical notes (if added by curators)
- Links to NCBI resources
- Related taxa

**If metaval available:**
- IGV coverage visualization
- BLASTN results
- Organism details from reference genomes

Interpreting results across classifiers
========================================

Each sample typically has results from multiple classifiers (Kraken2, Centrifuge, DIAMOND). Consistency is a good sign.

**Compare results:**

1. Go to the taxonomy table
2. Switch between classifier tabs
3. Look for:
   - Same organisms appearing in all classifiers
   - Agreement on relative abundances
   - Differences might indicate:
     - Database differences
     - Reference bias
     - Real signal vs. contamination

**High confidence** - Same organism in all classifiers at similar abundance

**Moderate confidence** - Present in 2 out of 3 classifiers

**Low confidence** - Only in one classifier, or very different abundances

Filtering negative controls
============================

When looking at negative control samples:

1. **Filter to see abundant taxa** - Look for unexpected organisms
2. **Compare to clinical samples** - What shouldn't be there?
3. **Check across multiple controls** - Is contamination consistent?

Negative control interpretation:
- Empty (0 organisms) - Perfect, no contamination
- Few organisms, low abundance - Acceptable background
- Many organisms, high abundance - Possible contamination batch
- Specific organism shared with clinical sample - Might be contamination of that sample

Case-control comparison workflow
=================================

To investigate potential contamination or cross-sample findings:

1. Go to the **Case** view
2. View all samples
3. **Compare clinical samples:**
   - Do they share unexpected organisms?
   - Are controls clean?
   - Is there a pattern?
4. **Check metaval** - Are shared organisms verified?
5. **Add notes** - Document your findings for other reviewers

Performance considerations
===========================

For samples with very large numbers of organisms (> 10,000 taxa):

- **Use filters** - Narrow by kingdom or rank first
- **Search specifically** - Rather than scrolling
- **Sort by abundance** - Top organisms usually most relevant

Tips for clinical interpretation
=================================

1. **Consider context** - What's the clinical question?
2. **Check positive controls** - Are expected organisms present?
3. **Review negatives** - Are contaminants absent?
4. **Verify abundant taxa** - Use metaval or manual review
5. **Document findings** - Use case notes for other reviewers
6. **Cross-reference** - Is the organism clinically known?

Next steps
==========

- :doc:`metaval-integration` - Verify organisms with metaval results
- :doc:`outbreak-detection` - Monitor for concerning patterns across cases
- :doc:`cases-and-samples` - Return to cases overview
