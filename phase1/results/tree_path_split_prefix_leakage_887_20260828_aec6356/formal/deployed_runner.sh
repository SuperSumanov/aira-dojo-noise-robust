#!/usr/bin/env bash
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=aec63564cb4a347a3bb6c61b38ae30850d1d755f
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot_root=${state_root}/snapshots/${snapshot_sha}
readonly root=/research/d7/spc/yzyang4/tree-path-split-prefix-leakage
readonly worktree=${root}/worktree-aec6356-v1
readonly formal=${root}/formal-aec6356-887491a-v1
readonly protocol_sha=bd8d23ebe959ea45937e93b9877c9d42a58c7840f8477d7889fd2e83c3490ade
readonly producer_sha=c91bcb07cb1f4690b32425096bf029019033d72959b69f36aad3a5ba7c22ac0c
readonly verifier_sha=974adb65b9a3da9ee9afc5650053995dd2565745158a14ec2730729a4298e414
readonly tests_sha=51465ea7d97e18df3fea5f1d15faba7790cfcadd2b89b76557d5f0b26eea6b03
readonly linear_receipt_sha=642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8
readonly native_receipt_sha=d5009a3464fb5d0597e67922bc7763af45271d0a06497b02b8fc2b7db989212d

test ! -e "$worktree"
test ! -e "$formal"
mkdir -p "$root"
git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$commit" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$commit"
test "$(git -C "$worktree" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"

readonly protocol=${worktree}/phase1/tree_path_split_prefix_leakage_v1.json
readonly producer=${worktree}/phase1/audit_tree_path_split_prefix_leakage.py
readonly verifier=${worktree}/phase1/verify_tree_path_split_prefix_leakage.py
readonly tests=${worktree}/phase1/tests/test_tree_path_split_prefix_leakage.py
readonly linear_receipt=${worktree}/phase1/results/tree_linearization_weight_887_20260828_e9f4fb9/formal/final_receipt.json
readonly native_receipt=${worktree}/phase1/results/tree_native_path_compatibility_887_20260828_cdc90e4/formal/final_receipt.json
test "$(sha256sum "$protocol" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$producer" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$verifier" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$tests" | awk '{print $1}')" = "$tests_sha"
test "$(sha256sum "$linear_receipt" | awk '{print $1}')" = "$linear_receipt_sha"
test "$(sha256sum "$native_receipt" | awk '{print $1}')" = "$native_receipt_sha"
test "$(tr -d '\r\n' < "${state_root}/LATEST")" = "$snapshot_sha"

mkdir "$formal"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "$rc" > "$formal/FAILED_RC" 2>/dev/null || true; fi; exit "$rc"' EXIT
cp /tmp/run_path_split_prefix_formal_aec6356_20260828.sh "$formal/deployed_runner.sh"
cat >"$formal/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; no HCE multifidelity Probe score-channel effect or lookahead
PREFLIGHT_02_QUESTION=exact canonical-edge crossing if shared-root-to-leaf paths are treated as independent fixed-size split records
PREFLIGHT_03_TIMING=global histogram-derived values disclosed as post-hoc; task run and fragment breadth unseen at protocol commit
PREFLIGHT_04_INPUT=fixed outcome-blind snapshot ${snapshot_sha} plus hash-bound tree linearization and tree-native receipts
PREFLIGHT_05_ESTIMANDS=uniform fixed-size 2879/360/360 path assignment; exact overlap expectations and ratio-of-expectations; anonymous group breadth
PREFLIGHT_06_SOURCE=fresh detached no-smudge exact commit ${commit}; protocol producer verifier tests and upstream receipt hashes exact
PREFLIGHT_07_CONTROLS=all-multiplicity-one two-branch hand calculation small-N exhaustive allocation cycle cross-run tamper and grouped-zero controls
PREFLIGHT_08_INDEPENDENCE=producer A/B and non-importing verifier A/B byte equality; verifier uses falling products rather than producer combinations
PREFLIGHT_09_RELATED=shared-prefix reuse and grouped splitting are prior art; only exact MLE corpus measurement and release contract allowed
PREFLIGHT_10_LEAKAGE=no prospective label grade outcome prediction accuracy effect utility or raw senior archive access
PREFLIGHT_11_SECURITY=open trace forbidden paths zero; credential filename and content zero; identity-free aggregate only
PREFLIGHT_12_RESOURCES=CPU only; GPU API model-fit base-update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=only focused full tests A/B independent equality clean worktree security and manifest success may create COMPLETE
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
(
  cd "$worktree"
  timeout 1800 "$python" -m pytest -q \
    phase1/tests/test_tree_path_split_prefix_leakage.py \
    phase1/tests/test_tree_linearization_depth_order_corollary.py \
    phase1/tests/test_tree_linearization_within_stratum_decomposition.py \
    phase1/tests/test_prospective_tree_linearization_weights.py \
    phase1/tests/test_tree_linearization_estimand_sensitivity.py \
    phase1/tests/test_tree_native_path_compatibility.py \
    phase1/tests/test_tree_native_path_compatibility_result.py
) >"$formal/focused_tests.txt" 2>"$formal/focused_tests.stderr"
test ! -s "$formal/focused_tests.stderr"
(
  cd "$worktree"
  timeout 7200 "$python" -m pytest -q phase1/tests
) >"$formal/full_tests.txt" 2>"$formal/full_tests.stderr"
test ! -s "$formal/full_tests.stderr"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"

(
  cd "$worktree"
  strace -f -qq -e trace=openat -o "$formal/producer_a_open_trace.log" \
    timeout 600 "$python" -m phase1.audit_tree_path_split_prefix_leakage \
    --state-root "$state_root" \
    --snapshot-root "$snapshot_root" \
    --repo-root "$worktree" \
    --protocol "$protocol" \
    --expect-protocol-sha256 "$protocol_sha" \
    --source-commit "$commit" \
    --out "$formal/producer_a.json"
) >"$formal/producer_a.stdout" 2>"$formal/producer_a.stderr"
test ! -s "$formal/producer_a.stderr"
(
  cd "$worktree"
  timeout 600 "$python" -m phase1.audit_tree_path_split_prefix_leakage \
    --state-root "$state_root" \
    --snapshot-root "$snapshot_root" \
    --repo-root "$worktree" \
    --protocol "$protocol" \
    --expect-protocol-sha256 "$protocol_sha" \
    --source-commit "$commit" \
    --out "$formal/producer_b.json"
) >"$formal/producer_b.stdout" 2>"$formal/producer_b.stderr"
test ! -s "$formal/producer_b.stderr"
cmp "$formal/producer_a.json" "$formal/producer_b.json"
readonly receipt_sha=$(sha256sum "$formal/producer_a.json" | awk '{print $1}')

(
  cd "$worktree"
  strace -f -qq -e trace=openat -o "$formal/verifier_a_open_trace.log" \
    timeout 600 "$python" -m phase1.verify_tree_path_split_prefix_leakage \
    --state-root "$state_root" \
    --snapshot-root "$snapshot_root" \
    --repo-root "$worktree" \
    --protocol "$protocol" \
    --expect-protocol-sha256 "$protocol_sha" \
    --receipt "$formal/producer_a.json" \
    --expect-receipt-sha256 "$receipt_sha" \
    --producer-source "$producer" \
    --expect-producer-source-sha256 "$producer_sha" \
    --source-commit "$commit" \
    --out "$formal/verifier_a.json"
) >"$formal/verifier_a.stdout" 2>"$formal/verifier_a.stderr"
test ! -s "$formal/verifier_a.stderr"
(
  cd "$worktree"
  timeout 600 "$python" -m phase1.verify_tree_path_split_prefix_leakage \
    --state-root "$state_root" \
    --snapshot-root "$snapshot_root" \
    --repo-root "$worktree" \
    --protocol "$protocol" \
    --expect-protocol-sha256 "$protocol_sha" \
    --receipt "$formal/producer_b.json" \
    --expect-receipt-sha256 "$receipt_sha" \
    --producer-source "$producer" \
    --expect-producer-source-sha256 "$producer_sha" \
    --source-commit "$commit" \
    --out "$formal/verifier_b.json"
) >"$formal/verifier_b.stdout" 2>"$formal/verifier_b.stderr"
test ! -s "$formal/verifier_b.stderr"
cmp "$formal/verifier_a.json" "$formal/verifier_b.json"

cat "$formal/producer_a_open_trace.log" "$formal/verifier_a_open_trace.log" >"$formal/combined_open_trace.log"
if grep -Ei '/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?|scorers?)(/|[^/]*\.(json|jsonl))|label[^/]*vault|score_registry|regrade' \
  "$formal/combined_open_trace.log" >"$formal/forbidden_open_hits.txt"; then
  exit 86
fi
test ! -s "$formal/forbidden_open_hits.txt"
credential_filename_hits=$(find "$formal" -type f \
  | grep -icE '(^|/)(\.env($|\.)|[^/]*(key|token|secret)[^/]*)' || true)
printf '%s\n' "$credential_filename_hits" >"$formal/credential_filename_hits.txt"
test "$credential_filename_hits" = 0
credential_content_hits=$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$formal" | wc -l || true)
printf '%s\n' "$credential_content_hits" >"$formal/credential_content_file_hits.txt"
test "$credential_content_hits" = 0

cp "$formal/producer_a.json" "$formal/final_receipt.json"
cp "$formal/verifier_a.json" "$formal/independent_verification.json"
jq '{status,classification,snapshot_sha256,inventory,global,anonymous_profiles,grouped_split_controls,pre_registered_gate,design_timing,claim_boundary,security}' \
  "$formal/producer_a.json" >"$formal/formal_summary.json"
cat >"$formal/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_fragment_path_card_parent_code_or_edge_values_emitted=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "$commit" >"$formal/source_commit.txt"
(
  cd "$formal"
  manifest_tmp=$(mktemp /tmp/path-prefix-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >"$manifest_tmp"
  printf '%s\n' TREE_PATH_SPLIT_PREFIX_LEAKAGE_FORMAL_COMPLETE >.COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "$complete_sha" >>"$manifest_tmp"
  mv "$manifest_tmp" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
chmod -R a-w "$formal"
trap - EXIT
jq '{status,classification,snapshot_sha256,inventory,global,anonymous_profiles,grouped_split_controls,security}' \
  "$formal/formal_summary.json"
sha256sum "$formal/SHA256SUMS"
