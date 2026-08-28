#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'usage: run_tree_content_selective_parent_recovery_887_20260828.sh OUTPUT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly output=$1
readonly expected_commit=$2
readonly repo_root=$(git rev-parse --show-toplevel)
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly protocol=phase1/tree_content_selective_parent_recovery_887_protocol_v1.json
readonly protocol_sha=a9fe1b26cec20b6725f19e30e605755aa2e854033ec0462c4a39d18e0f80f97c
readonly producer=phase1/audit_tree_content_selective_parent_recovery_887.py
readonly producer_sha=b30ecf9aca9f6e763ee7b03178f56f4749bfa84b81cd2db46e7a7f77b21b055e
readonly verifier=phase1/verify_tree_content_selective_parent_recovery_887.py
readonly verifier_sha=b53ee68eeb8d40bd365c188f1b6dc635c5307a130e415c2f90726bd100f85ffb
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test "$(git rev-parse HEAD)" = "${expected_commit}"
test "${repo_root}" = "$(pwd -P)"
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
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${verifier}" | awk '{print $1}')" = "${verifier_sha}"
test -d "${state_root}/snapshots/${snapshot}"
test ! -L "${state_root}/snapshots/${snapshot}"

cat > "${output}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=can an earlier-run-selected Jaccard-margin reject rule recover recorded parents on later run-disjoint development data; PASS
03_protocol=${protocol},sha256 ${protocol_sha}; PASS
04_population=immutable disclosed snapshot ${snapshot},train runs 1-290,test runs 291-435; PASS
05_selection=train precision at least 99/100 and support at least 500,maximize accepted edges,test labels unavailable to selection; PASS
06_primary=test precision at least 49/50,coverage at least 1/2,error at most half unfiltered plus breadth gates; PASS
07_denominators=all-alternative micro,uniform one-wrong-per-child,and adversarial child reported separately; PASS
08_controls=recorded parent masked,unique top only,ties rejected,exact fractions; PASS
09_reproducibility=producer A/B,non-importing verifier A/B,focused/full tests,hash seeds 0/1; PASS
10_integrity=exact commit,protocol,producer,verifier,snapshot summary,registry,ledger and run-split hashes; PASS
11_security=strace file/network audit and boundary-aware credential scan; PASS
12_forbidden=no prospective truth,prediction,accuracy,utility,Target-522 profile,raw archive,GPU/API/model fit/base update; PASS
13_interpretation=development masked-parent audit only,no orphan repair or semantic-lineage truth; PASS
EOF

export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432
git status --porcelain=v1 > "${output}/git_status_before.txt"
test ! -s "${output}/git_status_before.txt"
timeout 1800s "${python}" -m pytest -q \
  phase1/tests/test_tree_content_selective_parent_recovery_887.py \
  phase1/tests/test_tree_content_lineage_forward_target522_audit.py \
  > "${output}/focused_tests.txt"
timeout 1800s "${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

producer_command=(
  "${python}" -m phase1.audit_tree_content_selective_parent_recovery_887
  --repo-root "${repo_root}"
  --state-root "${state_root}"
  --snapshot "${snapshot}"
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
  --source-commit "${expected_commit}"
)
PYTHONHASHSEED=0 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "${output}/producer_a.trace" \
  "${producer_command[@]}" --output "${output}/producer_a.json" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${producer_command[@]}" --output "${output}/producer_b.json" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
test ! -s "${output}/producer_a.stdout"
test ! -s "${output}/producer_a.stderr"
test ! -s "${output}/producer_b.stdout"
test ! -s "${output}/producer_b.stderr"
cmp "${output}/producer_a.json" "${output}/producer_b.json"
result_sha=$(sha256sum "${output}/producer_a.json" | awk '{print $1}')

verifier_command=(
  "${python}" -m phase1.verify_tree_content_selective_parent_recovery_887
  --repo-root "${repo_root}"
  --state-root "${state_root}"
  --snapshot "${snapshot}"
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
  --source-commit "${expected_commit}"
  --result "${output}/producer_a.json"
  --expect-result-sha256 "${result_sha}"
)
PYTHONHASHSEED=0 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "${output}/verifier_a.trace" \
  "${verifier_command[@]}" --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${verifier_command[@]}" --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
test ! -s "${output}/verifier_a.stdout"
test ! -s "${output}/verifier_a.stderr"
test ! -s "${output}/verifier_b.stdout"
test ! -s "${output}/verifier_b.stderr"
cmp "${output}/verification_a.json" "${output}/verification_b.json"

for trace in "${output}"/producer_a.trace* "${output}"/verifier_a.trace*; do
  test -f "${trace}"
  forbidden_hits=$(grep -Eic \
    '/external/senior_data/|label_vault|outcome_vault|/outcomes?/|regrade|pair_predictions\.jsonl|endpoint_scores\.csv|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|tree-within-stratum-forward-target522/.*/candidate|/\.env([" ]|$)' \
    "${trace}" || true)
  network_hits=$(grep -Eic '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' "${trace}" || true)
  test "${forbidden_hits}" = 0
  test "${network_hits}" = 0
done

jq -e '
  .security.task_run_card_parent_code_or_per_edge_values_emitted == false
  and .security.prospective_label_grade_outcome_prediction_values_read == false
  and .security.raw_senior_archives_opened == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
  and .split_bindings.run_overlap == 0
' "${output}/producer_a.json" > /dev/null
jq -e '
  .producer_imported == false
  and .task_run_card_parent_code_or_per_edge_values_emitted == false
  and .prospective_label_grade_outcome_prediction_values_read == false
  and .raw_senior_archives_opened == false
  and .gpu_api_model_fit_base_update == [0,0,0,0]
' "${output}/verification_a.json" > /dev/null

filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=security_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
printf '%s\n' \
  'forbidden_path_hits=0' \
  'network_hits=0' \
  'credential_filename_hits=0' \
  'boundary_aware_credential_content_file_hits=0' \
  'prospective_label_grade_outcome_prediction_values_read=false' \
  'raw_senior_archives_opened=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' \
  > "${output}/security_receipt.txt"

jq '{
  protocol,
  status,
  classification,
  source_commit,
  protocol_sha256,
  snapshot_bindings,
  split_bindings,
  inventory,
  threshold_selection,
  train_profile,
  test_profile,
  test_breadth,
  test_wrong_pointer_controls,
  support_gates,
  primary_gates,
  claim_boundary,
  security
}' "${output}/producer_a.json" > "${output}/formal_summary.json"
git status --porcelain=v1 > "${output}/git_status_after.txt"
test ! -s "${output}/git_status_after.txt"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${output}"
trap - EXIT
jq -c '{classification,inventory,threshold_selection,test_profile,test_breadth,test_wrong_pointer_controls,support_gates,primary_gates}' \
  "${output}/formal_summary.json"
sha256sum "${output}/producer_a.json" "${output}/verification_a.json" "${output}/SHA256SUMS"
