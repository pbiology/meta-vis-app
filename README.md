![meta-vis logo](assets/logo.svg)

# meta-vis-app

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

## Quick Start

### 1. Installation

See the [Installation Guide](https://meta-vis-app.readthedocs.io/en/latest/getting-started/installation.html).

```bash
git clone <repo-url>
cd meta-vis-app

# Backend setup
cd backend
conda env create -f environment.yml
conda activate meta-vis-app
pip install -e .
cp .env.example .env
docker compose up -d

# Create first user
python create_user.py --username admin --password yourpassword --role admin

# Start backend
uvicorn app.main:app --reload

# Frontend setup (in new terminal)
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

### 2. Load Test Data

```bash
python ingest.py \
  --case-id test-case-001 \
  --order-date 2026-02-20 \
  --multiqc test-data/multiqc_data.json \
  --pipeline-info test-data/pipeline_info/nf_core_pipeline_software_mqc_versions.yml \
  --classifier "kraken2 db=k2_pluspf taxpasta=test-data/kraken2_k2_pluspf.tsv krona=test-data/kraken2_k2_pluspf.html" \
  --sample "sample_id=SRR13439790 type=sample material=DNA column_kraken2=SRR13439790_k2_pluspf.kraken2.kraken2.report" \
  --password yourpassword
```

## Documentation

Full documentation is available at: **https://meta-vis-app.readthedocs.io**

### For users:
- [Getting Started](https://meta-vis-app.readthedocs.io/en/latest/getting-started/overview.html)
- [User Guide](https://meta-vis-app.readthedocs.io/en/latest/user-guide/cases-and-samples.html)
- [Outbreak Detection](https://meta-vis-app.readthedocs.io/en/latest/user-guide/outbreak-detection.html)

### For administrators:
- [Deployment](https://meta-vis-app.readthedocs.io/en/latest/deployment/docker-compose.html)
- [Data Ingestion](https://meta-vis-app.readthedocs.io/en/latest/administration/ingestion.html)
- [Troubleshooting](https://meta-vis-app.readthedocs.io/en/latest/administration/troubleshooting.html)

### For developers:
- [Architecture](https://meta-vis-app.readthedocs.io/en/latest/developer/architecture.html)
- [Contributing](https://meta-vis-app.readthedocs.io/en/latest/developer/contributing.html)
- [Data Model](https://meta-vis-app.readthedocs.io/en/latest/developer/data-model.html)

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Motor (async MongoDB driver) |
| Database | MongoDB 7.0 (Docker) |
| Object storage | MinIO (Docker) — optional, see docs |
| Frontend | React 18 + Vite + Tailwind CSS |
| Runtime | Python 3.11 (conda), Node.js ≥18 |

## License

See LICENSE file for details.

## Contact

Developed by Genomic Medicine Sweden. For questions or issues, please refer to the [documentation](https://meta-vis-app.readthedocs.io) or contact the development team.
