#!/usr/bin/env bash
# ingest_bulk_test.sh
# Ingests test cases with random 12-character names and
# order dates spread across 2026-02-01 to 2026-04-03 (61 days).
#
# Usage:
#   bash ingest_bulk_test.sh          # ingests 10 cases (default)
#   bash ingest_bulk_test.sh 50       # ingests 50 cases

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
TEST_DATA="$REPO_ROOT/backend/test-data/speedysnake"
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

for i in $(seq 1 $COUNT); do
  case_id=$(LC_ALL=C tr -dc 'a-z' < /dev/urandom | head -c 12)

  offset_days=$(( RANDOM % (range_days + 1) ))
  offset_secs=$(( offset_days * 86400 ))
  order_epoch=$(( start_epoch + offset_secs ))
  order_date=$(date -j -r "$order_epoch" "+%Y-%m-%d")

  if python "$REPO_ROOT/ingest.py" \
    --case-id "$case_id" \
    --order-date "$order_date" \
    --multiqc "$TEST_DATA/taxprofiler/multiqc_data.json" \
    --pipeline-info "$TEST_DATA/taxprofiler/software_versions.yml" \
    --classifier "kraken2 db=k2_pluspf taxpasta=$TEST_DATA/taxprofiler/kraken2_k2_pluspf.tsv krona=$TEST_DATA/taxprofiler/kraken2_k2_pluspf.html" \
    --classifier "centrifuge db=p_compressed+h+v taxpasta=$TEST_DATA/taxprofiler/centrifuge_p_compressed+h+v.tsv krona=$TEST_DATA/taxprofiler/centrifuge_p_compressed+h+v.html" \
    --sample "sample_id=SRR13439799 type=sample source=csf material=DNA column_kraken2=SRR13439799_se_SRR13439799_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR13439799_se_SRR13439799_p_compressed+h+v.centrifuge" \
    --sample "sample_id=SRR13439802 type=negative_ctrl source=feces material=DNA column_kraken2=SRR13439802_pe_SRR13439802_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR13439802_pe_SRR13439802_p_compressed+h+v.centrifuge" \
    --sample "sample_id=SRR13439790 type=sample source=blood material=RNA column_kraken2=SRR13439790_pe_SRR13439790_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR13439790_pe_SRR13439790_p_compressed+h+v.centrifuge" \
    --sample "sample_id=SRR13439813 type=negative_ctrl material=RNA column_kraken2=SRR13439813_pe_SRR13439813_k2_pluspf.kraken2.kraken2.report column_centrifuge=SRR13439813_pe_SRR13439813_p_compressed+h+v.centrifuge" \
    --metaval-igv "$TEST_DATA/metaval/igv" \
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