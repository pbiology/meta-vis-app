# Technical debt

## MultiQC / TAXPASTA sample name normalisation
**Filed:** 2024-03-28  
**Location:** `backend/app/ingestor/multiqc_reader.py`, `backend/app/ingestor/taxpasta_reader.py`

### Problem
taxprofiler appends classifier and database suffixes to sample names in its output files,
meaning the sample name `PE-04-28` appears as:
- `PE-04-28_k2_pluspf.kraken2.kraken2.report` in TAXPASTA column headers
- `PE-04-28_k2_pluspf` in MultiQC kraken keys
- `PE-04-28_1_raw_1` / `PE-04-28_1_raw_2` in MultiQC FastQC keys
- `PE-04-28_1` in MultiQC fastp and bowtie2 keys

The current ingestor works around this with string splitting and prefix matching,
which is fragile if taxprofiler changes its naming conventions.

### Ideal solution
Enforce clean sample names in the taxprofiler sample sheet so that the canonical
sample name propagates consistently through all pipeline outputs. The POST payload
would then supply a single `sample_name` field used as-is across all readers,
with no string manipulation needed.

### Workaround in place
- `taxpasta_column` is supplied explicitly in the POST payload
- MultiQC keys are derived by splitting on `.` and `_k2`
- FastQC keys are matched by prefix + `_raw_1` / `_raw_2` suffix
- fastp and bowtie2 keys are matched by prefix only