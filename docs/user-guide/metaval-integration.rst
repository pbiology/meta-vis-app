=====================
Metaval Integration
=====================

When metaval results are available, they provide experimental validation for detected organisms.

What metaval does
==================

`metaval <https://github.com/genomic-medicine-sweden/metaval>`_ performs validation on top of taxonomic profiling:

- **Organism extraction** - Pulls reads assigned to each organism
- **Read mapping** - Maps reads to reference genomes
- **IGV visualization** - Creates coverage plots
- **BLAST alignment** - Validates sequence identity
- **Consensus calling** - Generates consensus sequences

The result: organism-level evidence that confirms metagenomic assignments.

Viewing metaval results
=======================

On the **Taxonomy Table**, verified organisms have a blue pill:

- **Verified** - Full IGV + BLAST evidence
- **IGV only** - Coverage visualization available
- **BLAST only** - Sequence match available
- **Unverified** - Detected but not validated by metaval

Click the pill to open the **Metaval Details** page.

Metaval details page
====================

Shows comprehensive validation data for an organism:

**Organism info:**
- Full taxonomy lineage
- NCBI taxon ID
- Abundance in the sample
- Classifier that detected it

**IGV Coverage**
  Interactive visualization of read mapping to the reference genome.

  - **Coverage depth** - How many reads map at each position
  - **Read alignment** - Paired-end reads shown on forward/reverse strands
  - **Gaps** - Uncovered regions indicate incomplete recovery

  **Interpreting coverage:**
  - Even coverage (few gaps) → Likely true presence
  - Patchy coverage (many gaps) → Might be partial genome or contamination
  - Very low coverage → Questionable presence

**BLASTN Results**
  Sequence similarity against the reference:

  - **% Identity** - How similar the query and subject sequences are
  - **Alignment length** - How much of the reference is covered
  - **E-value** - Statistical significance

  **Interpreting BLAST:**
  - > 98% identity + full-length match → High confidence
  - 95–98% identity → Likely same species, possible strain variation
  - < 95% identity → Different species, watch for contamination

**Consensus sequence**
  The derived consensus sequence for this organism. Can be used for:
  - Further phylogenetic analysis
  - Comparison to databases
  - Detection of resistance genes or virulence factors

When to trust metaval results
=============================

**High confidence (trust the result):**
- Abundant organism (> 1% of reads)
- Even IGV coverage across reference
- BLAST identity > 98%
- Appears in positive controls if relevant
- Clinically expected organism

**Moderate confidence (investigate further):**
- Moderate abundance (0.1–1%)
- Patchy IGV coverage
- BLAST identity 95–98%
- Not in negative controls
- Clinically plausible

**Low confidence (treat with suspicion):**
- Very rare organism (< 0.1%)
- Minimal IGV coverage
- BLAST identity < 95% or low alignment length
- Unexpectedly appears in multiple unrelated samples
- No clinical relevance

Troubleshooting metaval
=======================

**Missing IGV visualization**
  - IGV files are uploaded during ingest
  - Might indicate ingest failure
  - Check ingest logs

**Missing BLAST results**
  - metaval might not have tested this organism
  - Check metaval output directory
  - Very low-abundance organisms might be skipped

**No metaval results at all**
  - metaval output directory wasn't provided during ingest
  - Re-ingest the case with ``--metaval-igv`` flag
  - Or run metaval separately and reingest

Using metaval for clinical interpretation
==========================================

**Workflow for organism validation:**

1. Find organism in taxonomy table
2. Click organism name → Taxon Detail page
3. Check if metaval pill shows "Verified"
4. Click pill → Metaval Details page
5. Review IGV coverage and BLAST results
6. Decide: confirmed, probable, or artifact?
7. Document your interpretation in case notes

**Checklist for confident identification:**
- [ ] Organism appears in expected classifier(s)
- [ ] Abundant enough to be biologically significant
- [ ] IGV coverage is reasonably even
- [ ] BLAST shows > 95% identity
- [ ] Not found in negative controls
- [ ] Clinically relevant or expected
- [ ] No obvious contamination patterns

Comparing across classifiers and validation
============================================

Example: Multiple classifiers + metaval

.. code-block:: text

   Organism: Influenza A virus

   Kraken2:     Present, 5% abundance
   Centrifuge:  Present, 4.8% abundance
   DIAMOND:     Present, 5.2% abundance
   metaval:     Verified, 98% identity, even coverage

   Confidence: Very high → Report as confirmed

Versus:

.. code-block:: text

   Organism: Mystery bacterium (genus only)

   Kraken2:     Present, 0.02% abundance
   Centrifuge:  Not detected
   DIAMOND:     Not detected
   metaval:     No IGV, poor BLAST match (87% identity)

   Confidence: Very low → Likely artifact

Reporting findings
==================

When documenting verified organisms:

- **Method** - Which classifier(s) detected it?
- **Abundance** - What % of reads?
- **Confidence** - High/moderate/low
- **Evidence** - metaval results, appearance across classifiers, etc.
- **Clinical significance** - Is this organism concerning?

Example case note:

.. code-block:: text

   Influenza A virus (H3N2) confirmed:
   - Detected by all classifiers (4–5% abundance)
   - metaval IGV shows even genome coverage
   - BLAST confirms 99% identity
   - Clinically relevant for respiratory infection
   → HIGH CONFIDENCE RESULT

Next steps
==========

- :doc:`cases-and-samples` - Back to cases
- :doc:`taxonomy-browser` - Advanced searching
- :doc:`outbreak-detection` - Track concerning patterns
