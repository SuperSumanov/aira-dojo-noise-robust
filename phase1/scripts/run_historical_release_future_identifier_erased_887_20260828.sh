#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_historical_release_future_identifier_erased_887_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly output=$1
readonly expected_commit=$2
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
test ! -e "${output}"
mkdir -p "${output}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${output}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

cat > "${output}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=complete byte-reproducible v11 release to exact 435-run future identifier-erased overlap; PASS
03_population=16012 historical endpoints/667 runs/25 tasks versus 11906 future endpoints/435 runs/34 tasks; PASS
04_prior_disclosure=known 5519-endpoint train subset zero-link result disclosed; full-release result unread; PASS
05_representation=python_token_identifier_erased_v1 with 17/20 primary and 19/20 non-rescuing sensitivity; PASS
06_classification=ZERO then LOW_WITH_EXCEPTIONS then GATE_FAIL in frozen order; PASS
07_repetitions=producer A/B and non-importing independent verifier A/B, byte identity required; PASS
08_controls=256x256 prefix-join versus brute-force plus focused adversarial/schema tests; PASS
09_hashes=protocol,full release,release receipt,snapshot inputs,source commit,all dependencies bound; PASS
10_randomness=none,PYTHONHASHSEED=0,numeric threads=1; PASS
11_resources=CPU only,5400-second command timeout,32-GiB virtual memory,GPU/API/model-fit/base-update 0/0/0/0; PASS
11b_resource_revision=v1 producer A timed out at 1800 seconds with rc 124,no result file or stderr,scientific contract unchanged; PASS
12_security=no raw senior archive or prospective label/outcome/prediction input,no identities emitted,credential scans; PASS
13_failure=immutable FAILED_RC,no population,representation,threshold,gate,subset,task or classification rescue; PASS
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
test "$(sha256sum phase1/cards_current_v11.jsonl | awk '{print $1}')" = \
  6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
test "$(stat -c %s phase1/cards_current_v11.jsonl)" = 305750663

timeout 5400s "${python}" -m pytest -q \
  phase1/tests/test_historical_release_future_identifier_erased_overlap.py \
  phase1/tests/test_historical_train_future_identifier_erased_overlap.py \
  > "${output}/focused_tests.txt"
timeout 5400s "${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

producer=(
  "${python}" -m phase1.audit_historical_release_future_identifier_erased_overlap
  --repo-root .
  --state-root "${state}"
  --snapshot-root "${snapshot}"
  --source-commit "${expected_commit}"
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
)
timeout 5400s "${producer[@]}" --output "${output}/producer_a.json" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
timeout 5400s "${producer[@]}" --output "${output}/producer_b.json" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
test ! -s "${output}/producer_a.stderr"
test ! -s "${output}/producer_b.stderr"
cmp "${output}/producer_a.json" "${output}/producer_b.json"
producer_sha=$(sha256sum "${output}/producer_a.json" | awk '{print $1}')

verifier=(
  "${python}" -m phase1.verify_historical_release_future_identifier_erased_overlap
  --repo-root .
  --state-root "${state}"
  --snapshot-root "${snapshot}"
  --receipt "${output}/producer_a.json"
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
)
timeout 5400s "${verifier[@]}" --output "${output}/verifier_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
timeout 5400s "${verifier[@]}" --output "${output}/verifier_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
test ! -s "${output}/verifier_a.stderr"
test ! -s "${output}/verifier_b.stderr"
cmp "${output}/verifier_a.json" "${output}/verifier_b.json"

jq -e --arg snapshot "${snapshot_sha}" '
  .status == "PROVISIONAL_HISTORICAL_RELEASE_FUTURE_OVERLAP_AUDIT_COMPLETE"
  and (.classification == "ZERO_IDENTIFIER_ERASED_RELEASE_LINKS"
       or .classification == "LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS"
       or .classification == "RELEASE_SPLIT_INTEGRITY_GATE_FAIL")
  and .snapshot_sha256 == $snapshot
  and .historical_scope.endpoints == 16012
  and .historical_scope.runs == 667
  and .historical_scope.tasks == 25
  and .prospective_scope.observed_runs == 435
  and .prospective_scope.observed_endpoints == 11906
  and .prospective_scope.observed_tasks == 34
  and .prospective_scope.closure_provided == false
  and .security.historical_label_or_observation_fields_used == false
  and .security.prospective_label_vault_opened == false
  and .security.prospective_outcome_files_opened == []
  and .security.prediction_values_read == false
  and .security.code_or_identity_values_emitted == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
' "${output}/producer_a.json" > /dev/null
jq -e --arg sha "${producer_sha}" '
  .status == "INDEPENDENTLY_VERIFIED_HISTORICAL_RELEASE_FUTURE_OVERLAP"
  and .producer_receipt_sha256 == $sha
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
' "${output}/verifier_a.json" > /dev/null
test "$(jq -r .classification "${output}/producer_a.json")" = \
  "$(jq -r .classification "${output}/verifier_a.json")"

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
raw_senior_archives_opened=false
historical_label_or_observation_fields_used=false
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
jq '{status,classification,historical_scope,prospective_scope:{observed_runs,observed_endpoints,observed_tasks,closure_provided},historical_fingerprinting,prospective_fingerprinting,primary_jaccard_0_85,strict_jaccard_0_95,pre_registered_gate}' \
  "${output}/producer_a.json"
sha256sum "${output}/producer_a.json" "${output}/verifier_a.json" \
  "${output}/SHA256SUMS"
printf '%s\n' FORMAL_HISTORICAL_RELEASE_FUTURE_IDENTIFIER_ERASED_COMPLETE
