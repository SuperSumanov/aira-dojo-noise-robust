#!/usr/bin/env bash
set -Eeo pipefail
source ~/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=e9f4fb9cf495d6751fb77d061095f6dca312728c
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-linearization-weight
readonly worktree=${root}/prereg-e9f4fb9
readonly formal=${root}/formal-e9f4fb9-887491a-v3
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly protocol_sha=95b49fd50b75dd16fd9eefbb34557da35daa52fcecc35fce45ac89948a697feb
readonly producer_sha=cd204c1607b754f1d07861da83c829cab09df2871242a69236fe65fcc84eb09f
readonly verifier_sha=7c26338065d2258d56d2f7e3ed9b778a852f3d688655c54401492099c5a89009

test ! -e "${formal}"
test -f "${state}/LATEST"
test ! -L "${state}/LATEST"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test -d "${snapshot}"
test -d "${worktree}"
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"

readonly protocol=${worktree}/phase1/prospective_tree_linearization_weight_audit_v1.json
readonly producer=${worktree}/phase1/audit_prospective_tree_linearization_weights.py
readonly verifier=${worktree}/phase1/verify_prospective_tree_linearization_weights.py
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${verifier}" | awk '{print $1}')" = "${verifier_sha}"

mkdir "${formal}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${formal}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_linearization_weight_formal_e9f4fb9_20260828.sh "${formal}/deployed_runner.sh"

cat > "${formal}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol; closed HCE multifidelity Probe score-channel effect and K>=1 remain closed
PREFLIGHT_02_GOAL=measure whether root-to-leaf branch linearization duplicates observed shared-prefix edges and changes task or physical-run empirical weights
PREFLIGHT_03_KNOWN=canonical path tables can duplicate shared prefixes; real MLE snapshot aggregate magnitude and threshold classification were unknown at protocol freeze
PREFLIGHT_04_INPUTS=exact outcome-blind snapshot ${snapshot_sha}; registry accumulator provisional-run ledger and eligible blind manifests only
PREFLIGHT_05_FIXED=population graph rule unique-edge and branch-linearized weights support gates material thresholds ordered classification and claim boundary
PREFLIGHT_06_UNIT=all eligible endpoints; observed child-parent edges only when both endpoints are present; one physical run and task per observed edge
PREFLIGHT_07_LEAKAGE=no prospective label grade outcome prediction accuracy utility raw senior archive or identity-valued output access
PREFLIGHT_08_SOURCE=detached exact commit ${commit}; protocol producer and verifier hashes exact; clean before aggregate computation
PREFLIGHT_09_TESTS=focused neighboring regressions and all phase1 tests before aggregate computation
PREFLIGHT_10_INDEPENDENCE=producer A/B byte equality plus non-importing Kahn-traversal verifier A/B byte equality
PREFLIGHT_11_SECURITY=open trace forbidden paths zero; exact blind schema; credential filename and content hits zero; aggregate-only output
PREFLIGHT_12_RESOURCES=CPU only; PYTHONHASHSEED zero and numeric thread counts one; GPU API model_fit base_update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=v3 changes only manifest temporary-file placement after preserved v1 worktree and v2 packaging failures; all tests producer and verifier runs repeat in a new root and every scientific gate is unchanged
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

(
  cd "${worktree}"
  timeout 1800 "${python}" -m pytest -q \
    phase1/tests/test_prospective_tree_linearization_weights.py \
    phase1/tests/test_audit_prospective_code_clones.py \
    phase1/tests/test_transition_future_escrow_support.py
) > "${formal}/focused_tests.txt" 2> "${formal}/focused_tests.stderr"
test ! -s "${formal}/focused_tests.stderr"
(
  cd "${worktree}"
  timeout 3600 "${python}" -m pytest -q phase1/tests
) > "${formal}/full_tests.txt" 2> "${formal}/full_tests.stderr"
test ! -s "${formal}/full_tests.stderr"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"

strace -f -qq -e trace=openat -o "${formal}/producer_a_open_trace.log" \
  timeout 900 "${python}" "${producer}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --source-commit "${commit}" \
  --output "${formal}/producer_a.json" \
  > "${formal}/producer_a.stdout" 2> "${formal}/producer_a.stderr"
test ! -s "${formal}/producer_a.stderr"
timeout 900 "${python}" "${producer}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --source-commit "${commit}" \
  --output "${formal}/producer_b.json" \
  > "${formal}/producer_b.stdout" 2> "${formal}/producer_b.stderr"
test ! -s "${formal}/producer_b.stderr"
cmp "${formal}/producer_a.json" "${formal}/producer_b.json"
readonly receipt_sha=$(sha256sum "${formal}/producer_a.json" | awk '{print $1}')

strace -f -qq -e trace=openat -o "${formal}/verifier_a_open_trace.log" \
  timeout 900 "${python}" "${verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --receipt "${formal}/producer_a.json" \
  --expect-receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --expect-producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${formal}/verifier_a.json" \
  > "${formal}/verifier_a.stdout" 2> "${formal}/verifier_a.stderr"
test ! -s "${formal}/verifier_a.stderr"
timeout 900 "${python}" "${verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --receipt "${formal}/producer_b.json" \
  --expect-receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --expect-producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${formal}/verifier_b.json" \
  > "${formal}/verifier_b.stdout" 2> "${formal}/verifier_b.stderr"
test ! -s "${formal}/verifier_b.stderr"
cmp "${formal}/verifier_a.json" "${formal}/verifier_b.json"

cat "${formal}/producer_a_open_trace.log" "${formal}/verifier_a_open_trace.log" > "${formal}/combined_open_trace.log"
if grep -Ei '/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault' \
  "${formal}/combined_open_trace.log" > "${formal}/forbidden_open_hits.txt"; then
  exit 86
fi
test ! -s "${formal}/forbidden_open_hits.txt"

credential_filename_hits=$(find "${formal}" -type f \
  | grep -icE '(^|/)(\.env($|\.)|[^/]*(key|token|secret)[^/]*)' || true)
printf '%s\n' "${credential_filename_hits}" > "${formal}/credential_filename_hits.txt"
test "${credential_filename_hits}" = 0
credential_content_hits=$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "${formal}" | wc -l || true)
printf '%s\n' "${credential_content_hits}" > "${formal}/credential_content_file_hits.txt"
test "${credential_content_hits}" = 0

cp "${formal}/producer_a.json" "${formal}/final_receipt.json"
cp "${formal}/verifier_a.json" "${formal}/independent_verification.json"
jq '{status,classification,snapshot_sha256,protocol_sha256,source_commit,inventory,linearization,weighting,pre_registered_gate,security}' \
  "${formal}/producer_a.json" > "${formal}/formal_summary.json"
cat > "${formal}/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_card_parent_or_code_values_emitted=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${formal}/source_commit.txt"
(
  cd "${formal}"
  manifest_tmp=$(mktemp /tmp/tree-linearization-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' OUTCOME_BLIND_TREE_LINEARIZATION_WEIGHT_FORMAL_COMPLETE > .COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "${complete_sha}" >> "${manifest_tmp}"
  mv "${manifest_tmp}" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
chmod -R a-w "${formal}"
trap - EXIT
jq '{status,classification,snapshot_sha256,inventory,linearization,weighting,pre_registered_gate,security}' "${formal}/formal_summary.json"
sha256sum "${formal}/SHA256SUMS"
printf '%s\n' 'access_attestation=aggregate_only_no_prospective_truth_or_prediction_values'
