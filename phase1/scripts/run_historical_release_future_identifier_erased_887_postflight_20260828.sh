#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 3 || ! $3 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_historical_release_future_identifier_erased_887_postflight_20260828.sh FORMAL_ROOT OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly formal=$1
readonly output=$2
readonly expected_commit=$3
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly protocol=phase1/historical_release_future_identifier_erased_887_protocol_v1_resource_r2.json
readonly protocol_sha=52390b9a78893775db70a85dbda8e98132363cbb997e7006eab0646e9c0f73b3
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test "$(git rev-parse HEAD)" = "${expected_commit}"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test -f "${formal}/COMPLETE"
test ! -e "${formal}/FAILED_RC"
test ! -e "${output}"
(
  cd "${formal}"
  sha256sum -c SHA256SUMS > /dev/null
)
mkdir -p "${output}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${output}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

cat > "${output}/postflight_preflight.txt" <<EOF
role=independent postflight; verifier only; producer is not imported or rerun
formal=${formal}
commit=${expected_commit}
snapshot=${snapshot_sha}
population=complete v11 release versus exact 435-run future
checks=formal manifest,source binding,verifier A/B,formal verifier byte identity,classification and security contract
resources=CPU only;5400-second command timeout;GPU/API/model_fit/base_update=0/0/0/0
resource_revision=v1 producer A timed out at 1800 seconds with rc 124,no result file or stderr,scientific contract unchanged
failure=immutable FAILED_RC;no result-dependent rescue
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

git status --porcelain=v1 > "${output}/git_status_before.txt"
test ! -s "${output}/git_status_before.txt"
test "$(jq -r .source_commit "${formal}/producer_a.json")" = "${expected_commit}"
producer_sha=$(sha256sum "${formal}/producer_a.json" | awk '{print $1}')
verifier=(
  "${python}" -m phase1.verify_historical_release_future_identifier_erased_overlap
  --repo-root .
  --state-root "${state}"
  --snapshot-root "${snapshot}"
  --receipt "${formal}/producer_a.json"
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
)
timeout 5400s "${verifier[@]}" --output "${output}/independent_a.json" \
  > "${output}/independent_a.stdout" 2> "${output}/independent_a.stderr"
timeout 5400s "${verifier[@]}" --output "${output}/independent_b.json" \
  > "${output}/independent_b.stdout" 2> "${output}/independent_b.stderr"
test ! -s "${output}/independent_a.stderr"
test ! -s "${output}/independent_b.stderr"
cmp "${output}/independent_a.json" "${output}/independent_b.json"
cmp "${output}/independent_a.json" "${formal}/verifier_a.json"

jq -e --arg producer "${producer_sha}" '
  .status == "INDEPENDENTLY_VERIFIED_HISTORICAL_RELEASE_FUTURE_OVERLAP"
  and .producer_receipt_sha256 == $producer
  and .historical_endpoints == 16012
  and .historical_runs == 667
  and .prospective_endpoints == 11906
  and .prospective_runs == 435
  and .producer_aggregate_matches == true
  and .subset_bruteforce_matches == true
  and .imports_new_producer_code == false
  and .raw_senior_archives_opened == false
  and .historical_label_or_observation_fields_used == false
  and .prospective_outcomes_read == false
  and .prediction_values_read == false
  and .gpu_api_model_fit_base_update == [0,0,0,0]
' "${output}/independent_a.json" > /dev/null
test "$(jq -r .classification "${formal}/producer_a.json")" = \
  "$(jq -r .classification "${output}/independent_a.json")"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"

credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=credential_scan_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
cat > "${output}/access_attestation.txt" <<EOF
boundary_aware_credential_file_hits=0
credential_filename_hits=0
producer_rerun=false
new_producer_imported=false
raw_senior_archives_opened=false
prospective_label_outcome_prediction_values_read=false
task_run_card_code_or_edge_identities_emitted=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

git status --porcelain=v1 > "${output}/git_status_after.txt"
test ! -s "${output}/git_status_after.txt"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${output}"
trap - EXIT
jq '{status,classification,historical_endpoints,historical_runs,prospective_endpoints,prospective_runs,primary_candidate_pairs,primary_near_duplicate_pairs,strict_near_duplicate_pairs,producer_aggregate_matches,subset_bruteforce_matches}' \
  "${output}/independent_a.json"
sha256sum "${output}/independent_a.json" "${output}/SHA256SUMS"
printf '%s\n' HISTORICAL_RELEASE_FUTURE_IDENTIFIER_ERASED_POSTFLIGHT_COMPLETE
