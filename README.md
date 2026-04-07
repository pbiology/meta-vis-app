![meta-vis logo](assets/logo.svg)

A web application for visualising and reviewing the output of [nf-core/taxprofiler](https://github.com/nf-core/taxprofiler) metagenomics runs, with optional integration of [metaval](https://github.com/genomic-medicine-sweden/metaval) post-processing results.

## What the app does

meta-vis-app organises taxprofiler output into **cases** — one per pipeline run — each containing one or more **samples**. For each case the app provides:

- A case overview with per-sample general QC metrics (read counts, Q30, host removal)
- Per-classifier QC tables (unclassified %, host %, species count, genera count, top taxa) with tabs to switch between classifiers
- Krona interactive taxonomy plots, tabbed per classifier
- A taxonomy table per classifier with search, kingdom filter, and rank display
- A provenance section showing pipeline and tool versions (taxprofiler and metaval)
- Case-level review status (mark as reviewed / unmark)
- Case-level notes, allowing reviewers to record observations while viewing the data

When metaval output is also ingested, taxa in the taxonomy table that have been verified by metaval gain a clickable pill linking to a details page showing IGV coverage reports and BLASTN results.

The app also includes an **outbreak detection** feature that monitors viral taxa appearing across multiple cases within a configurable time window.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Motor (async MongoDB driver) |
| Database | MongoDB 7.0 (Docker) |
| Object storage | MinIO (Docker) — optional, see below |
| Frontend | React 18 + Vite + Tailwind CSS |
| Runtime | Python 3.11 (conda), Node.js |

---

## Deployment

### 1. Prerequisites

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or Anaconda
- Docker and Docker Compose
- Node.js ≥ 18

### 2. Clone the repository

```bash
git clone <repo-url>
cd meta-vis-app
```

### 3. Create the conda environment

```bash
conda env create -f backend/environment.yml
conda activate meta-vis-app
pip install -e backend/
```

### 4. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```
# MongoDB
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DB_NAME=meta-vis-dev
MONGODB_USERNAME=meta_vis_app
MONGO_APP_PASSWORD=<choose-a-password>
MONGO_ROOT_PASSWORD=<choose-a-root-password>
MONGODB_AUTH_SOURCE=admin

# App
APP_ENV=development
LOG_LEVEL=info

# Authentication
JWT_SECRET=<choose-a-long-random-string>

# Object storage — optional, see Object storage section below
# OBJECT_STORAGE_ENDPOINT=http://localhost:9000
# OBJECT_STORAGE_ACCESS_KEY=<choose-a-password>
# OBJECT_STORAGE_SECRET_KEY=<choose-a-password>
# OBJECT_STORAGE_BUCKET=meta-vis
```

### 5. Start services

```bash
cd backend
docker compose up -d
```

This starts MongoDB (and MinIO if object storage is configured). MongoDB runs `mongo-init.js` on first start to create the application database user. If the container already exists you may need to remove the volume first:

```bash
docker compose down -v
docker compose up -d
```

### 6. Create the first app user

```bash
cd backend
conda activate meta-vis-app
python create_user.py --username admin --password yourpassword --role admin
```

Roles are `reader`, `writer`, or `admin`. Only admins can manage users. Only writers and admins can mark cases as reviewed.

### 7. Start the backend

```bash
cd backend
conda activate meta-vis-app
uvicorn app.main:app --reload --host 127.0.0.1
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 8. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Object storage

Krona HTML files and IGV reports are large blobs that are poor candidates for storage inside MongoDB. The app supports two backends for these files, selected by configuration at startup.

### MongoDB backend (default)

When no object storage is configured, Krona and IGV files are stored in a `blobs` collection in MongoDB, keyed by a path string. This works out of the box with no additional setup and is suitable for small deployments or development.

### MinIO / S3 backend (recommended for production)

For larger deployments, storing blobs in S3-compatible object storage keeps MongoDB lean and fast. The app ships with MinIO pre-configured in `docker-compose.yml`.

**To enable MinIO:**

Uncomment the four `OBJECT_STORAGE_*` lines in `backend/.env` and set credentials to match `docker-compose.yml`:

```
OBJECT_STORAGE_ENDPOINT=http://localhost:9000
OBJECT_STORAGE_ACCESS_KEY=<choose-a-password>
OBJECT_STORAGE_SECRET_KEY=<choose-a-password>
OBJECT_STORAGE_BUCKET=meta-vis
```

Start MinIO:

```bash
cd backend
docker compose up -d minio
```

Restart the backend — it will detect the env vars and switch to the S3 backend automatically, creating the bucket if it does not exist.

The MinIO web console is available at `http://localhost:9001`. Objects are stored with the following key structure:

```
meta-vis/
  krona/{case_object_id}/{classifier}.html
  igv/{case_object_id}/{sample_name}/{classifier}/{organism_name}.html
```

**Switching between backends:** Cases ingested with one backend will have their blobs in that backend only. If you switch backends, previously ingested cases will have broken Krona and IGV views until re-ingested. The recommended approach is to clear all case data and re-ingest after switching.

**Production S3:** To use AWS S3 or another S3-compatible service instead of MinIO, set `OBJECT_STORAGE_ENDPOINT` to the service endpoint and provide real credentials. No code changes are required.

---

## Ingesting data

All ingestion is done via the `ingest.py` script at the repo root. All file paths must be absolute.

### Taxprofiler output

```bash
python ingest.py \
  --case-id <case_id> \
  --order-date 2026-02-20 \
  --multiqc /abs/path/to/multiqc_data.json \
  --pipeline-info /abs/path/to/software_versions.yml \
  --classifier "kraken2 db=k2_pluspf taxpasta=/abs/path/kraken2.tsv krona=/abs/path/kraken2.html" \
  --classifier "centrifuge db=p_compressed+h+v taxpasta=/abs/path/centrifuge.tsv krona=/abs/path/centrifuge.html" \
  --classifier "diamond db=diamond taxpasta=/abs/path/diamond.tsv" \
  --sample "sample_id=PE-04-28 type=sample material=DNA column_kraken2=PE-04-28_k2_pluspf.kraken2.kraken2.report column_centrifuge=PE-04-28_p_compressed+h+v.centrifuge column_diamond=PE-04-28_diamond.diamond" \
  --sample "sample_id=CTRL-01 type=negative_ctrl material=DNA column_kraken2=CTRL-01_k2_pluspf.kraken2.kraken2.report column_centrifuge=CTRL-01_p_compressed+h+v.centrifuge column_diamond=CTRL-01_diamond.diamond" \
  --password yourpassword
```

#### `--classifier` keys

| Key | Required | Notes |
|---|---|---|
| `name` (first token) | yes | `kraken2`, `centrifuge`, or `diamond` |
| `db` | yes | Reference database name, e.g. `k2_pluspf` |
| `taxpasta` | yes | Path to the taxpasta merged TSV file |
| `krona` | no | Path to the Krona HTML file — not produced by diamond |

#### `--sample` keys

| Key | Required | Notes |
|---|---|---|
| `sample_id` | yes | Must match the prefix in the taxpasta column name |
| `type` | yes | `sample`, `positive_ctrl`, or `negative_ctrl` |
| `material` | yes | `DNA` or `RNA` |
| `column_<classifier>` | yes (per classifier) | Exact column name in the taxpasta TSV for that classifier |
| `subject_id` | no | Omit for controls |

#### `--order-date`

The date the samples in this case were ordered (`YYYY-MM-DD`). Used by the outbreak detection feature. Cases without an order date are excluded from outbreak analysis.

#### `--pipeline-info`

Accepts the `software_versions.yml` or `nf_core_*_software_mqc_versions.yml` file from the taxprofiler `pipeline_info/` output directory.

#### Taxpasta column name format

taxprofiler appends classifier and database suffixes to column names:

```
kraken2:    <sample_id>_<db>.kraken2.kraken2.report
centrifuge: <sample_id>_<db>.centrifuge
diamond:    <sample_id>_<db>.diamond
```

### Including metaval results

If metaval has been run on the same case, pass the path to metaval's `igv/` output directory:

```bash
python ingest.py \
  --case-id <case_id> \
  ... \
  --metaval-igv /abs/path/to/metaval/igv
```

The metaval `igv/` directory must be a subdirectory of the metaval output root (i.e. `viral_taxids/` and `blast/` directories must be present as siblings). IGV HTML files are uploaded to the configured blob store during ingest.

#### Re-ingesting a case

Each `case_id` must be unique. To re-ingest, delete the existing case via the UI (admin only) or the API, then run the ingest command again. Deleting a case also removes all associated blobs from object storage.

---

## Outbreak alerts

The app continuously monitors for viral taxa appearing in multiple cases within a rolling time window. This is intended as an early signal for potential outbreak situations.

**How it works:**
- On request, the backend queries cases with an `order_date` within `2 × window_days` of today — bounding the query regardless of total database size
- A MongoDB aggregation pipeline runs entirely inside the database: sample profiles are unwound, filtered to qualifying viral taxa (superkingdom = Viruses, rank in species/no rank/serotype, abundance > 1, not on the ignorelist), and grouped by taxon to collect the set of distinct cases each taxon appears in
- Only taxa seen in 2 or more cases are returned to Python, where a sliding window clusters cases by `order_date`
- Results are cached in memory for 1 hour and explicitly invalidated when a new case is ingested or the ignorelist changes
- Flagged taxa are surfaced in three places: the **Alerts** page (accessible from the sidebar), a warning indicator on the **case list**, and an amber pill in the **taxonomy table** on the sample page

**Scope and limitations:**
- Only viruses are considered (superkingdom = Viruses)
- Only taxa with more than 1 classified read are included
- Detection is based on `order_date` on the case, not ingestion date — cases without an order date are excluded
- The time window can be adjusted to 7, 14, or 30 days from the Alerts page
- The ignorelist is managed from the Alerts page (writers can add, admins can remove)

---

## Performance

### Object storage

Krona HTML files (1–2 MB each) and IGV reports are stored in object storage rather than MongoDB. This keeps the MongoDB working set small and avoids write amplification from large inline documents. Krona and IGV uploads during ingest are performed concurrently using `asyncio.gather`.

### Outbreak detection scaling

The aggregation pipeline approach scales well because the query is bounded by the time window, not total case count. At 500 cases/month with a 30-day window, the pipeline operates on ~1,000 cases regardless of total database size.

The main cost is the `$unwind` stages, which expand profile arrays before filtering. This is acceptable because results are cached for 1 hour and invalidated explicitly on ingest and ignorelist changes.

**Known future optimisation — pre-computed viral taxa summary**

The `$unwind` cost could be eliminated by storing a pre-computed summary of qualifying viral taxa alongside each sample at ingest time. Instead of unwinding the full profile array, the aggregation would run on a small `viral_taxa` array. This is not currently implemented and should be considered if MongoDB memory pressure becomes observable in production.

---

## Data model

| Collection | Description |
|---|---|
| `cases` | One document per taxprofiler run. Stores classifiers, pipeline info, order date, review status, notes, and denormalised sample summary fields. |
| `samples` | One document per sample per case. Stores QC metrics and taxonomic profiles. Contains denormalised `case_id_str` and `order_date` for efficient list queries. |
| `blobs` | Krona and IGV HTML files when using the MongoDB blob backend. Empty when using MinIO. |
| `metaval_results` | BLAST results and organism metadata from metaval. IGV HTML is stored in the blob store; documents contain only a key reference. |
| `users` | App users with hashed passwords and roles. |
| `outbreak_ignorelist` | Taxa excluded from outbreak detection, with reason and author. |

Outbreak detection is computed at query time from the `cases` and `samples` collections.

---

## User management

Users are managed through the Admin panel (sidebar, visible to admins only). Three roles are available:

| Role | Capabilities |
|---|---|
| `reader` | View all cases and samples |
| `writer` | View + mark/unmark cases as reviewed + add notes |
| `admin` | View + review + add notes + manage users |

The first user must be created via the command line using `create_user.py` as described above. Subsequent users can be added through the Admin panel in the UI.
