#!/usr/bin/env bash
# ingest_bulk_test.sh
# Ingests slowowl test cases with random 12-character names and
# order dates spread across 2026-02-01 to 2026-04-06.
#
# Usage:
#   bash ingest_bulk_test.sh          # ingests 10 cases (default)
#   bash ingest_bulk_test.sh 50       # ingests 50 cases

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Host path: used to run ingest.py from your machine
INGEST_SCRIPT="$REPO_ROOT/ingest.py"

# Container-visible path: used by the backend when it reads files.
# The backend mounts the repo as /app/ inside Docker; for local uvicorn use
# the actual host path instead, e.g. /Users/you/repos/meta-vis-app/backend/test-data/slowowl.
TD="/app/test-data/slowowl"

PASSWORD="yourpassword"
URL="http://localhost:8000"
COUNT="${1:-10}"

START_DATE="2026-02-01"
END_DATE="2026-04-06"

start_epoch=$(date -j -f "%Y-%m-%d" "$START_DATE" "+%s")
end_epoch=$(date -j -f "%Y-%m-%d" "$END_DATE" "+%s")
range_days=$(( (end_epoch - start_epoch) / 86400 ))

echo "Ingesting $COUNT cases from $START_DATE to $END_DATE..."
echo ""

success=0
fail=0

for i in $(seq 1 "$COUNT"); do
  case_id=$(LC_ALL=C tr -dc 'a-z' < /dev/urandom | head -c 12)

  offset_days=$(( RANDOM % (range_days + 1) ))
  offset_secs=$(( offset_days * 86400 ))
  order_epoch=$(( start_epoch + offset_secs ))
  order_date=$(date -j -r "$order_epoch" "+%Y-%m-%d")

  if python "$INGEST_SCRIPT" \
    --case-id "$case_id" \
    --order-date "$order_date" \
    --multiqc "$TD/taxprofiler/multiqc/multiqc_data.json" \
    --pipeline-info "$TD/taxprofiler/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml" \
    --classifier "kraken2 db=k2_pluspf taxpasta=$TD/taxprofiler/taxpasta/kraken2_k2_pluspf.tsv krona=$TD/taxprofiler/krona/kraken2_k2_pluspf.html" \
    --classifier "centrifuge db=p_compressed+h+v taxpasta=$TD/taxprofiler/taxpasta/centrifuge_p_compressed+h+v.tsv krona=$TD/taxprofiler/krona/centrifuge_p_compressed+h+v.html" \
    --classifier "diamond db=diamond taxpasta=$TD/taxprofiler/taxpasta/diamond_diamond.tsv" \
    --sample "sample_id=26CE100005-DNA subject_id=26CE100005 type=sample material=DNA column_kraken2=26CE100005-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE100005-DNA_p_compressed+h+v.centrifuge column_diamond=26CE100005-DNA_diamond.diamond" \
    --sample "sample_id=26CE100005-RNA subject_id=26CE100005 type=sample material=RNA column_kraken2=26CE100005-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE100005-RNA_p_compressed+h+v.centrifuge column_diamond=26CE100005-RNA_diamond.diamond" \
    --sample "sample_id=NTC-260305-DNA type=negative_ctrl material=DNA column_kraken2=NTC-260305-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC-260305-DNA_p_compressed+h+v.centrifuge column_diamond=NTC-260305-DNA_diamond.diamond" \
    --sample "sample_id=NTC-260305-RNA type=negative_ctrl material=RNA column_kraken2=NTC-260305-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC-260305-RNA_p_compressed+h+v.centrifuge column_diamond=NTC-260305-RNA_diamond.diamond" \
    --metaval "$TD/metaval" \
    --url "$URL" \
    --password "$PASSWORD" 2>/dev/null; then
    success=$(( success + 1 ))
  else
    fail=$(( fail + 1 ))
  fi

  echo "[$i/$COUNT] $case_id — $order_date (ok: $success, failed: $fail)"
done

echo ""
echo "Done. $success ingested, $fail failed."