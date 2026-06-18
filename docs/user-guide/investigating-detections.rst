==========================
Investigating detections
==========================

Once you have a sample open, three pieces of UI help you decide whether a
detected organism is real and what is known about it: the **taxonomy
table**, the **metaval details** view (when metaval was run), and the
**BV-BRC enrichments** on the taxon detail page.

Taxonomy table
==============

The main exploration surface, available on both case and sample views.
One row per detected organism, columns: rank, name, abundance (read
count), %abundance (share of classified reads).

Search
   Case-insensitive partial match against organism names. ``species:1234``
   searches by NCBI taxon id.

Kingdom filter
   *All / Bacteria / Archaea / Viruses / Eukaryota / Unclassified*. Your
   default selection is stored in your preferences (see
   :doc:`administration`).

Rank filter
   *All / Genus / Species / Family / Order / Class / Phylum / No rank /
   Serotype*. Filters can be combined.

Switching classifier tabs swaps the underlying profile while keeping
your filters. Use this to spot-check consistency — an organism present
across classifiers at similar abundance is a stronger signal than one
that appears in only one.

Clicking an organism name opens the **Taxon Detail** page, which adds
the full taxonomy lineage, NCBI taxon id, clinical notes (if curated),
the metaval verification status, and the BV-BRC enrichments described
below.

Metaval validation
==================

`metaval <https://github.com/genomic-medicine-sweden/metaval>`_ runs on
top of taxonomic profiling and produces per-organism read-level
evidence: an IGV coverage plot against a reference genome and a BLASTN
hit table. When metaval results are included at ingest, organisms it
has examined get a coloured pill in the taxonomy table.

Pill states:

- **Verified** — both IGV coverage and a BLASTN match are present.
- **IGV only** — coverage available, no BLASTN result.
- **BLAST only** — BLASTN match available, no IGV.
- (no pill) — metaval did not examine this taxon.

Clicking the pill opens the **Metaval Details** page for the organism.

IGV coverage
   An embedded igv.js viewer showing read pile-up against the reference.
   Coverage depth is plotted per position; gaps appear where no reads
   mapped.

BLASTN results
   A table of the top BLAST hits — percent identity, alignment length,
   e-value, subject description.

The interpretation of these is a clinical judgement and not something
the app tries to make for you — but evenness of coverage and identity
percentage are the two numbers most reviewers anchor on.

If a case has no metaval pills at all on any organism, the metaval
directory was not passed at ingest. Re-ingest with ``--metaval-igv``
(see :doc:`loading-data`).

BV-BRC enrichments
==================

The **Taxon Detail** page fetches additional context from the
`Bacterial and Viral Bioinformatics Resource Center
<https://www.bv-brc.org>`_, a public NIAID-funded reference database.
Results are cached per taxon for 24 hours; if BV-BRC is unreachable the
section shows an empty state rather than an error.

Two subsections appear:

Sequenced genomes
-----------------

Available for both bacterial and viral taxa.

- **Total genome count** — How many sequenced genomes BV-BRC has for
  this organism. A proxy for how well-studied the pathogen is.
- **Top isolation sources** — Where isolates were collected (blood,
  sputum, soil, clinical specimen…). A read on the organism's niche.
- **Geographic distribution** — Top contributing countries. Regional
  context for whether the organism is common here.
- **AMR genome counts** (bacteria) — How many genomes carry documented
  resistance to specific antibiotics, sourced from BV-BRC's curated
  AMR metadata.

AMR genes and virulence factors
-------------------------------

Bacterial taxa only. For viral taxa the section is shown but displays
"No data in BV-BRC" — these reference databases don't cover viruses.

- **AMR genes** — Genes documented to confer resistance, from CARD and
  NDARO. Shows gene name, resistance mechanism, source. Deduplicated
  across strains.
- **Virulence factors** — From VFDB and Victors. Shows gene name, gene
  product, source.
- **AMR phenotype summary** — Aggregate experimentally-determined
  resistance counts (resistant vs susceptible genomes) per antibiotic,
  pulled from BV-BRC genome metadata. Distinct from gene-level
  prediction.

What the BV-BRC section is and isn't
------------------------------------

It is **species-level reference context**: what is known about the
species globally. It is **not** sample-specific — the presence of an
AMR gene in BV-BRC for the species does not mean the strain detected
in your sample carries that gene. Treat it as risk-stratification
background while waiting for susceptibility testing.

BV-BRC coverage is best for well-studied pathogens (*M. tuberculosis*,
*E. coli*, influenza…); rare organisms may return few or no genomes.
Aggregations are capped at 1 000 genomes per query.

See also
========

- :doc:`reviewing-cases` — opening the case and sample that gets you
  here
- :doc:`monitoring` — cross-case patterns for the same organism
