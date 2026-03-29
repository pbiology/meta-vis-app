# meta-vis-app

Visualization frontend for nf-core/taxprofiler metagenomics output.

**Stack:** FastAPI + Motor + MongoDB (`meta-vis-dev`) · React 18 + Vite + Tailwind · conda env `meta-vis-app`

---

## Setup

```bash
conda activate meta-vis-app
# Backend
cd backend && uvicorn app.main:app --reload
# Frontend
cd frontend && npm run dev
```

---

## Ingesting a run

All paths must be **absolute**. Run from the repo root.

```bash
python ingest.py \
  --case-id <case_id> \
  --taxonomy-db <db_name> \
  --taxpasta  /abs/path/to/kraken2_<db>.tsv \
  --multiqc   /abs/path/to/multiqc_data.json \
  --pipeline-info /abs/path/to/pipeline_info/ \
  --krona     /abs/path/to/kraken2_<db>.html \
  --sample "subject_id=S-001 sample_id=PE-04-28 column=PE-04-28_k2_pluspf.kraken2.kraken2.report type=test material=DNA order_date=2026-02-20" \
  --sample "sample_id=CTRL-DNA column=CTRL-DNA_k2_pluspf.kraken2.kraken2.report type=negative_ctrl material=DNA" \
  --password yourpassword
```

### `--sample` keys

| Key | Required | Values | Notes |
|---|---|---|---|
| `sample_id` | yes | string | e.g. `PE-04-28` |
| `column` | yes | string | exact column name in the taxpasta TSV |
| `type` | yes | `test` \| `positive_ctrl` \| `negative_ctrl` | |
| `material` | yes | `DNA` \| `RNA` | |
| `subject_id` | no | string | omit for controls |
| `order_date` | no | `YYYY-MM-DD` | |

### Column name format (taxprofiler convention)

The `column` value is the full taxprofiler-suffixed header from the TSV:
```
<sample_id>_<db>.kraken2.kraken2.report
# e.g.: PE-04-28_k2_pluspf.kraken2.kraken2.report
```

---

## Reference ingest — `run_2026_02_23_large`

```bash
python ingest.py \
  --case-id run_2026_02_23_large \
  --taxonomy-db k2_pluspf \
  --taxpasta      /Users/anderslind/repos/meta-vis-app/backend/test-data/outTestLarge/taxpasta/kraken2_k2_pluspf.tsv \
  --multiqc       /Users/anderslind/repos/meta-vis-app/backend/test-data/outTestLarge/multiqc/multiqc_data/multiqc_data.json \
  --pipeline-info /Users/anderslind/repos/meta-vis-app/backend/test-data/outTestLarge/pipeline_info \
  --krona         /Users/anderslind/repos/meta-vis-app/backend/test-data/outTestLarge/krona/kraken2_k2_pluspf.html \
  --sample "subject_id=S-001 sample_id=PE-04-28 column=PE-04-28_k2_pluspf.kraken2.kraken2.report type=test         material=DNA order_date=2026-02-20" \
  --sample "subject_id=S-001 sample_id=EN-30-35 column=EN-30-35_k2_pluspf.kraken2.kraken2.report type=test         material=RNA order_date=2026-02-20" \
  --sample "                 sample_id=H2-17-32 column=H2-17-32_k2_pluspf.kraken2.kraken2.report type=positive_ctrl material=DNA order_date=2026-02-20" \
  --sample "                 sample_id=VZ-20-28 column=VZ-20-28_k2_pluspf.kraken2.kraken2.report type=positive_ctrl material=RNA order_date=2026-02-20" \
  --password yourpassword
```

**Sample breakdown:**
- `PE-04-28` — subject S-001, DNA, test
- `EN-30-35` — subject S-001, RNA, test
- `H2-17-32` — no subject, DNA, positive control
- `VZ-20-28` — no subject, RNA, positive control

---

## Data model notes

- **Case** = one taxprofiler run (`runs` collection). Review lives here.
- **Sample** = one library within a case (`samples` collection). Multiple samples share taxpasta/multiqc/krona files.
- **Krona** is stored at run level (`krona_files` collection), linked by `run_id` ObjectId.
- **Taxonomy** lives in `taxonomy_databases` + `taxonomy_nodes`; load once with `taxonomy.py` before ingesting.
- `run_id` is a unique string — re-ingesting the same `run_id` returns HTTP 422. Drop the run from Compass first.
