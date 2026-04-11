![meta-vis logo](assets/logo.svg)

# meta-vis-app

A web application for visualising and reviewing the output of [nf-core/taxprofiler](https://github.com/nf-core/taxprofiler) metagenomics runs, with optional integration of [metaval](https://github.com/genomic-medicine-sweden/metaval) post-processing results.

## What the app does

meta-vis-app is a **clinical interpretation tool for metagenomic quality control and pathogen detection**. It transforms complex taxonomic profiling data into actionable intelligence for clinicians and lab teams.

### Core Features

**Organize & Review Cases**

- Ingest taxonomic profiling results from nf-core/taxprofiler with a single command
- Organize results into cases (one per run) with multiple samples
- Review sample-level quality metrics (read counts, host removal, contamination)
- Mark cases as reviewed and add clinical notes

**Interpret Taxonomy Results**

- View organism detection across three classifiers (Kraken2, Centrifuge, DIAMOND)
- Search and filter organisms by name, kingdom, and abundance
- Interactive Krona visualizations for intuitive taxonomy exploration
- Cross-classifier comparison to validate detections

**Verify Findings with Confidence**

- When metaval results available: See IGV coverage plots and BLASTN alignments for detected organisms
- Confirms organisms are truly present in reads (not artifacts)
- Links sequence evidence directly to organism calls
- Reduces false positives and increases confidence in clinical reporting

**Monitor for Outbreaks & Contamination**

- **Outbreak alerts:** Automatically detects when same viral pathogen appears in 2+ cases
- **Quality control:** Track negative test control (NTC) contamination over time
- **Flexible monitoring:** Configurable time windows (7/14/30 days) and abundance thresholds
- **Team communication:** Orange alerts flag problematic patterns for immediate investigation

**Manage Quality Standards**

- Build curated lists of known contaminants to track
- Exclude environmental organisms from alerting
- Assign alert thresholds per organism
- Maintain audit trail of who added/removed list items

### Why It Matters

- ✓ **Clinical confidence** — Verification data (IGV + BLASTN) confirms organisms are real
- ✓ **Faster interpretation** — Organized interface reduces review time
- ✓ **Quality assurance** — Built-in contamination monitoring
- ✓ **Early warning** — Outbreak detection catches patterns before they spread
- ✓ **Compliance-ready** — Full audit trail and user-level access control

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

| Layer | Technology                             |
|---|----------------------------------------|
| Backend | FastAPI + Motor (async MongoDB driver) |
| Database | MongoDB 7.0 (Docker)                   |
| Object storage | MinIO (Docker) — optional, see docs    |
| Frontend | React 18 + Vite + Tailwind CSS         |
| Runtime | Python 3.13 (conda), Node.js ≥18       |

## License

See LICENSE file for details.

## Contact

Developed by Genomic Medicine Sweden. For questions or issues, please refer to the [documentation](https://meta-vis-app.readthedocs.io) or contact the development team.
