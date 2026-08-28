#!/usr/bin/env bash
source "$HOME/env_setup.sh" >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly commit=2363b687ea503ced5945208766bb25f1baaeffed
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly root=/research/d7/spc/yzyang4/tree-linearization-within-stratum
readonly worktree=${root}/worktree-2363b68-v1
readonly formal=${root}/formal-2363b68-887491a-v1
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly protocol_sha=9f4f27c56e6dcec7b6302b095225afb307c0be3900b528dd5f56225639fb79a7
readonly producer_sha=38aa702d58e1250db31790227778130d6fca41939cdc4f74249cbfa3d766e25c
readonly verifier_sha=c6158bb201d604180739c24f9cf57309f2159dbd2e7233190e0fe36db5690e16
readonly tests_sha=08d874d98ed443378627213362e3e66b7af757f0d447228be6fc739ada11e3fd

test ! -e "$worktree"
test ! -e "$formal"
test -f "$state/LATEST"
test ! -L "$state/LATEST"
test "$(tr -d '\r\n' < "$state/LATEST")" = "$snapshot_sha"
test -d "$snapshot"

mkdir -p "$root"
git -C "$repo" fetch fork phase1-value-critic
test "$(git -C "$repo" rev-parse fork/phase1-value-critic)" = "$commit"
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$commit"
test "$(git -C "$worktree" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"

readonly protocol=${worktree}/phase1/tree_linearization_within_stratum_decomposition_v1.json
readonly producer=${worktree}/phase1/decompose_tree_linearization_within_strata.py
readonly verifier=${worktree}/phase1/verify_tree_linearization_within_stratum_decomposition.py
readonly tests=${worktree}/phase1/tests/test_tree_linearization_within_stratum_decomposition.py
test "$(sha256sum "$protocol" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$producer" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$verifier" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$tests" | awk '{print $1}')" = "$tests_sha"

mkdir "$formal"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "$rc" > "$formal/FAILED_RC" 2>/dev/null || true; fi; exit "$rc"' EXIT
cp /tmp/run_within_stratum_formal_2363b68_20260828.sh "$formal/deployed_runner.sh"

cat >"$formal/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; HCE multifidelity Probe score-channel effect and K>=1 remain closed
PREFLIGHT_02_QUESTION=after fixing task or physical-run marginal mass quantify exact conditional edge-measure distortion breadth and concentration
PREFLIGHT_03_DISCLOSURE=overall edge TV and task/run marginal TVs plus their triangle lower bounds were known before freeze; positive or material W_p alone is not new
PREFLIGHT_04_AMENDMENT=commit e99499e initial slack gate was corrected before synthetic or real new values because slack measures bound looseness; protocol SHA ${protocol_sha}
PREFLIGHT_05_INPUTS=exact snapshot ${snapshot_sha}; original blind population contract and two hash-bound aggregate receipts only
PREFLIGHT_06_ESTIMAND=canonical-marginal standardized within TV primary; path-marginal standardized TV secondary non-rescuing; all conditionable groups retained
PREFLIGHT_07_GATES=task/run integrity floors 0.20/0.15 are weaker than disclosed lower bounds; genuinely new gates are breadth 1/2 and 1/4 plus max contribution 0.40 and 0.20
PREFLIGHT_08_LEAKAGE=no prospective label grade outcome prediction accuracy utility raw senior archive or identity-valued output access
PREFLIGHT_09_SOURCE=fresh detached no-smudge exact commit ${commit}; protocol producer verifier and tests hashes exact; clean before aggregate
PREFLIGHT_10_TESTS=synthetic and neighboring focused suite followed by all phase1 tests before real aggregate
PREFLIGHT_11_INDEPENDENCE=producer A/B byte equality and verifier A/B byte equality; verifier imports no new producer and reconstructs graph with a distinct algorithm
PREFLIGHT_12_SECURITY=open trace forbidden paths zero; exact blind schema; credential filename/content zero; aggregate-only output; CPU only and GPU/API/model-fit/base-update 0/0/0/0
PREFLIGHT_13_PROMOTION=only exact tests A/B independent reconstruction security clean-worktree and manifest success may create COMPLETE; any mismatch fails closed
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
    timeout 900 "$python" -m phase1.decompose_tree_linearization_within_strata \
    --state-root "$state" \
    --snapshot-root "$snapshot" \
    --repo-root "$worktree" \
    --protocol "$protocol" \
    --expect-protocol-sha256 "$protocol_sha" \
    --source-commit "$commit" \
    --out "$formal/producer_a.json"
) >"$formal/producer_a.stdout" 2>"$formal/producer_a.stderr"
test ! -s "$formal/producer_a.stderr"
(
  cd "$worktree"
  timeout 900 "$python" -m phase1.decompose_tree_linearization_within_strata \
    --state-root "$state" \
    --snapshot-root "$snapshot" \
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
    timeout 900 "$python" -m phase1.verify_tree_linearization_within_stratum_decomposition \
    --state-root "$state" \
    --snapshot-root "$snapshot" \
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
  timeout 900 "$python" -m phase1.verify_tree_linearization_within_stratum_decomposition \
    --state-root "$state" \
    --snapshot-root "$snapshot" \
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
if grep -Ei '/external/senior_data/|decision_clean[^/]*\.jsonl|/(labels?|outcomes?|predictions?)(/|[^/]*\.(json|jsonl))|label[^/]*vault' \
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
jq '{status,classification,snapshot_sha256,protocol_sha256,source_commit,inventory,overall_edge_total_variation,partitions,pre_registered_gate,design_timing,claim_boundary,security}' \
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
  manifest_tmp=$(mktemp /tmp/within-stratum-formal-manifest.XXXXXX)
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >"$manifest_tmp"
  printf '%s\n' OUTCOME_BLIND_WITHIN_STRATUM_FORMAL_COMPLETE >.COMPLETE.tmp
  complete_sha=$(sha256sum .COMPLETE.tmp | awk '{print $1}')
  printf '%s  COMPLETE\n' "$complete_sha" >>"$manifest_tmp"
  mv "$manifest_tmp" SHA256SUMS
  mv .COMPLETE.tmp COMPLETE
  sha256sum -c SHA256SUMS >/dev/null
)
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
chmod -R a-w "$formal"
trap - EXIT
jq '{status,classification,snapshot_sha256,inventory,overall_edge_total_variation,partitions,pre_registered_gate,security}' \
  "$formal/formal_summary.json"
sha256sum "$formal/SHA256SUMS"
