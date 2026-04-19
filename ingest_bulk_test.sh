#!/usr/bin/env bash
# ingest_bulk_test.sh
# Ingests test cases with random 12-character names and
# order dates spread across 2026-02-01 to 2026-04-06.
#
# Usage:
#   bash ingest_bulk_test.sh                  # 10 taxprofiler + 3 trana (defaults)
#   bash ingest_bulk_test.sh 50               # 50 taxprofiler + 3 trana
#   bash ingest_bulk_test.sh 50 10            # 50 taxprofiler + 10 trana
#   bash ingest_bulk_test.sh 0 5              # skip taxprofiler, ingest 5 trana

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Host path: used to run ingest.py from your machine
INGEST_SCRIPT="$REPO_ROOT/ingest.py"

# Container-visible paths: used by the backend when it reads files.
# The backend mounts the repo as /app/ inside Docker; for local uvicorn use
# the actual host path instead, e.g. /Users/you/repos/meta-vis-app/backend/test-data/slowowl.
TD="/app/test-data/slowowl"
TD_TRANA="/app/test-data/16S_trana"

PASSWORD="yourpassword"
URL="http://localhost:8000"
COUNT="${1:-10}"
TRANA_COUNT="${2:-3}"

START_DATE="2026-02-01"
END_DATE="2026-04-06"

start_epoch=$(date -j -f "%Y-%m-%d" "$START_DATE" "+%s")
end_epoch=$(date -j -f "%Y-%m-%d" "$END_DATE" "+%s")
range_days=$(( (end_epoch - start_epoch) / 86400 ))

# ---------------------------------------------------------------------------
# Taxprofiler cases
# ---------------------------------------------------------------------------

if [ "$COUNT" -gt 0 ]; then
  echo "Ingesting $COUNT taxprofiler case(s) from $START_DATE to $END_DATE..."
  echo ""

  success=0
  fail=0

  for i in $(seq 1 "$COUNT"); do
    case_id=$(LC_ALL=C tr -dc 'a-z' < /dev/urandom | head -c 12)

    offset_days=$(( RANDOM % (range_days + 1) ))
    offset_secs=$(( offset_days * 86400 ))
    order_epoch=$(( start_epoch + offset_secs ))
    order_date=$(date -j -r "$order_epoch" "+%Y-%m-%d")

    if python "$INGEST_SCRIPT" taxprofiler \
      --case-id "$case_id" \
      --order-date "$order_date" \
      --multiqc "$TD/taxprofiler/multiqc/multiqc_data/multiqc_data.json" \
      --pipeline-info "$TD/taxprofiler/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml" \
      --analysis-type "shotgun" \
      --sequencing-platform "illumina" \
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

    echo "  [taxprofiler $i/$COUNT] $case_id — $order_date (ok: $success, failed: $fail)"
  done

  echo ""
  echo "Taxprofiler: $success ingested, $fail failed."
  echo ""
fi

# ---------------------------------------------------------------------------
# Trana cases (16S amplicon, ONT, Emu)
# ---------------------------------------------------------------------------

if [ "$TRANA_COUNT" -gt 0 ]; then
  echo "Ingesting $TRANA_COUNT Trana (16S) case(s) from $START_DATE to $END_DATE..."
  echo ""

  t_success=0
  t_fail=0

  for i in $(seq 1 "$TRANA_COUNT"); do
    case_id="trana-$(LC_ALL=C tr -dc 'a-z' < /dev/urandom | head -c 8)"

    offset_days=$(( RANDOM % (range_days + 1) ))
    offset_secs=$(( offset_days * 86400 ))
    order_epoch=$(( start_epoch + offset_secs ))
    order_date=$(date -j -r "$order_epoch" "+%Y-%m-%d")

    if python "$INGEST_SCRIPT" trana \
      --case-id "$case_id" \
      --order-date "$order_date" \
      --pipeline-info "$TD_TRANA/pipeline_info/software_versions.yml" \
      --analysis-type "amplicon" \
      --sequencing-platform "nanopore" \
      --sample "sample_id=1234567890AB type=sample material=DNA abundance_path=$TD_TRANA/results/1234567890AB_downsampled.fastq_rel-abundance.tsv krona_path=$TD_TRANA/krona/1234567890AB_krona.html nanoplot_unprocessed_path=$TD_TRANA/nanoplot_unprocessed/1234567890AB_nanoplot_unprocessed_NanoStats.txt nanoplot_processed_path=$TD_TRANA/nanoplot_processed/1234567890AB_nanoplot_processed_NanoStats.txt" \
      --sample "sample_id=16SNEGABC123 type=negative_ctrl material=DNA abundance_path=$TD_TRANA/results/16SNEGABC123_downsampled.fastq_rel-abundance.tsv krona_path=$TD_TRANA/krona/16SNEGABC123_krona.html nanoplot_unprocessed_path=$TD_TRANA/nanoplot_unprocessed/16SNEGABC123_nanoplot_unprocessed_NanoStats.txt nanoplot_processed_path=$TD_TRANA/nanoplot_processed/16SNEGABC123_nanoplot_processed_NanoStats.txt" \
      --url "$URL" \
      --password "$PASSWORD" 2>/dev/null; then
      t_success=$(( t_success + 1 ))
    else
      t_fail=$(( t_fail + 1 ))
    fi

    echo "  [trana $i/$TRANA_COUNT] $case_id — $order_date (ok: $t_success, failed: $t_fail)"
  done

  echo ""
  echo "Trana: $t_success ingested, $t_fail failed."
fi