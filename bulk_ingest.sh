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
#   bash bulk_ingest.sh 10 3 --reingest 4         # 4 of the 10 get a second analysis
#   bash bulk_ingest.sh 6 0 --reingest 2 --reingest-depth 2
#                                                 # 2 cases end up with three analyses each
#   bash bulk_ingest.sh 0 0 --ntc 20              # 20 NTC-only cases for the trends page
#   WINDOW_DAYS=30 bash bulk_ingest.sh            # tighter date spread
#
# A case can be sequenced more than once, so re-ingesting the same --case-id
# appends an analysis rather than replacing the case. --reingest exercises that:
# it re-runs N of the freshly created taxprofiler cases, each extra analysis
# dated a week later than the last, which is what the UI groups under the
# current run. The sample specs (and therefore subject_id) are reused verbatim,
# so the ingest subject cross-check passes.
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
REINGEST_DEPTH=1
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

for n in "$REINGEST" "$REINGEST_DEPTH" "$NTC_COUNT"; do
  if ! [[ "$n" =~ ^[0-9]+$ ]]; then
    echo "Error: --reingest, --reingest-depth and --ntc take a non-negative integer (got: '$n')" >&2
    exit 1
  fi
done
if [[ "$REINGEST_DEPTH" -lt 1 ]]; then
  echo "Error: --reingest-depth must be at least 1" >&2
  exit 1
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

# Later order date for a re-sequencing, so version order is visible in the UI.
date_plus_days() {
  local base="$1" days="$2" base_epoch
  base_epoch=$(date -j -f "%Y-%m-%d" "$base" "+%s")
  date -j -r $(( base_epoch + days * 86400 )) "+%Y-%m-%d"
  return
}

ms() { python3 -c "import time; print(int(time.time()*1000))"; return; }

# ---------------------------------------------------------------------------
# One taxprofiler ingest. Extracted because --reingest runs the identical
# invocation again against an existing case to append an analysis; the sample
# specs (and their subject_id) must match exactly or the subject cross-check
# rejects the bundle.
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
# Taxprofiler cases
# ---------------------------------------------------------------------------
# Populated by the taxprofiler pass; consumed by --reingest below.
ingested_case_ids=()
ingested_dates=()

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
      # Remember what landed so --reingest can add analyses to real cases.
      ingested_case_ids+=("$case_id")
      ingested_dates+=("$order_date")
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
# Re-sequencing pass — append analyses to cases the taxprofiler pass created.
#
# Re-running the same --case-id adds an analysis instead of replacing the case,
# so these end up in the UI as one row with the newest run current and the
# earlier ones collapsed beneath it.
# ---------------------------------------------------------------------------
multi_analysis_cases=()

if [[ "$REINGEST" -gt 0 ]]; then
  available="${#ingested_case_ids[@]}"

  if [[ "$available" -eq 0 ]]; then
    echo "--reingest $REINGEST requested, but no taxprofiler cases were ingested — skipping."
    echo ""
  else
    targets="$REINGEST"
    if [[ "$targets" -gt "$available" ]]; then
      echo "Note: --reingest $REINGEST exceeds the $available case(s) ingested; using $available."
      targets="$available"
    fi

    total_extra=$(( targets * REINGEST_DEPTH ))
    echo "Re-sequencing $targets case(s), $REINGEST_DEPTH extra analysis(es) each ($total_extra ingest(s))..."
    echo ""

    r_success=0; r_fail=0

    for (( c = 0; c < targets; c++ )); do
      case_id="${ingested_case_ids[$c]}"
      base_date="${ingested_dates[$c]}"
      case_extra=0

      for (( d = 1; d <= REINGEST_DEPTH; d++ )); do
        # Each re-run is a week later than the previous, so the version order
        # and the order-date order agree.
        order_date=$(date_plus_days "$base_date" $(( d * 7 )))
        version=$(( d + 1 ))
        t0=$(ms)

        output=$(ingest_taxprofiler_case "$case_id" "$order_date") && rc=0 || rc=$?

        elapsed=$(( $(ms) - t0 ))

        if [[ $rc -eq 0 ]]; then
          r_success=$(( r_success + 1 ))
          case_extra=$(( case_extra + 1 ))
          echo "  [reingest $((c + 1))/$targets] $case_id v$version — $order_date — ${elapsed}ms (ok: $r_success, failed: $r_fail)"
        else
          r_fail=$(( r_fail + 1 ))
          echo "  [reingest $((c + 1))/$targets] $case_id v$version — $order_date — ${elapsed}ms FAILED (ok: $r_success, failed: $r_fail)"
          echo "$output" | sed 's/^/    /'
        fi
      done

      # Only list cases that actually gained an analysis, and report the count
      # they really have rather than the count that was asked for.
      if [[ "$case_extra" -gt 0 ]]; then
        multi_analysis_cases+=("$case_id:$(( case_extra + 1 ))")
      fi
    done

    echo ""
    echo "Re-sequencing: $r_success extra analysis(es) ingested, $r_fail failed."
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
