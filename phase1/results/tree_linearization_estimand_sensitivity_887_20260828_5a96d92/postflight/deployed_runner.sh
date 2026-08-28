#!/usr/bin/env bash
set -Eeo pipefail
source ~/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=5a96d92e0d638af6dba6f65c5f4a96e1ab37e9b4
readonly declaration_commit=d8214ce0a1aecdc184ef6909fc2542c3e1506719
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-linearization-estimand-sensitivity
readonly formal_worktree=${root}/formal-worktree-5a96d92
readonly postflight_worktree=${root}/postflight-worktree-5a96d92
readonly formal=${root}/formal-5a96d92-887491a-v1
readonly postflight=${root}/postflight-5a96d92-887491a-v1
readonly protocol_sha=e4e6fcdb7fe859fc3b66b660cdca65093e8859b3b754ec54bc6e2cd33d1a84c0
readonly producer_sha=13ba4f686ec0028d97e074da55e1c928bd7d2032690c92214d4cc5a7937e80c8
readonly verifier_sha=877f96f4b6db24e45cb3d8a851e0650a811487da07699aa553a1f13ffc18a48e
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697

test ! -e "${formal}"
test ! -e "${postflight}"
test ! -e "${formal_worktree}"
test ! -e "${postflight_worktree}"
mkdir -p "${root}"
git -C "${repo}" fetch fork phase1-value-critic
git -C "${repo}" cat-file -e "${commit}^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${formal_worktree}" "${commit}"
test "$(git -C "${formal_worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${formal_worktree}" status --porcelain --untracked-files=all)"

readonly protocol=${formal_worktree}/phase1/tree_linearization_estimand_sensitivity_corollary_v1.json
readonly producer=${formal_worktree}/phase1/derive_tree_linearization_estimand_sensitivity.py
readonly verifier=${formal_worktree}/phase1/verify_tree_linearization_estimand_sensitivity.py
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${verifier}" | awk '{print $1}')" = "${verifier_sha}"

mkdir "${formal}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${formal}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_linearization_estimand_sensitivity_5a96d92_20260828.sh "${formal}/deployed_runner.sh"
cat > "${formal}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; HCE multifidelity Probe score-channel effect and K>=1 remain closed
PREFLIGHT_02_GOAL=derive and independently verify the exact edge-empirical-measure sensitivity implied by the already-published path-multiplicity aggregate
PREFLIGHT_03_TIMING=exploratory values were seen before declaration; protocol frozen at ${declaration_commit}; result is a post-hoc deterministic corollary and not an independent discovery
PREFLIGHT_04_INPUTS=only two hash-bound aggregate receipts from fixed snapshot ${snapshot_sha}; no raw snapshot state
PREFLIGHT_05_FIXED=canonical and path measures exact rational formulas reconciliation checks classification and claim boundary
PREFLIGHT_06_UNIT=distinct observed child-parent edge under canonical measure versus path occurrence multiplicity measure
PREFLIGHT_07_LEAKAGE=no prospective label grade outcome prediction accuracy utility identity code raw archive or blind manifest access
PREFLIGHT_08_SOURCE=fresh detached exact implementation commit ${commit}; protocol producer verifier hashes exact and worktree clean
PREFLIGHT_09_TESTS=synthetic adversarial and neighboring focused tests plus all phase1 tests before formal receipt
PREFLIGHT_10_INDEPENDENCE=histogram-count producer versus independently expanded-edge verifier; producer A/B and verifier A/B byte equality
PREFLIGHT_11_SECURITY=strace forbidden paths zero; credential filename/content hits zero; aggregate-only outputs
PREFLIGHT_12_RESOURCES=CPU only deterministic no sampling; GPU API model_fit base_update equals 0/0/0/0; expected under ten minutes
PREFLIGHT_13_PROMOTION=formal plus second fresh-worktree postflight exact match and complete manifests required; any mismatch records FAILED_RC
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
    phase1/tests/test_tree_linearization_estimand_sensitivity.py \
    phase1/tests/test_tree_native_path_compatibility_result.py \
    phase1/tests/test_prospective_tree_linearization_weights.py
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
  --protocol "${protocol}" \
  --protocol-sha256 "${protocol_sha}" \
  --repo-root "${formal_worktree}" \
  --source-commit "${commit}" \
  --output "${formal}/producer_a.json" \
  > "${formal}/producer_a.stdout" 2> "${formal}/producer_a.stderr"
test ! -s "${formal}/producer_a.stderr"
timeout 900 "${python}" "${producer}" \
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
if grep -Ei '/prospective_decision_v1/|/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault|blind[^/]*manifest' \
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
jq '{status,classification,snapshot_sha256,protocol_sha256,source_commit,inventory,edge_measure_shift,concentration,inverse_multiplicity_correction,all_verification_checks_passed,claim_boundary,design_timing,security}' \
  "${formal}/producer_a.json" > "${formal}/formal_summary.json"
cat > "${formal}/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_or_blind_manifests_opened=false
identity_code_or_per_path_values_written=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${formal}/source_commit.txt"
(
  cd "${formal}"
  manifest_tmp=$(mktemp /tmp/estimand-sensitivity-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' AGGREGATE_ONLY_TREE_LINEARIZATION_ESTIMAND_SENSITIVITY_FORMAL_COMPLETE > .COMPLETE.tmp
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
readonly post_protocol=${postflight_worktree}/phase1/tree_linearization_estimand_sensitivity_corollary_v1.json
readonly post_producer=${postflight_worktree}/phase1/derive_tree_linearization_estimand_sensitivity.py
readonly post_verifier=${postflight_worktree}/phase1/verify_tree_linearization_estimand_sensitivity.py
test "$(sha256sum "${post_protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${post_producer}" | awk '{print $1}')" = "${producer_sha}"
test "$(sha256sum "${post_verifier}" | awk '{print $1}')" = "${verifier_sha}"

mkdir "${postflight}"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${postflight}/FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
cp /tmp/run_tree_linearization_estimand_sensitivity_5a96d92_20260828.sh "${postflight}/deployed_runner.sh"
cat > "${postflight}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only
PREFLIGHT_02_GOAL=second fresh-worktree independent reconstruction of the completed aggregate-only corollary
PREFLIGHT_03_TIMING=formal receipt known; no protocol input formula classification or output changes allowed
PREFLIGHT_04_INPUTS=immutable formal receipt and the same two hash-bound aggregate upstream receipts
PREFLIGHT_05_FIXED=protocol receipt source commit producer source and formal verifier hash exact
PREFLIGHT_06_UNIT=all distinct observed edges represented only through the fixed multiplicity histogram
PREFLIGHT_07_LEAKAGE=no label grade outcome prediction accuracy utility raw archive blind manifest identity or code access
PREFLIGHT_08_SOURCE=second fresh detached exact commit ${commit}; no shared generated state
PREFLIGHT_09_TESTS=focused synthetic and neighboring tests before postflight reconstruction
PREFLIGHT_10_INDEPENDENCE=non-importing verifier A/B byte equal and exact-match formal verifier
PREFLIGHT_11_SECURITY=strace forbidden paths zero; credential filename/content hits zero
PREFLIGHT_12_RESOURCES=CPU only; GPU API model_fit base_update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=manifest exact and every gate required; any mismatch records FAILED_RC
EOF
(
  cd "${postflight_worktree}"
  timeout 1800 "${python}" -m pytest -q \
    phase1/tests/test_tree_linearization_estimand_sensitivity.py \
    phase1/tests/test_tree_native_path_compatibility_result.py
) > "${postflight}/focused_tests.txt" 2> "${postflight}/focused_tests.stderr"
test ! -s "${postflight}/focused_tests.stderr"

strace -f -qq -e trace=openat -o "${postflight}/verifier_a_open_trace.log" \
  timeout 900 "${python}" "${post_verifier}" \
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

if grep -Ei '/prospective_decision_v1/|/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault|blind[^/]*manifest' \
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
raw_senior_archives_or_blind_manifests_opened=false
identity_code_or_per_path_values_written=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "${commit}" > "${postflight}/source_commit.txt"
(
  cd "${postflight}"
  manifest_tmp=$(mktemp /tmp/estimand-sensitivity-postflight-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > "${manifest_tmp}"
  printf '%s\n' INDEPENDENT_TREE_LINEARIZATION_ESTIMAND_SENSITIVITY_POSTFLIGHT_COMPLETE > .COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "${complete_sha}" >> "${manifest_tmp}"
  mv "${manifest_tmp}" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "${postflight_worktree}" status --porcelain --untracked-files=all)"
chmod -R a-w "${postflight}"
trap - EXIT

jq '{status,classification,snapshot_sha256,total_variation:.edge_measure_shift.total_variation,path_inverse_hhi_descriptive_diversity:.concentration.path_inverse_hhi_descriptive_diversity,path_to_canonical_diversity_retention:.concentration.path_to_canonical_diversity_retention,maximum_single_edge_mass_inflation:.concentration.maximum_single_edge_mass_inflation,all_verification_checks_passed,security}' "${formal}/final_receipt.json"
sha256sum "${formal}/SHA256SUMS" "${postflight}/SHA256SUMS"
printf '%s\n' 'access_attestation=two_fresh_worktrees_aggregate_receipts_only_no_prospective_truth_or_prediction_values'
