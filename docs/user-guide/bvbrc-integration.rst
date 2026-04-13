====================
BV-BRC Resources
====================

The Taxon Detail page automatically enriches organism entries with data from the
`Bacterial and Viral Bioinformatics Resource Center (BV-BRC) <https://www.bv-brc.org>`_,
a public NIAID-funded database that integrates genomic, epidemiological, and clinical data
for bacterial and viral pathogens.

What it provides
================

BV-BRC data is fetched on demand when a taxon is opened and displayed in two subsections.

Sequenced genomes
-----------------

Available for both bacterial and viral taxa.

- **Total genome count** — How many sequenced genomes for this organism are archived in BV-BRC.
  A high count indicates a well-studied pathogen with broad global surveillance.

- **Top isolation sources** — Where isolates were collected from (e.g., blood, sputum, soil,
  clinical specimen). This gives a quick read on the organism's ecological niche and whether
  it is primarily a human pathogen, environmental organism, or both.

- **Geographic distribution** — Countries contributing the most sequenced genomes.
  Useful for contextualising whether a detected organism is common in your region.

- **AMR genome counts** — For bacterial taxa, how many genomes in BV-BRC carry documented
  resistance to specific antibiotics. This is derived from BV-BRC's curated AMR metadata
  per genome, not from computational prediction on the detected reads.

AMR genes and virulence factors (bacteria only)
-----------------------------------------------

For bacterial taxa, BV-BRC provides gene-level data from curated reference databases.
For viral taxa, where these databases do not apply, the specialty genes section is still
shown but displays "No data in BV-BRC" — no gene tables are rendered.

**AMR genes**
  Genes documented to confer antibiotic resistance, sourced from:

  - `CARD <https://card.mcmaster.ca>`_ (Comprehensive Antibiotic Resistance Database)
  - `NDARO <https://www.ncbi.nlm.nih.gov/pathogens/antimicrobial-resistance/>`_ (NCBI Pathogen AMR)

  The table shows gene name, resistance mechanism (e.g., *target alteration*, *efflux*),
  and the source database. Genes are deduplicated across strains.

**Virulence factors**
  Genes associated with pathogenicity, sourced from:

  - `VFDB <http://www.mgc.ac.cn/VFs/>`_ (Virulence Factor Database)
  - Victors database

  The table shows gene name, gene product description, and source database.

**AMR phenotype summary**
  An aggregate view of experimentally determined resistance phenotypes across all sequenced
  genomes for this taxon in BV-BRC. Columns show the number of genomes classified as
  *resistant* or *susceptible* for each antibiotic.

  This is distinct from computational AMR gene prediction — it reflects phenotypic
  susceptibility testing results recorded in BV-BRC's genome metadata.

Interpreting the data
=====================

**Genome count and isolation sources**
  A pathogen detected in a metagenomic run that has thousands of sequenced genomes and
  predominantly human/clinical isolation sources warrants more attention than one with
  few genomes and only environmental isolates. This context does not affect the confidence
  of the metagenomics detection itself — it is epidemiological background information.

**AMR genes**
  The presence of a known AMR gene in BV-BRC means the gene has been documented in at
  least one sequenced strain of this species. It does not mean the specific isolate
  detected in your sample carries that gene. Treat this as a risk signal: certain species
  are known to harbour resistance genes that clinicians should be aware of.

**AMR phenotypes (resistant/susceptible counts)**
  A high proportion of resistant genomes relative to susceptible ones (e.g., 80 resistant /
  5 susceptible for Isoniazid in *Mycobacterium tuberculosis*) reflects the known resistance
  landscape for that antibiotic in that species. Use this to anticipate likely resistance
  profiles when waiting for susceptibility testing results.

Limitations
===========

- **Coverage** — BV-BRC data is most comprehensive for well-studied pathogens (e.g.,
  *M. tuberculosis*, *E. coli*, influenza). Rare or recently described organisms may return
  few or no genomes.

- **Caching** — Data is cached for 24 hours per taxon. If you open the same taxon page
  within 24 hours, the previously fetched BV-BRC data is served from cache without a new
  API call. If BV-BRC is unavailable, the section shows an empty state rather than an
  error; no action is required.

- **Not sample-specific** — All BV-BRC data is species-level context. It describes what is
  known about the species globally, not what is present in the patient sample.

- **Viral taxa** — Genome summary data is available for viruses. The specialty genes
  section is shown for all taxa, but displays "No data in BV-BRC" for viral organisms
  because AMR gene and virulence factor databases cover bacteria only.

- **Genome limit** — The backend fetches up to 1 000 genomes per query for aggregation.
  For very large species (e.g., *E. coli*), isolation source and country distributions
  reflect a representative subset rather than the complete BV-BRC collection.

Next steps
==========

- :doc:`taxonomy-browser` — Search and explore detected organisms
- :doc:`metaval-integration` — Validate organisms with IGV coverage and BLASTN
- :doc:`outbreak-detection` — Track patterns across cases
