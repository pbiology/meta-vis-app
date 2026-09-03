#!/usr/bin/env bash
# bulk_ingest.sh
# Ingests test cases with random adjective-animal names and order dates spread
# across the last WINDOW_DAYS days (default 60), so they land inside the
# lookback windows the Alerts and NTC trends pages use.
#
# Usage:
#   bash bulk_ingest.sh                           # 10 taxprofiler + 3 trana, CG stage KC + local backend
#   bash bulk_ingest.sh --env k8s                 # same, against K8s deployment
#   bash bulk_ingest.sh 50 3 --env k8s            # 50 taxprofiler + 3 trana, K8s
#   bash bulk_ingest.sh 0 5                       # skip taxprofiler, 5 trana
#   RESET=1 bash bulk_ingest.sh                   # drop collections first, then ingest
#
#   bash bulk_ingest.sh 10 3 --reingest 4         # plus 4 re-sequenced cases
#   bash bulk_ingest.sh 0 0 --reingest 2 --reingest-depth 1
#                                                 # 2 cases with two analyses each
#   bash bulk_ingest.sh 0 0 --ntc 20              # 20 NTC-only cases for the trends page
#   WINDOW_DAYS=30 bash bulk_ingest.sh            # tighter date spread
#
# A case can be sequenced more than once, so re-ingesting the same --case-id
# appends an analysis rather than replacing the case. --reingest exercises that
# with backend/test-data/fullcamel, which is one patient's sample set actually
# sequenced three times (one subdirectory per run date) — so each analysis
# carries genuinely different profiles and QC, not a replayed bundle.
#
# --reingest N creates N such cases, independent of the taxprofiler count.
# It cannot append to the cases the taxprofiler pass creates: those are
# subject 26CE100005 (slowowl) and fullcamel is a different patient, which the
# ingest subject cross-check rejects by design.
#
# --reingest-depth controls how many *extra* analyses each case gets, so depth
# 1 gives two analyses and depth 2 gives three. Left out, every run directory
# is used — three analyses per case today. An explicit value is capped at the
# number of run directories available.
#
# fullcamel's samplesheet also carried a second patient (26CE500025); only
# 26CE500026 and the run's negative controls are declared here. The undeclared
# columns are inert — both taxpasta and MultiQC are read per declared sample.
#
# --ntc N ingests N negative-control-only cases whose kraken2 profiles carry
# planted recurring contaminants, which is what the NTC trends page looks for.
# Fixtures are generated on demand by backend/test-data/generate_ntc_test_data.py.
#
# Prerequisites (cg env):
#   KEYCLOAK_CLIENT_SECRET is read from .env in the repo root automatically.
#   The local backend must be running: uvicorn app.main:app --reload
#
# Prerequisites (k8s env):
#   The script fetches KEYCLOAK_CLIENT_SECRET from Vault automatically.
#   You must be logged in to Vault first:
#     vault login -address=https://vault.test.kim.karolinska.se -method=oidc
#   Corporate CA (one-time setup — fixes Python SSL against the K8s cluster):
#     security find-certificate -a -c "Region Stockholm" -p > /tmp/region-stockholm-ca.pem
#     cat "$(python -c 'import certifi; print(certifi.where())')" \
#         /tmp/region-stockholm-ca.pem > /tmp/combined-ca.pem
#     export REQUESTS_CA_BUNDLE=/tmp/combined-ca.pem   # add to your shell rc

set -uo pipefail

# ---------------------------------------------------------------------------
# Load repo-root .env so KEYCLOAK_CLIENT_SECRET etc. are available.
# ---------------------------------------------------------------------------
REPO_ROOT_ENV="$(cd "$(dirname "$0")" && pwd)/.env"
if [[ -f "$REPO_ROOT_ENV" ]]; then
  set -o allexport
  # shellcheck source=/dev/null
  source "$REPO_ROOT_ENV"
  set +o allexport
fi

# ---------------------------------------------------------------------------
# Argument parsing — positional COUNT / TRANA_COUNT plus an --env flag.
# ---------------------------------------------------------------------------
ENV="cg"
REINGEST=0
# Empty means "use every available run directory". Left unset rather than
# defaulting to 1 so that the whole re-sequencing dataset is exercised by
# default, and so adding a run directory deepens the cases automatically.
REINGEST_DEPTH=""
NTC_COUNT=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENV="$2"
      shift 2
      ;;
    --reingest)
      REINGEST="$2"
      shift 2
      ;;
    --reingest-depth)
      REINGEST_DEPTH="$2"
      shift 2
      ;;
    --ntc)
      NTC_COUNT="$2"
      shift 2
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

COUNT="${POSITIONAL[0]:-10}"
TRANA_COUNT="${POSITIONAL[1]:-3}"

for n in "$REINGEST" "$NTC_COUNT"; do
  if ! [[ "$n" =~ ^[0-9]+$ ]]; then
    echo "Error: --reingest and --ntc take a non-negative integer (got: '$n')" >&2
    exit 1
  fi
done
# Only validated when given; unset resolves to the run count in the pass below.
if [[ -n "$REINGEST_DEPTH" ]]; then
  if ! [[ "$REINGEST_DEPTH" =~ ^[0-9]+$ ]]; then
    echo "Error: --reingest-depth takes a non-negative integer (got: '$REINGEST_DEPTH')" >&2
    exit 1
  fi
  if [[ "$REINGEST_DEPTH" -lt 1 ]]; then
    echo "Error: --reingest-depth must be at least 1" >&2
    exit 1
  fi
fi

case "$ENV" in
  cg|k8s) ;;
  *) echo "Error: --env must be 'cg' or 'k8s' (got: '$ENV')" >&2; exit 1 ;;
esac

# ---------------------------------------------------------------------------
# Environment-specific settings
# ---------------------------------------------------------------------------
case "$ENV" in
  cg)
    URL="http://localhost:8000"
    if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
      echo "Error: KEYCLOAK_CLIENT_SECRET is not set. Add it to .env in the repo root." >&2
      exit 1
    fi
    KC_ARGS=(
      --keycloak-url https://keycloak-stage.cg-orchestration.sys.scilifelab.se
      --realm clinical-genomics
      --client-id meta-vis-cli
      --client-secret "$KEYCLOAK_CLIENT_SECRET"
    )
    ;;
  k8s)
    URL="https://metavis-backend.apps.test.kim.karolinska.se"
    KC_ARGS=(--keycloak-url https://sso.test.kim.karolinska.se --realm karolinska --client-id meta-vis-cli)

    # Always fetch the K8s client secret from Vault (the .env holds the CG secret, not K8s).
    unset KEYCLOAK_CLIENT_SECRET
    VAULT_ADDR="${VAULT_ADDR:-https://vault.test.kim.karolinska.se}"
    VAULT_PATH="kar-app-gmck-apps/dev/meta-vis"
    VAULT_FIELD="KEYCLOAK_CLI_SECRET"
    echo "Fetching K8s client secret from Vault ($VAULT_ADDR)..."
    if ! command -v vault >/dev/null 2>&1; then
      echo "Error: 'vault' CLI not found on PATH. Install it or set KEYCLOAK_CLIENT_SECRET manually." >&2
      exit 1
    fi
    KEYCLOAK_CLIENT_SECRET=$(vault kv get \
      -address="$VAULT_ADDR" \
      -mount=secret \
      -field="$VAULT_FIELD" \
      "$VAULT_PATH") || {
        echo "Error: Vault lookup failed. Make sure you are logged in:" >&2
        echo "  vault login -address=$VAULT_ADDR -method=oidc" >&2
        exit 1
      }
    echo "Vault: secret fetched OK."
    echo ""
    KC_ARGS+=(--client-secret "$KEYCLOAK_CLIENT_SECRET")

    if [[ -z "${REQUESTS_CA_BUNDLE:-}" ]]; then
      echo "Warning: REQUESTS_CA_BUNDLE is not set — K8s TLS may fail (Region Stockholm CA)." >&2
      echo "  See the K8s prerequisites comment at the top of this script." >&2
      echo ""
    fi
    ;;
  *)
    echo "Error: unhandled env '$ENV'" >&2
    exit 1
    ;;
esac

echo "Environment : $ENV"
echo "Backend URL : $URL"
echo ""

# ---------------------------------------------------------------------------
# Optional reset: drop case-owned collections before ingesting.
# ---------------------------------------------------------------------------
if [[ "${RESET:-0}" = "1" ]]; then
  MONGO_DB="${MONGO_DB:-meta_vis}"
  MONGO_URI="${MONGO_URI:-mongodb://localhost:27017/$MONGO_DB}"
  echo "RESET=1 — dropping case-owned collections in $MONGO_DB..."
  if ! command -v mongosh >/dev/null 2>&1; then
    echo "Error: mongosh not found on PATH — cannot reset collections" >&2
    exit 1
  fi
  # case_analysis must go too: a case is now identity plus N analyses. Leaving
  # the analyses behind would make the next ingest of the same case name resolve
  # its version from the stale documents and start at v2.
  # subjects are dropped because a raw collection drop, unlike DELETE /cases,
  # does not clean up subjects left with no cases.
  mongosh --quiet "$MONGO_URI" --eval '
    db.cases.drop();
    db.case_analysis.drop();
    db.samples.drop();
    db.metaval_results.drop();
    db.subjects.drop();
    db.blobs.drop();
    print("dropped cases/case_analysis/samples/metaval_results/subjects/blobs");
  '
  echo ""
fi

# ---------------------------------------------------------------------------
# Paths — host-local (CLI bundles these files and uploads them; the server
# never reads from its own filesystem anymore).
# ---------------------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

TD="$REPO_ROOT/backend/test-data/slowowl"
TD_TRANA="$REPO_ROOT/backend/test-data/16S_trana"
TD_NTC="$REPO_ROOT/backend/test-data/ntc"
TD_FULLCAMEL="$REPO_ROOT/backend/test-data/fullcamel"
NTC_GENERATOR="$REPO_ROOT/backend/test-data/generate_ntc_test_data.py"

INGEST_SCRIPT="$REPO_ROOT/ingest.py"

ADJECTIVES_FILE="$REPO_ROOT/backend/test-data/adjectives.txt"
ANIMALS_FILE="$REPO_ROOT/backend/test-data/animals.txt"

for f in "$ADJECTIVES_FILE" "$ANIMALS_FILE" "$TD" "$TD_TRANA" "$INGEST_SCRIPT"; do
  if [[ ! -e "$f" ]]; then
    echo "Error: missing required path: $f" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# fullcamel run directories — one per sequencing date, named YYYY-MM-DD.
#
# Discovered rather than hard-coded so that dropping a fourth run in extends
# the maximum --reingest-depth without touching this script. Sorted, so
# FULLCAMEL_RUNS[0] is the earliest run and index order is version order.
# Only resolved when --reingest is used; the dataset is optional otherwise.
# ---------------------------------------------------------------------------
FULLCAMEL_RUNS=()
if [[ -d "$TD_FULLCAMEL" ]]; then
  while IFS= read -r d; do
    FULLCAMEL_RUNS+=("$d")
  done < <(find "$TD_FULLCAMEL" -mindepth 1 -maxdepth 1 -type d | sort)
fi

# ---------------------------------------------------------------------------
# Case-ID generation
# ---------------------------------------------------------------------------
adjectives=()
while IFS= read -r line; do [[ -n "$line" ]] && adjectives+=("$line"); done < "$ADJECTIVES_FILE"
animals=()
while IFS= read -r line; do [[ -n "$line" ]] && animals+=("$line"); done < "$ANIMALS_FILE"

used_ids=()

generate_case_id() {
  local max_combos=$(( ${#adjectives[@]} * ${#animals[@]} ))
  if [[ "${#used_ids[@]}" -ge "$max_combos" ]]; then
    echo "Error: exhausted all $max_combos adjective-animal combinations" >&2
    return 1
  fi
  local candidate taken
  while :; do
    local adj="${adjectives[$(( RANDOM % ${#adjectives[@]} ))]}"
    local ani="${animals[$(( RANDOM % ${#animals[@]} ))]}"
    candidate="${adj}${ani}"
    taken=0
    for existing in ${used_ids[@]+"${used_ids[@]}"}; do
      [[ "$existing" = "$candidate" ]] && { taken=1; break; }
    done
    [[ "$taken" -eq 0 ]] && break
  done
  used_ids+=("$candidate")
  echo "$candidate"
}

# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------
# Order dates are relative to today, not pinned. The Alerts and NTC views only
# look back a fixed window (90 days for NTC trends, 2x the outbreak window for
# alerts), so a hard-coded range silently ages out and every ingested case
# lands outside it — the data loads fine but those pages stay empty.
WINDOW_DAYS="${WINDOW_DAYS:-60}"

end_epoch=$(date "+%s")
start_epoch=$(( end_epoch - WINDOW_DAYS * 86400 ))
START_DATE=$(date -j -r "$start_epoch" "+%Y-%m-%d")
END_DATE=$(date -j -r "$end_epoch" "+%Y-%m-%d")
range_days="$WINDOW_DAYS"

random_date() {
  local offset=$(( RANDOM % (range_days + 1) ))
  date -j -r $(( start_epoch + offset * 86400 )) "+%Y-%m-%d"
  return
}

# As random_date, but leaves $1 days of room before the end of the window. A
# re-sequenced case dates its later analyses forward from this base, so without
# the headroom the newest analysis can land after today.
random_date_with_headroom() {
  # Declared separately: bash creates every name in a `local` list before
  # assigning any of them, so referencing headroom on the same line trips
  # `set -u` and the function silently produces nothing.
  local headroom="$1"
  local span=$(( range_days - headroom ))
  if (( span < 0 )); then
    # The cadence is longer than the window, so no base inside the window can
    # hold it. Anchor the newest analysis on today and let the earlier ones
    # predate the window — clamping span here instead would still add the full
    # headroom onto START_DATE and date the newest analysis in the future.
    date -j -r $(( end_epoch - headroom * 86400 )) "+%Y-%m-%d"
    return
  fi
  local offset=$(( RANDOM % (span + 1) ))
  date -j -r $(( start_epoch + offset * 86400 )) "+%Y-%m-%d"
  return
}

# Later order date for a re-sequencing, so version order is visible in the UI.
date_plus_days() {
  local base="$1" days="$2" base_epoch
  # Guarded because an empty or malformed base silently yielded 1970-01-01,
  # which reads as a plausible order date rather than as a failure.
  if ! base_epoch=$(date -j -f "%Y-%m-%d" "$base" "+%s" 2>/dev/null); then
    echo "Error: date_plus_days got an invalid base date: '$base'" >&2
    return 1
  fi
  date -j -r $(( base_epoch + days * 86400 )) "+%Y-%m-%d"
  return
}

# Whole days from $1 to $2 (both YYYY-MM-DD). Used to carry the real spacing
# between fullcamel run directories onto a freshly picked base date, so the
# re-sequencing cadence stays authentic without pinning the order dates to
# 2026 — see the WINDOW_DAYS note above for why pinned dates are a trap.
days_between() {
  local from="$1" to="$2" from_epoch to_epoch
  from_epoch=$(date -j -f "%Y-%m-%d" "$from" "+%s")
  to_epoch=$(date -j -f "%Y-%m-%d" "$to" "+%s")
  echo $(( (to_epoch - from_epoch) / 86400 ))
  return
}

ms() { python3 -c "import time; print(int(time.time()*1000))"; return; }

# ---------------------------------------------------------------------------
# One taxprofiler ingest of the slowowl dataset — one patient (26CE100005),
# full metaval tree, three classifiers. Every case the taxprofiler pass creates
# shares this sample set, so they all land under the same subject.
#
# --yes is required, not cosmetic: the CLI confirms before uploading whenever
# stdin is a terminal, and inside output=$(...) only stdout is redirected — so
# without it the prompt is swallowed and the script blocks forever.
# ---------------------------------------------------------------------------
ingest_taxprofiler_case() {
  local case_id="$1" order_date="$2"
  python "$INGEST_SCRIPT" taxprofiler \
    --case-id "$case_id" \
    --ticket-id "1007645" \
    --order-date "$order_date" \
    --multiqc           "$TD/taxprofiler/multiqc/multiqc_data/multiqc_data.json" \
    --multiqc-report    "$TD/taxprofiler/multiqc/multiqc_report.html" \
    --pipeline-info     "$TD/taxprofiler/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml" \
    --analysis-type     "shotgun" \
    --sequencing-platform "illumina" \
    --classifier "kraken2 db=k2_pluspf taxpasta=$TD/taxprofiler/taxpasta/kraken2_k2_pluspf.tsv krona=$TD/taxprofiler/krona/kraken2_k2_pluspf.html" \
    --classifier "centrifuge db=p_compressed+h+v taxpasta=$TD/taxprofiler/taxpasta/centrifuge_p_compressed+h+v.tsv krona=$TD/taxprofiler/krona/centrifuge_p_compressed+h+v.html" \
    --classifier "diamond db=diamond taxpasta=$TD/taxprofiler/taxpasta/diamond_diamond.tsv" \
    --sample "sample_id=26CE100005-DNA subject_id=26CE100005 type=sample material=DNA column_kraken2=26CE100005-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE100005-DNA_p_compressed+h+v.centrifuge column_diamond=26CE100005-DNA_diamond.diamond" \
    --sample "sample_id=26CE100005-RNA subject_id=26CE100005 type=sample material=RNA column_kraken2=26CE100005-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE100005-RNA_p_compressed+h+v.centrifuge column_diamond=26CE100005-RNA_diamond.diamond" \
    --sample "sample_id=NTC-260305-DNA type=negative_ctrl material=DNA column_kraken2=NTC-260305-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC-260305-DNA_p_compressed+h+v.centrifuge column_diamond=NTC-260305-DNA_diamond.diamond" \
    --sample "sample_id=NTC-260305-RNA type=negative_ctrl material=RNA column_kraken2=NTC-260305-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC-260305-RNA_p_compressed+h+v.centrifuge column_diamond=NTC-260305-RNA_diamond.diamond" \
    --metaval "$TD/metaval" \
    --yes \
    --url "$URL" \
    "${KC_ARGS[@]}" 2>&1
  return
}

# ---------------------------------------------------------------------------
# One fullcamel ingest — the re-sequencing dataset. $run_dir is one of the
# per-run-date directories; calling this repeatedly with the same case_id and
# successive run directories is what builds a case with several analyses.
#
# Only 26CE500026 and the run's negative controls are declared. fullcamel was
# produced from a single taxprofiler run whose samplesheet also held patient
# 26CE500025; those columns are simply never referenced, and both taxpasta and
# MultiQC are read per declared sample, so they contribute nothing.
#
# No --metaval and no diamond: this dataset has neither. Cases built from it
# show two classifiers and an empty metaval view — slowowl remains the source
# of full-fidelity cases.
#
# The stored MultiQC report does still contain 26CE500025, so that tab lists
# six samples against the case's four. Cosmetic, and only in test data.
# ---------------------------------------------------------------------------
ingest_fullcamel_run() {
  local case_id="$1" run_dir="$2" order_date="$3"
  python "$INGEST_SCRIPT" taxprofiler \
    --case-id "$case_id" \
    --ticket-id "1007646" \
    --order-date "$order_date" \
    --multiqc           "$run_dir/multiqc_data.json" \
    --multiqc-report    "$run_dir/multiqc_report.html" \
    --pipeline-info     "$run_dir/nf_core_taxprofiler_software_mqc_versions.yml" \
    --analysis-type     "shotgun" \
    --sequencing-platform "illumina" \
    --classifier "kraken2 db=k2_pluspf taxpasta=$run_dir/kraken2_k2_pluspf.tsv krona=$run_dir/kraken2_k2_pluspf.html" \
    --classifier "centrifuge db=p_compressed+h+v taxpasta=$run_dir/centrifuge_p_compressed+h+v.tsv krona=$run_dir/centrifuge_p_compressed+h+v.html" \
    --sample "sample_id=26CE500026-DNA subject_id=26CE500026 type=sample material=DNA column_kraken2=26CE500026-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE500026-DNA_p_compressed+h+v.centrifuge" \
    --sample "sample_id=26CE500026-RNA subject_id=26CE500026 type=sample material=RNA column_kraken2=26CE500026-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=26CE500026-RNA_p_compressed+h+v.centrifuge" \
    --sample "sample_id=NTC260707-DNA type=negative_ctrl material=DNA column_kraken2=NTC260707-DNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC260707-DNA_p_compressed+h+v.centrifuge" \
    --sample "sample_id=NTC260707-RNA type=negative_ctrl material=RNA column_kraken2=NTC260707-RNA_k2_pluspf.kraken2.kraken2.report column_centrifuge=NTC260707-RNA_p_compressed+h+v.centrifuge" \
    --yes \
    --url "$URL" \
    "${KC_ARGS[@]}" 2>&1
  return
}

# ---------------------------------------------------------------------------
# Taxprofiler cases
# ---------------------------------------------------------------------------
if [[ "$COUNT" -gt 0 ]]; then
  echo "Ingesting $COUNT taxprofiler case(s) ($START_DATE – $END_DATE)..."
  echo ""

  success=0; fail=0

  for i in $(seq 1 "$COUNT"); do
    case_id=$(generate_case_id)
    order_date=$(random_date)
    t0=$(ms)

    output=$(ingest_taxprofiler_case "$case_id" "$order_date") && rc=0 || rc=$?

    elapsed=$(( $(ms) - t0 ))

    if [[ $rc -eq 0 ]]; then
      success=$(( success + 1 ))
      echo "  [taxprofiler $i/$COUNT] $case_id — $order_date — ${elapsed}ms (ok: $success, failed: $fail)"
    else
      fail=$(( fail + 1 ))
      echo "  [taxprofiler $i/$COUNT] $case_id — $order_date — ${elapsed}ms FAILED (ok: $success, failed: $fail)"
      echo "$output" | sed 's/^/    /'
    fi
  done

  echo ""
  echo "Taxprofiler: $success ingested, $fail failed."
  echo ""
fi

# ---------------------------------------------------------------------------
# Trana cases (16S amplicon, ONT, Emu)
# ---------------------------------------------------------------------------
if [[ "$TRANA_COUNT" -gt 0 ]]; then
  echo "Ingesting $TRANA_COUNT Trana (16S) case(s) ($START_DATE – $END_DATE)..."
  echo ""

  t_success=0; t_fail=0

  for i in $(seq 1 "$TRANA_COUNT"); do
    case_id=$(generate_case_id)
    order_date=$(random_date)
    t0=$(ms)

    output=$(python "$INGEST_SCRIPT" trana \
      --case-id "$case_id" \
      --ticket-id "1007645" \
      --order-date "$order_date" \
      --multiqc-report    "$TD_TRANA/multiqc/multiqc_report.html" \
      --pipeline-info     "$TD_TRANA/pipeline_info/software_versions.yml" \
      --analysis-type     "amplicon" \
      --sequencing-platform "nanopore" \
      --sample "sample_id=1234567890AB subject_id=1234567890AB type=sample material=DNA abundance_path=$TD_TRANA/results/1234567890AB_downsampled.fastq_rel-abundance.tsv krona_path=$TD_TRANA/krona/1234567890AB_krona.html nanoplot_unprocessed_path=$TD_TRANA/nanoplot_unprocessed/1234567890AB_nanoplot_unprocessed_NanoStats.txt nanoplot_processed_path=$TD_TRANA/nanoplot_processed/1234567890AB_nanoplot_processed_NanoStats.txt" \
      --sample "sample_id=16SNEGABC123 type=negative_ctrl material=DNA abundance_path=$TD_TRANA/results/16SNEGABC123_downsampled.fastq_rel-abundance.tsv krona_path=$TD_TRANA/krona/16SNEGABC123_krona.html nanoplot_unprocessed_path=$TD_TRANA/nanoplot_unprocessed/16SNEGABC123_nanoplot_unprocessed_NanoStats.txt nanoplot_processed_path=$TD_TRANA/nanoplot_processed/16SNEGABC123_nanoplot_processed_NanoStats.txt" \
      --yes \
      --url "$URL" \
      "${KC_ARGS[@]}" 2>&1) && rc=0 || rc=$?

    elapsed=$(( $(ms) - t0 ))

    if [[ $rc -eq 0 ]]; then
      t_success=$(( t_success + 1 ))
      echo "  [trana $i/$TRANA_COUNT] $case_id — $order_date — ${elapsed}ms (ok: $t_success, failed: $t_fail)"
    else
      t_fail=$(( t_fail + 1 ))
      echo "  [trana $i/$TRANA_COUNT] $case_id — $order_date — ${elapsed}ms FAILED (ok: $t_success, failed: $t_fail)"
      echo "$output" | sed 's/^/    /'
    fi
  done

  echo ""
  echo "Trana: $t_success ingested, $t_fail failed."
  echo ""
fi

# ---------------------------------------------------------------------------
# NTC-only cases — feed the NTC trends page.
#
# Each case is a pair of negative controls whose kraken2 profile carries
# planted persistent contaminants, so recurring-taxa detection has something to
# find. Fixtures come from generate_ntc_test_data.py; order dates are decided
# here rather than baked into the fixtures, so they stay inside the trends
# lookback window instead of ageing out.
# ---------------------------------------------------------------------------
if [[ "$NTC_COUNT" -gt 0 ]]; then
  if [[ ! -f "$NTC_GENERATOR" ]]; then
    echo "Error: NTC generator not found: $NTC_GENERATOR" >&2
    exit 1
  fi

  # Regenerate whenever the fixtures are missing or too few for this run.
  have=0
  [[ -d "$TD_NTC" ]] && have=$(find "$TD_NTC" -name 'ntc_case_*_kraken2.tsv' | wc -l | tr -d ' ')
  if [[ "$have" -lt "$NTC_COUNT" ]]; then
    echo "Generating $NTC_COUNT NTC fixture(s) (found $have)..."
    if ! python "$NTC_GENERATOR" --count "$NTC_COUNT"; then
      echo "Error: NTC fixture generation failed" >&2
      exit 1
    fi
    echo ""
  fi

  echo "Ingesting $NTC_COUNT NTC-only case(s) ($START_DATE – $END_DATE)..."
  echo ""

  n_success=0; n_fail=0

  for i in $(seq 1 "$NTC_COUNT"); do
    idx=$(printf "%02d" "$i")
    case_id="ntc-test-$idx"
    taxpasta="$TD_NTC/ntc_case_${idx}_kraken2.tsv"

    if [[ ! -f "$taxpasta" ]]; then
      n_fail=$(( n_fail + 1 ))
      echo "  [ntc $i/$NTC_COUNT] $case_id — missing fixture $taxpasta"
      continue
    fi

    # Spread evenly across the window so the trend charts have a time axis.
    offset=$(( range_days - (i - 1) * range_days / NTC_COUNT ))
    order_date=$(date -j -r $(( start_epoch + (range_days - offset) * 86400 )) "+%Y-%m-%d")
    t0=$(ms)

    output=$(python "$INGEST_SCRIPT" taxprofiler \
      --case-id "$case_id" \
      --order-date "$order_date" \
      --multiqc       "$TD/taxprofiler/multiqc/multiqc_data/multiqc_data.json" \
      --pipeline-info "$TD/taxprofiler/pipeline_info/nf_core_taxprofiler_software_mqc_versions.yml" \
      --analysis-type "shotgun" \
      --sequencing-platform "illumina" \
      --classifier "kraken2 db=k2_pluspf taxpasta=$taxpasta" \
      --sample "sample_id=NTC-DNA-$idx type=negative_ctrl material=DNA column_kraken2=NTC-DNA-${idx}_k2_pluspf.kraken2.kraken2.report" \
      --sample "sample_id=NTC-RNA-$idx type=negative_ctrl material=RNA column_kraken2=NTC-RNA-${idx}_k2_pluspf.kraken2.kraken2.report" \
      --yes \
      --url "$URL" \
      "${KC_ARGS[@]}" 2>&1) && rc=0 || rc=$?

    elapsed=$(( $(ms) - t0 ))

    if [[ $rc -eq 0 ]]; then
      n_success=$(( n_success + 1 ))
      echo "  [ntc $i/$NTC_COUNT] $case_id — $order_date — ${elapsed}ms (ok: $n_success, failed: $n_fail)"
    else
      n_fail=$(( n_fail + 1 ))
      echo "  [ntc $i/$NTC_COUNT] $case_id — $order_date — ${elapsed}ms FAILED (ok: $n_success, failed: $n_fail)"
      echo "$output" | sed 's/^/    /'
    fi
  done

  echo ""
  echo "NTC: $n_success ingested, $n_fail failed."
  echo ""
fi

# ---------------------------------------------------------------------------
# Re-sequencing pass — build cases that carry several analyses.
#
# Each case is ingested once per fullcamel run directory under the same
# --case-id, which appends an analysis instead of replacing the case, so it
# ends up in the UI as one row with the newest run current and the earlier
# ones collapsed beneath it. Because the runs are real re-sequencings of the
# same patient, the analyses differ in profiles and QC rather than being the
# same bundle replayed.
#
# These are cases of their own, not the taxprofiler pass's: fullcamel is a
# different patient from slowowl, and the ingest subject cross-check rejects
# an analysis whose subject contradicts the case's.
# ---------------------------------------------------------------------------
multi_analysis_cases=()

if [[ "$REINGEST" -gt 0 ]]; then
  runs_available="${#FULLCAMEL_RUNS[@]}"

  if [[ "$runs_available" -lt 2 ]]; then
    echo "--reingest $REINGEST requested, but $TD_FULLCAMEL holds $runs_available run"
    echo "directory(ies) — at least 2 are needed to re-sequence. Skipping."
    echo ""
  else
    # depth is the number of *extra* analyses, so it consumes depth+1 runs.
    # Unset means every run directory available.
    max_depth=$(( runs_available - 1 ))
    depth="${REINGEST_DEPTH:-$max_depth}"
    if [[ "$depth" -gt "$max_depth" ]]; then
      echo "Note: --reingest-depth $REINGEST_DEPTH exceeds the $runs_available fullcamel run(s); using $max_depth."
      depth="$max_depth"
    fi

    # Day offsets of each run from the first, taken from the directory names,
    # so a case's analyses keep the dataset's real sequencing cadence. Computed
    # once — they are the same for every case. Directories that are not named
    # YYYY-MM-DD fall back to weekly spacing rather than failing the run.
    run_offsets=()
    first_run_date="$(basename "${FULLCAMEL_RUNS[0]}")"
    for (( r = 0; r <= depth; r++ )); do
      run_date="$(basename "${FULLCAMEL_RUNS[$r]}")"
      if [[ "$first_run_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ && "$run_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        run_offsets+=("$(days_between "$first_run_date" "$run_date")")
      else
        run_offsets+=("$(( r * 7 ))")
      fi
    done

    # When the cadence does not fit inside the window,
    # random_date_with_headroom anchors the newest analysis on today and the
    # earlier ones fall outside it. Harmless for the analytics pages — they
    # restrict to the latest analysis — but say so rather than let the dates
    # look arbitrary.
    total_span="${run_offsets[$depth]}"
    if (( total_span > range_days )); then
      echo "Note: the run directories span $total_span days, more than WINDOW_DAYS=$WINDOW_DAYS."
      echo "      Earlier analyses will predate the window; the newest lands on today."
      echo ""
    fi

    total_ingests=$(( REINGEST * (depth + 1) ))
    echo "Re-sequencing $REINGEST case(s), $((depth + 1)) analysis(es) each ($total_ingests ingest(s))..."
    echo ""

    r_success=0; r_fail=0

    for (( c = 1; c <= REINGEST; c++ )); do
      case_id=$(generate_case_id)
      base_date=$(random_date_with_headroom "${run_offsets[$depth]}")
      case_analyses=0

      for (( r = 0; r <= depth; r++ )); do
        run_dir="${FULLCAMEL_RUNS[$r]}"
        order_date=$(date_plus_days "$base_date" "${run_offsets[$r]}")
        version=$(( r + 1 ))
        t0=$(ms)

        output=$(ingest_fullcamel_run "$case_id" "$run_dir" "$order_date") && rc=0 || rc=$?

        elapsed=$(( $(ms) - t0 ))

        if [[ $rc -eq 0 ]]; then
          r_success=$(( r_success + 1 ))
          case_analyses=$(( case_analyses + 1 ))
          echo "  [reingest $c/$REINGEST] $case_id v$version — $order_date — $(basename "$run_dir") — ${elapsed}ms (ok: $r_success, failed: $r_fail)"
        else
          r_fail=$(( r_fail + 1 ))
          echo "  [reingest $c/$REINGEST] $case_id v$version — $order_date — $(basename "$run_dir") — ${elapsed}ms FAILED (ok: $r_success, failed: $r_fail)"
          echo "$output" | sed 's/^/    /'
          # Stop this case here. A later run would still be accepted and would
          # silently take the failed run's version number, so the case would
          # claim a history it does not have.
          break
        fi
      done

      # Report the analyses the case really has, not the count asked for.
      if [[ "$case_analyses" -gt 1 ]]; then
        multi_analysis_cases+=("$case_id:$case_analyses")
      fi
    done

    echo ""
    echo "Re-sequencing: $r_success analysis(es) ingested, $r_fail failed."
    echo ""
  fi
fi

# ---------------------------------------------------------------------------
# Summary — name the multi-analysis cases so they're easy to find in the UI.
# ---------------------------------------------------------------------------
if [[ "${#multi_analysis_cases[@]}" -gt 0 ]]; then
  echo "Cases with multiple analyses (expand the arrow in the case list):"
  for entry in "${multi_analysis_cases[@]}"; do
    echo "  - ${entry%%:*}  (${entry##*:} analyses)"
  done
fi
