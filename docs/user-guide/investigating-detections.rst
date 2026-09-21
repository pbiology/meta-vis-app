==========================
Investigating detections
==========================

Once you have a sample open, four pieces of UI help you decide whether a
detected organism is real and what is known about it: the **taxonomy
table**, the **related taxa** tree on the taxon detail page, the
**metaval details** view (when metaval was run), and the **BV-BRC
enrichments**.

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

Reads and percentages
---------------------

Classifier counts are **direct**: reads assigned to exactly that taxon,
never to it plus everything below it. The ``root`` row is therefore only
the reads that could not be placed any deeper — it is not a total for
the sample, and rows must not be added up.

Two figures sit above the table:

**Total classified**
   Every read the classifier placed on some taxon. Taken from the run's
   QC metrics when they carry it, otherwise summed from the profile.

**Non-host reads**
   The same total minus the reads assigned to *Homo sapiens*. This is
   the denominator behind every **%abundance** in the table, so a
   percentage tells you an organism's share of the non-host material.

Host reads that a classifier stopped at a parent taxon — *Homo*,
*Hominidae* — cannot be told apart from genuine signal without a
lineage, so they are not subtracted. In practice Kraken2 assigns human
reads to *Homo sapiens* itself, and the difference is negligible.

TRANA/Emu profiles carry relative abundances rather than read counts, so
both figures show ``—``.

.. note::

   An amber banner above the table means the QC metrics report fewer
   classified reads than the profile assigns to host alone. The two
   disagree about what was sequenced, so the counts and percentages for
   that classifier are unreliable — check the run's QC output before
   reading anything into them, and re-ingest if the bundle was
   incomplete.

Related taxa in sample and controls
===================================

The NTC column in the taxonomy table compares **exact taxon ids**: a
taxon counts as present in a control only when the control carries that
same id. Classifiers do not oblige. The same organism can land on a
sibling strain, on a neighbouring species, or stop at a higher rank,
depending on read length, database contents and how much of the genome
was covered. Compared on ids alone, an organism that is plainly in your
control looks absent from it.

The **Related taxa in sample and controls** section on the taxon detail
page lays the neighbourhood out instead. It shows every taxon under the
clicked organism's **genus** that has signal in this sample or in any
negative control of the same run, as a tree, one column per sample.

A real example — clicking a *Streptomyces* strain with two reads::

   Streptomyces [genus]              sample: 0 / 2      NTC: 880 / 12,405
     S. xinghaiensis [species]       sample: 0 / 2      NTC: 0
       S. xinghaiensis S187 [strain] sample: 2 / 2      NTC: 0
     unclassified Streptomyces       sample: 0          NTC: 406 / 9,067
       Streptomyces sp. Y1           sample: 0          NTC: 5,624

On exact ids the strain is unique to the sample. In context, the control
carries 12 405 *Streptomyces* reads spread over other members of the
genus, and the two reads are almost certainly the same contamination.

Reading the tree
----------------

Two numbers per cell
   Classifier counts are **direct**: reads assigned to exactly that
   taxon, not to its children. Each cell therefore shows the **clade
   total** (the taxon plus everything below it) and, on rows that have
   children, the **direct** count as well. Do not add rows up — the
   parent already includes them.

Reads per million
   Shown under each value, relative to all reads that classifier
   processed for that sample. Controls are usually sequenced far
   shallower than samples, so raw counts are not comparable between
   columns; rpm is.

Greyed-out rows
   A taxon with no reads of its own, present only to connect the taxa
   below it to the genus.

``N more taxa``
   Siblings beyond the ten strongest are folded into one row carrying
   their combined signal; click it to show them. **Anything with reads
   in the sample is always shown**, however weak, as is the organism you
   clicked.

``includes retired taxid …``
   NCBI merged that id into this taxon; the reads have been added
   together. Classifier databases are built on older taxonomy snapshots,
   so retired ids are common in real profiles.

Amber notice
   Taxa in the run that could not be placed in the taxonomy at all —
   deleted ids, or ids the loaded reference does not have. They may
   belong to the group you are looking at, so they are listed rather
   than dropped.

Columns are the sample first, then the negative controls of the **same
pipeline run with the same nucleic acid** — the only controls that say
anything about this run's contamination. Positive controls are not
included. A control with no profile for the selected classifier shows
``—``, which means "no data", not zero.

What it does and does not answer
--------------------------------

It answers "is this organism's *neighbourhood* in my controls?" and
leaves the judgement to you — nothing here re-labels a detection as
contamination.

Two limits worth knowing:

- **It stops at the genus.** Organisms that look alike but sit in
  different genera — *E. coli* and *Shigella*, the *B. cereus* group —
  will not appear in each other's trees.
- **It needs taxonomy lineages.** If the section reports that the
  reference must be reloaded, run ``load_taxonomy.py`` (see
  :doc:`loading-data`).

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
