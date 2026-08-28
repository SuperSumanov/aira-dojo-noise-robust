#!/usr/bin/env bash
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=333a3b66ca5399dcf87e586be1339423917d1264
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-linearization-depth-order
readonly worktree=${root}/worktree-333a3b6-v1
readonly formal=${root}/formal-333a3b6-887491a-v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly protocol_sha=29a4e060ef958892b3e2c3f5dccf6258ef87f9bc5ea7b94923551d19d8a2e7e3
readonly producer_sha=2d314d4b1c5f87e9c84782f43cc33ca079b4650182d7ea6b8d79b1deabee5321
readonly verifier_sha=f240a57cbb843ddd5200cd6112a35cbc9a1f2115525878d3e5c1f9a2a21ebb15
readonly tests_sha=146b0721b7f705596352e9c286da83ed848a80c80e912ad389986b53c469b524
readonly input_sha=642e9fd793950d4dfd082669df164be0781bd13847f35d6483ebd8611a136ea8

test ! -e "$worktree"
test ! -e "$formal"
mkdir -p "$root"
git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$commit" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$commit"
test "$(git -C "$worktree" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"

readonly protocol=${worktree}/phase1/tree_linearization_depth_order_corollary_v1.json
readonly producer=${worktree}/phase1/derive_tree_linearization_depth_order_corollary.py
readonly verifier=${worktree}/phase1/verify_tree_linearization_depth_order_corollary.py
readonly tests=${worktree}/phase1/tests/test_tree_linearization_depth_order_corollary.py
readonly source_receipt=${worktree}/phase1/results/tree_linearization_weight_887_20260828_e9f4fb9/formal/final_receipt.json
test "$(sha256sum "$protocol" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$producer" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$verifier" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$tests" | awk '{print $1}')" = "$tests_sha"
test "$(sha256sum "$source_receipt" | awk '{print $1}')" = "$input_sha"

mkdir "$formal"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "$rc" > "$formal/FAILED_RC" 2>/dev/null || true; fi; exit "$rc"' EXIT
cp /tmp/run_depth_order_formal_333a3b6_20260828.sh "$formal/deployed_runner.sh"
cat >"$formal/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; no HCE multifidelity Probe score-channel effect or lookahead
PREFLIGHT_02_QUESTION=exact post-hoc interpretation of how root-to-leaf enumeration changes the logged edge-depth distribution
PREFLIGHT_03_TIMING=all source depth counts TV mean CDF crossing and quantiles were seen before declaration; no preregistered or confirmatory discovery claim
PREFLIGHT_04_INPUT=one hash-bound aggregate receipt ${input_sha}; no raw snapshot identity or prospective value input
PREFLIGHT_05_ESTIMANDS=canonical-edge and path-frequency depth distributions exact FOSD mean shift TV CDF gaps sign crossings and nearest-rank quantiles
PREFLIGHT_06_SOURCE=fresh detached no-smudge exact commit ${commit}; protocol producer verifier and tests hashes exact
PREFLIGHT_07_TESTS=synthetic attacks and official aggregate test plus neighboring tree tests followed by all phase1 tests before formal derivation
PREFLIGHT_08_INDEPENDENCE=producer A/B and non-importing verifier A/B byte equality; verifier uses integer cross-products rather than producer PMF construction
PREFLIGHT_09_RELATED=Tree Training and TreeAdv already cover shared-prefix duplication and root-scale normalization; only MLE empirical release corollary allowed
PREFLIGHT_10_LEAKAGE=no prospective label grade outcome prediction accuracy utility raw senior archive or identity-valued output access
PREFLIGHT_11_SECURITY=open trace forbidden paths zero; credential filename and content zero; aggregate-only output
PREFLIGHT_12_RESOURCES=CPU only; GPU API model-fit base-update equals 0/0/0/0
PREFLIGHT_13_PROMOTION=only exact tests A/B independent equality clean worktree security and manifest success may create COMPLETE; any mismatch fails closed
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
(
  cd "$worktree"
  timeout 1800 "$python" -m pytest -q \
    phase1/tests/test_tree_linearization_depth_order_corollary.py \
    phase1/tests/test_tree_linearization_within_stratum_decomposition.py \
    phase1/tests/test_prospective_tree_linearization_weights.py \
    phase1/tests/test_tree_linearization_estimand_sensitivity.py \
    phase1/tests/test_tree_native_path_compatibility.py
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
    timeout 300 "$python" -m phase1.derive_tree_linearization_depth_order_corollary \
    --protocol "$protocol" \
    --protocol-sha256 "$protocol_sha" \
    --repo-root "$worktree" \
    --source-commit "$commit" \
    --output "$formal/producer_a.json"
) >"$formal/producer_a.stdout" 2>"$formal/producer_a.stderr"
test ! -s "$formal/producer_a.stderr"
(
  cd "$worktree"
  timeout 300 "$python" -m phase1.derive_tree_linearization_depth_order_corollary \
    --protocol "$protocol" \
    --protocol-sha256 "$protocol_sha" \
    --repo-root "$worktree" \
    --source-commit "$commit" \
    --output "$formal/producer_b.json"
) >"$formal/producer_b.stdout" 2>"$formal/producer_b.stderr"
test ! -s "$formal/producer_b.stderr"
cmp "$formal/producer_a.json" "$formal/producer_b.json"
readonly receipt_sha=$(sha256sum "$formal/producer_a.json" | awk '{print $1}')

(
  cd "$worktree"
  strace -f -qq -e trace=openat -o "$formal/verifier_a_open_trace.log" \
    timeout 300 "$python" -m phase1.verify_tree_linearization_depth_order_corollary \
    --protocol "$protocol" \
    --protocol-sha256 "$protocol_sha" \
    --repo-root "$worktree" \
    --receipt "$formal/producer_a.json" \
    --receipt-sha256 "$receipt_sha" \
    --producer-source "$producer" \
    --producer-source-sha256 "$producer_sha" \
    --source-commit "$commit" \
    --output "$formal/verifier_a.json"
) >"$formal/verifier_a.stdout" 2>"$formal/verifier_a.stderr"
test ! -s "$formal/verifier_a.stderr"
(
  cd "$worktree"
  timeout 300 "$python" -m phase1.verify_tree_linearization_depth_order_corollary \
    --protocol "$protocol" \
    --protocol-sha256 "$protocol_sha" \
    --repo-root "$worktree" \
    --receipt "$formal/producer_b.json" \
    --receipt-sha256 "$receipt_sha" \
    --producer-source "$producer" \
    --producer-source-sha256 "$producer_sha" \
    --source-commit "$commit" \
    --output "$formal/verifier_b.json"
) >"$formal/verifier_b.stdout" 2>"$formal/verifier_b.stderr"
test ! -s "$formal/verifier_b.stderr"
cmp "$formal/verifier_a.json" "$formal/verifier_b.json"

cat "$formal/producer_a_open_trace.log" "$formal/verifier_a_open_trace.log" >"$formal/combined_open_trace.log"
if grep -Ei '/external/senior_data/|/prospective_decision_v1/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault' \
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
jq '{status,classification,snapshot_sha256,inventory,exact_order_profile,deterministic_properties,exact_integrity_checks,design_timing,claim_boundary,security}' \
  "$formal/producer_a.json" >"$formal/formal_summary.json"
cat >"$formal/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_card_parent_code_or_per_edge_values_emitted=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
printf '%s\n' "$commit" >"$formal/source_commit.txt"
(
  cd "$formal"
  manifest_tmp=$(mktemp /tmp/depth-order-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >"$manifest_tmp"
  printf '%s\n' TREE_LINEARIZATION_DEPTH_ORDER_FORMAL_COMPLETE >.COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "$complete_sha" >>"$manifest_tmp"
  mv "$manifest_tmp" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
chmod -R a-w "$formal"
trap - EXIT
jq '{status,classification,snapshot_sha256,inventory,exact_order_profile,deterministic_properties,security}' \
  "$formal/formal_summary.json"
sha256sum "$formal/SHA256SUMS"
