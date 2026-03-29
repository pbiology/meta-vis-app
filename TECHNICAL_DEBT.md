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

## Duplicate run_id on ingest

**File**: `backend/app/ingestor/orchestrator.py`

**Problem**: `POST /api/v1/ingest` always inserts a new run document, even if a
run with the same `run_id` already exists. Calling the endpoint twice with the
same `run_id` creates two run documents. Samples are linked to the `_id` of the
most recently created run, making the earlier run a ghost that returns no
samples.

**Fix**: Before inserting, check if a run with the given `run_id` already
exists. Either:
- Reject with `409 Conflict` if the run already exists (safest for production), or
- Upsert — add new samples to the existing run document instead of creating a
  new one (better for incremental ingestion workflows).

**Priority**: High — must be resolved before ingesting real data to avoid
silent data integrity issues.