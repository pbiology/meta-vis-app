# meta-vis-app

A web application for visualising and reviewing the output of [nf-core/taxprofiler](https://github.com/nf-core/taxprofiler) metagenomics runs, with optional integration of [metaval](https://github.com/genomic-medicine-sweden/metaval) post-processing results.

## What the app does

meta-vis-app organises taxprofiler output into **cases** — one per pipeline run — each containing one or more **samples**. For each case the app provides:

- A case overview with per-sample general QC metrics (read counts, Q30, host removal)
- Per-classifier QC tables (unclassified %, species count, genera count, positive control detection, top taxa) with tabs to switch between classifiers
- Krona interactive taxonomy plots, tabbed per classifier
- A taxonomy table per classifier with search, kingdom filter, and rank display
- A provenance section showing pipeline and tool versions
- Case-level review status (mark as reviewed / unmark)

When metaval output is also ingested, taxa in the taxonomy table that have been verified by metaval gain a clickable pill linking to a details page showing IGV coverage reports.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Motor (async MongoDB driver) |
| Database | MongoDB 7.0 (Docker) |
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

# Static files
STATIC_FILES_ROOT=/data/taxprofiler

# App
APP_ENV=development
LOG_LEVEL=info

# Authentication
JWT_SECRET=<choose-a-long-random-string>
```

### 5. Start MongoDB
```bash
cd backend
docker compose up -d
```

This starts MongoDB and runs `mongo-init.js` which creates the `meta_vis_app` database user. This only runs on a fresh volume — if the container already exists you may need to remove the volume first:
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
uvicorn app.main:app --reload
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

## Ingesting data

All ingestion is done via the `ingest.py` script at the repo root. All file paths must be absolute.

### Taxprofiler output
```bash
python ingest.py \
  --case-id <case_id> \
  --multiqc /abs/path/to/multiqc_data.json \
  --pipeline-info /abs/path/to/software_versions.yml \
  --classifier "kraken2 db=k2_pluspf taxpasta=/abs/path/kraken2.tsv krona=/abs/path/kraken2.html" \
  --classifier "centrifuge db=p_compressed+h+v taxpasta=/abs/path/centrifuge.tsv krona=/abs/path/centrifuge.html" \
  --sample "sample_id=PE-04-28 type=test material=DNA order_date=2026-02-20 column_kraken2=PE-04-28_k2_pluspf.kraken2.kraken2.report column_centrifuge=PE-04-28_p_compressed+h+v.centrifuge" \
  --sample "sample_id=CTRL-01 type=negative_ctrl material=DNA column_kraken2=CTRL-01_k2_pluspf.kraken2.kraken2.report column_centrifuge=CTRL-01_p_compressed+h+v.centrifuge" \
  --password yourpassword
```

#### `--classifier` keys

| Key | Required | Notes |
|---|---|---|
| `name` (first token) | yes | `kraken2`, `centrifuge`, or `diamond` |
| `db` | yes | Reference database name, e.g. `k2_pluspf` |
| `taxpasta` | yes | Path to the taxpasta merged TSV file |
| `krona` | no | Path to the Krona HTML file |

#### `--sample` keys

| Key | Required | Notes |
|---|---|---|
| `sample_id` | yes | Must match the prefix in the taxpasta column name |
| `type` | yes | `test`, `positive_ctrl`, or `negative_ctrl` |
| `material` | yes | `DNA` or `RNA` |
| `column_<classifier>` | yes (per classifier) | Exact column name in the taxpasta TSV for that classifier |
| `subject_id` | no | Omit for controls |
| `order_date` | no | `YYYY-MM-DD` |

#### `--pipeline-info`

Accepts the `software_versions.yml` file from the taxprofiler `pipeline_info/` output directory.

#### Taxpasta column name format

taxprofiler appends classifier and database suffixes to column names:
```
# kraken2:    <sample_id>_<db>.kraken2.kraken2.report
# centrifuge: <sample_id>_<db>.centrifuge
```

For example:
```
column_kraken2=SRR13439802_pe_SRR13439802_k2_pluspf.kraken2.kraken2.report
column_centrifuge=SRR13439802_pe_SRR13439802_p_compressed+h+v.centrifuge
```

### Including metaval results

If metaval has been run on the same case, pass the path to metaval's `igv/` output directory:
```bash
python ingest.py \
  --case-id <case_id> \
  ... \
  --metaval-igv /abs/path/to/metaval/igv
```

Metaval results are ingested alongside the taxprofiler data. The metaval `igv/` directory must be a subdirectory of the metaval output root (i.e. `viral_taxids/` and `blast/` directories must be present as siblings).

#### Re-ingesting a case

Each `case_id` must be unique. To re-ingest, first delete the existing case and its samples from the database (e.g. via MongoDB Compass), then run the ingest command again.

---

## Data model

| Collection | Description |
|---|---|
| `cases` | One document per taxprofiler run. Stores classifiers, pipeline info, review status. |
| `samples` | One document per sample per case. Stores QC metrics, taxonomic profiles, and metaval associations. |
| `krona_files` | Krona HTML files, stored as text, keyed by case and classifier. |
| `metaval_results` | IGV reports and BLAST results from metaval, keyed by sample, classifier, and taxon. |
| `users` | App users with hashed passwords and roles. |

---

## User management

Users are managed through the Admin panel (top-left sidebar, visible to admins only). Three roles are available:

| Role | Capabilities |
|---|---|
| `reader` | View all cases and samples |
| `writer` | View + mark/unmark cases as reviewed |
| `admin` | View + review + manage users |

The first user must be created via the command line using `create_user.py` as described above. Subsequent users can be added through the Admin panel in the UI.