#!/usr/bin/env bash
set -Eeo pipefail
source ~/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=cdc90e472eb57189a939187399d6b5fb5ec9a5c1
readonly prereg_commit=0deb5b6e9161547bff7c2ec3566a90c5ab324fad
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-native-path-compatibility
readonly formal_worktree=${root}/formal-worktree-cdc90e4
readonly postflight_worktree=${root}/postflight-worktree-cdc90e4
readonly formal=${root}/formal-cdc90e4-887491a-v1
readonly postflight=${root}/postflight-cdc90e4-887491a-v1
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly protocol_sha=319906f0dc0525ecbc2455a5d468d5fe9e3522405455657d29f0dd5accf54511
readonly producer_sha=cc06d01a09f3b78c35dfca9ad3075beb549a2669a869870eedc7f589ceac7569
readonly verifier_sha=26b2dd7dda3d9f4b29f059d5b0e789000c78a94da79f74df09a1b97344437364

test ! -e "${formal}"
test ! -e "${postflight}"
test ! -e "${formal_worktree}"
test ! -e "${postflight_worktree}"
test -f "${state}/LATEST"
test ! -L "${state}/LATEST"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test -d "${snapshot}"
mkdir -p "${root}"
git -C "${repo}" fetch fork phase1-value-critic
git -C "${repo}" cat-file -e "${commit}^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${formal_worktree}" "${commit}"
test "$(git -C "${formal_worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${formal_worktree}" status --porcelain --untracked-files=all)"

readonly protocol=${formal_worktree}/phase1/tree_native_path_compatibility_contract_v1.json
readonly producer=${formal_worktree}/phase1/certify_tree_native_path_compatibility.py
readonly verifier=${formal_worktree}/phase1/verify_tree_native_path_compatibility.py
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${verifier}" | awk '{print $1}')" = "${verifier_sha}"

mkdir "${formal}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${formal}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_native_path_compatibility_cdc90e4_20260828.sh "${formal}/deployed_runner.sh"
cat > "${formal}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; HCE multifidelity Probe score-channel effect and K>=1 remain closed
PREFLIGHT_02_GOAL=verify that a tree-native canonical observed-edge view can coexist with a root-to-leaf compatibility view that exactly recovers the canonical empirical measure
PREFLIGHT_03_TIMING=linearization materiality was already known; remedy protocol was frozen at ${prereg_commit} before any compatibility certificate
PREFLIGHT_04_INPUTS=exact blind snapshot ${snapshot_sha}; registry accumulator run ledger eligible manifests and hash-bound aggregate upstream receipt only
PREFLIGHT_05_FIXED=population fragment path multiplicity inverse-mass exact rational rules classification and claim boundary
PREFLIGHT_06_UNIT=canonical distinct observed child-parent edge; compatibility occurrence within one contiguous same-task same-physical-run fragment path
PREFLIGHT_07_LEAKAGE=no prospective label grade outcome prediction accuracy utility raw senior archive or identity-valued artifact access
PREFLIGHT_08_SOURCE=fresh detached exact implementation commit ${commit}; protocol producer verifier hashes exact and worktree clean
PREFLIGHT_09_TESTS=new synthetic adversarial tests neighboring regressions and all phase1 tests before real certificate
PREFLIGHT_10_INDEPENDENCE=producer root-forward traversal versus non-importing verifier leaf-backtrace; producer A/B and verifier A/B byte equality
PREFLIGHT_11_SECURITY=strace forbidden paths zero; exact blind schema; credential filename and content hits zero; aggregate-only outputs
PREFLIGHT_12_RESOURCES=CPU only; deterministic no sampling; GPU API model_fit base_update equals 0/0/0/0; expected under ten minutes
PREFLIGHT_13_PROMOTION=formal plus fresh-worktree postflight exact match and complete manifests required; any mismatch leaves FAILED_RC and no promoted claim
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

"${python}" --version > "${formal}/python_version.txt" 2>&1
git --version > "${formal}/git_version.txt"
(
  cd "${formal_worktree}"
  timeout 1800 "${python}" -m pytest -q \
    phase1/tests/test_tree_native_path_compatibility.py \
    phase1/tests/test_prospective_tree_linearization_weights.py \
    phase1/tests/test_decision_predictor_estimand_panel.py
) > "${formal}/focused_tests.txt" 2> "${formal}/focused_tests.stderr"
test ! -s "${formal}/focused_tests.stderr"
(
  cd "${formal_worktree}"
  timeout 3600 "${python}" -m pytest -q phase1/tests
) > "${formal}/full_tests.txt" 2> "${formal}/full_tests.stderr"
test ! -s "${formal}/full_tests.stderr"
test -z "$(git -C "${formal_worktree}" status --porcelain --untracked-files=all)"

strace -f -qq -e trace=openat -o "${formal}/producer_a_open_trace.log" \
  timeout 900 "${python}" "${producer}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${formal_worktree}" \
  --source-commit "${commit}" \
  --output "${formal}/producer_a.json" \
  > "${formal}/producer_a.stdout" 2> "${formal}/producer_a.stderr"
test ! -s "${formal}/producer_a.stderr"
timeout 900 "${python}" "${producer}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${formal_worktree}" \
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
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${formal_worktree}" \
  --receipt "${formal}/producer_a.json" \
  --receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${formal}/verifier_a.json" \
  > "${formal}/verifier_a.stdout" 2> "${formal}/verifier_a.stderr"
test ! -s "${formal}/verifier_a.stderr"
timeout 900 "${python}" "${verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${formal_worktree}" \
  --receipt "${formal}/producer_b.json" \
  --receipt-sha256 "${receipt_sha}" \
  --producer-source "${producer}" \
  --producer-source-sha256 "${producer_sha}" \
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
jq '{status,classification,snapshot_sha256,protocol_sha256,source_commit,inventory,path_compatibility,exact_recovery,all_verification_gates_passed,security}' \
  "${formal}/producer_a.json" > "${formal}/formal_summary.json"
cat > "${formal}/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
identity_code_or_per_path_values_written=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${formal}/source_commit.txt"
(
  cd "${formal}"
  manifest_tmp=$(mktemp /tmp/tree-native-path-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' OUTCOME_BLIND_TREE_NATIVE_PATH_COMPATIBILITY_FORMAL_COMPLETE > .COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "${complete_sha}" >> "${manifest_tmp}"
  mv "${manifest_tmp}" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "${formal_worktree}" status --porcelain --untracked-files=all)"
chmod -R a-w "${formal}"
trap - EXIT

readonly formal_verifier_sha=$(sha256sum "${formal}/independent_verification.json" | awk '{print $1}')
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${postflight_worktree}" "${commit}"
test "$(git -C "${postflight_worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${postflight_worktree}" status --porcelain --untracked-files=all)"
readonly post_protocol=${postflight_worktree}/phase1/tree_native_path_compatibility_contract_v1.json
readonly post_producer=${postflight_worktree}/phase1/certify_tree_native_path_compatibility.py
readonly post_verifier=${postflight_worktree}/phase1/verify_tree_native_path_compatibility.py
test "$(sha256sum "${post_protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${post_producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${post_verifier}" | awk '{print $1}')" = "${verifier_sha}"

mkdir "${postflight}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${postflight}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_native_path_compatibility_cdc90e4_20260828.sh "${postflight}/deployed_runner.sh"
cat > "${postflight}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only
PREFLIGHT_02_GOAL=fresh-worktree independent reconstruction of the completed aggregate-only compatibility certificate
PREFLIGHT_03_TIMING=formal certificate is known; no protocol population path mass or output changes allowed
PREFLIGHT_04_INPUTS=immutable formal receipt exact fixed blind snapshot and hash-bound aggregate upstream files
PREFLIGHT_05_FIXED=protocol receipt source commit producer source and formal manifest exact
PREFLIGHT_06_UNIT=all canonical observed edges and all observed-fragment root-to-leaf paths
PREFLIGHT_07_LEAKAGE=no label grade outcome prediction accuracy utility raw senior archive or identity-valued output
PREFLIGHT_08_SOURCE=second fresh detached exact commit ${commit}; no shared generated state
PREFLIGHT_09_TESTS=focused synthetic and neighboring tests before postflight reconstruction
PREFLIGHT_10_INDEPENDENCE=non-importing leaf-backtrace verifier A/B byte equal and exact-match formal verifier
PREFLIGHT_11_SECURITY=strace forbidden paths zero; credential filename and content hits zero
PREFLIGHT_12_RESOURCES=CPU only; GPU API model_fit base_update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=manifest exact and every gate required; any mismatch records FAILED_RC
EOF
(
  cd "${postflight_worktree}"
  timeout 1800 "${python}" -m pytest -q \
    phase1/tests/test_tree_native_path_compatibility.py \
    phase1/tests/test_prospective_tree_linearization_weights.py
) > "${postflight}/focused_tests.txt" 2> "${postflight}/focused_tests.stderr"
test ! -s "${postflight}/focused_tests.stderr"

strace -f -qq -e trace=openat -o "${postflight}/verifier_a_open_trace.log" \
  timeout 900 "${python}" "${post_verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${post_protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${postflight_worktree}" \
  --receipt "${formal}/final_receipt.json" \
  --receipt-sha256 "${receipt_sha}" \
  --producer-source "${post_producer}" \
  --producer-source-sha256 "${producer_sha}" \
  --source-commit "${commit}" \
  --output "${postflight}/verifier_a.json" \
  > "${postflight}/verifier_a.stdout" 2> "${postflight}/verifier_a.stderr"
test ! -s "${postflight}/verifier_a.stderr"
timeout 900 "${python}" "${post_verifier}" \
  --state-root "${state}" \
  --snapshot-root "${snapshot}" \
  --protocol "${post_protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${postflight_worktree}" \
  --receipt "${formal}/final_receipt.json" \
  --receipt-sha256 "${receipt_sha}" \
  --producer-source "${post_producer}" \
  --producer-source-sha256 "${producer_sha}" \
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
identity_code_or_per_path_values_written=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${postflight}/source_commit.txt"
(
  cd "${postflight}"
  manifest_tmp=$(mktemp /tmp/tree-native-path-postflight-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' INDEPENDENT_TREE_NATIVE_PATH_COMPATIBILITY_POSTFLIGHT_COMPLETE > .COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "${complete_sha}" >> "${manifest_tmp}"
  mv "${manifest_tmp}" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "${postflight_worktree}" status --porcelain --untracked-files=all)"
chmod -R a-w "${postflight}"
trap - EXIT

jq '{status,classification,snapshot_sha256,inventory,path_compatibility,exact_recovery,all_verification_gates_passed,security}' "${formal}/formal_summary.json"
sha256sum "${formal}/SHA256SUMS" "${postflight}/SHA256SUMS"
printf '%s\n' 'access_attestation=two_fresh_worktrees_aggregate_only_no_prospective_truth_or_prediction_values'
