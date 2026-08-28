#!/usr/bin/env bash
set -Eeo pipefail
source ~/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=e9f4fb9cf495d6751fb77d061095f6dca312728c
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-linearization-weight
readonly worktree=${root}/postflight-worktree-e9f4fb9
readonly formal=${root}/formal-e9f4fb9-887491a-v3
readonly postflight=${root}/postflight-e9f4fb9-887491a-v1
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly protocol_sha=95b49fd50b75dd16fd9eefbb34557da35daa52fcecc35fce45ac89948a697feb
readonly producer_sha=cd204c1607b754f1d07861da83c829cab09df2871242a69236fe65fcc84eb09f
readonly receipt_sha=642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8
readonly formal_verifier_sha=11b255093055941c5747d238cc1bc00b4a3d81a7216dd6efb701da85c9a9045d

test -f "${formal}/COMPLETE"
test ! -e "${formal}/FAILED_RC"
(
  cd "${formal}"
  sha256sum -c SHA256SUMS >/dev/null
)
test "$(sha256sum "${formal}/final_receipt.json" | awk '{print $1}')" = "${receipt_sha}"
test "$(sha256sum "${formal}/independent_verification.json" | awk '{print $1}')" = "${formal_verifier_sha}"
test ! -e "${worktree}"
test ! -e "${postflight}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}"
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"

readonly protocol=${worktree}/phase1/prospective_tree_linearization_weight_audit_v1.json
readonly producer=${worktree}/phase1/audit_prospective_tree_linearization_weights.py
readonly verifier=${worktree}/phase1/verify_prospective_tree_linearization_weights.py
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${producer}" | awk '{print $1}')" = "${producer_sha}"
mkdir "${postflight}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${postflight}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_linearization_postflight_e9f4fb9_20260828.sh "${postflight}/deployed_runner.sh"
cat > "${postflight}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only
PREFLIGHT_02_GOAL=fresh-worktree independent reconstruction of the completed aggregate-only tree-linearization receipt
PREFLIGHT_03_KNOWN=formal classification and aggregates are now known; no threshold population or implementation changes are allowed
PREFLIGHT_04_INPUTS=immutable formal v3 receipt and exact fixed blind snapshot only
PREFLIGHT_05_FIXED=protocol receipt source commit producer source hash and formal manifest exact
PREFLIGHT_06_UNIT=all eligible endpoints and observed same-run same-task edges under frozen graph rules
PREFLIGHT_07_LEAKAGE=no label grade outcome prediction accuracy utility or raw senior archive input
PREFLIGHT_08_SOURCE=fresh detached exact commit ${commit}; LFS smudge skipped only for unrelated historical pointers
PREFLIGHT_09_TESTS=independent verifier focused tests before postflight reconstruction
PREFLIGHT_10_INDEPENDENCE=verifier does not import producer; A/B byte equal and exact-match formal verifier
PREFLIGHT_11_SECURITY=open trace forbidden paths zero; credential filename and content hits zero
PREFLIGHT_12_RESOURCES=CPU only; GPU API model_fit base_update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=manifest exact and all gates required; any mismatch fails closed
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
(
  cd "${worktree}"
  "${python}" -m pytest -q phase1/tests/test_prospective_tree_linearization_weights.py
) > "${postflight}/focused_tests.txt" 2> "${postflight}/focused_tests.stderr"
test ! -s "${postflight}/focused_tests.stderr"

strace -f -qq -e trace=openat -o "${postflight}/verifier_a_open_trace.log" \
  timeout 900 "${python}" "${verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --receipt "${formal}/final_receipt.json" \
  --expect-receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --expect-producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${postflight}/verifier_a.json" \
  > "${postflight}/verifier_a.stdout" 2> "${postflight}/verifier_a.stderr"
test ! -s "${postflight}/verifier_a.stderr"
timeout 900 "${python}" "${verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --expect-protocol-sha256 "${protocol_sha}" \
  --receipt "${formal}/final_receipt.json" \
  --expect-receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --expect-producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${postflight}/verifier_b.json" \
  > "${postflight}/verifier_b.stdout" 2> "${postflight}/verifier_b.stderr"
test ! -s "${postflight}/verifier_b.stderr"
cmp "${postflight}/verifier_a.json" "${postflight}/verifier_b.json"
cmp "${postflight}/verifier_a.json" "${formal}/independent_verification.json"
test "$(sha256sum "${postflight}/verifier_a.json" | awk '{print $1}')" = "${formal_verifier_sha}"

if grep -Ei '/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault' \
  "${postflight}/verifier_a_open_trace.log" > "${postflight}/forbidden_open_hits.txt"; then
  exit 86
fi
test ! -s "${postflight}/forbidden_open_hits.txt"
credential_filename_hits=$(find "${postflight}" -type f \
  | grep -icE '(^|/)(\.env($|\.)|[^/]*(key|token|secret)[^/]*)' || true)
printf '%s\n' "${credential_filename_hits}" > "${postflight}/credential_filename_hits.txt"
test "${credential_filename_hits}" = 0
credential_content_hits=$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "${postflight}" | wc -l || true)
printf '%s\n' "${credential_content_hits}" > "${postflight}/credential_content_file_hits.txt"
test "${credential_content_hits}" = 0
cat > "${postflight}/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_card_parent_or_code_values_emitted=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${postflight}/source_commit.txt"
(
  cd "${postflight}"
  manifest_tmp=$(mktemp /tmp/tree-linearization-postflight-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' INDEPENDENT_TREE_LINEARIZATION_POSTFLIGHT_COMPLETE > .COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "${complete_sha}" >> "${manifest_tmp}"
  mv "${manifest_tmp}" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
chmod -R a-w "${postflight}"
trap - EXIT
jq '{status,classification,snapshot_sha256,observed_unique_edges,branch_linearized_edge_occurrences,all_hard_gates_passed,security}' "${postflight}/verifier_a.json"
sha256sum "${postflight}/SHA256SUMS"
printf '%s\n' 'access_attestation=fresh_worktree_aggregate_only_independent_postflight'
