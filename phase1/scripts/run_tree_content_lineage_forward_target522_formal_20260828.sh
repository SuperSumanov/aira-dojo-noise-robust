#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 8 ]]; then
  echo 'usage: run_tree_content_lineage_forward_target522_formal_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA SELECTION_SHA256SUMS_SHA' >&2
  exit 64
fi
readonly output=$1
readonly expected_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly test_sha=$6
readonly runner_sha=$7
readonly selection_manifest_sha=$8
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly worktree=/research/d7/spc/yzyang4/tree-content-lineage-formal-worktrees/worktree-${expected_commit:0:7}-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly protocol_rel=phase1/tree_content_lineage_forward_target522_v1.json
readonly producer_rel=phase1/audit_tree_content_lineage_forward_target522.py
readonly verifier_rel=phase1/verify_tree_content_lineage_forward_target522.py
readonly test_rel=phase1/tests/test_tree_content_lineage_forward_target522_audit.py
readonly runner_rel=phase1/scripts/run_tree_content_lineage_forward_target522_formal_20260828.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/tree-content-lineage-forward-target522/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha" "$selection_manifest_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$output"
test ! -e "$worktree"
test -d "$selection" && test ! -L "$selection"
test -f "$selection/COMPLETE"
test ! -e "$selection/FAILED_RC"
test ! -e "$selection/CONTINUITY_GAP"
test ! -e "$selection/TIMEOUT_RC"
test "$(sha256sum "$selection/SHA256SUMS" | awk '{print $1}')" = "$selection_manifest_sha"
(
  cd "$selection"
  sha256sum -c SHA256SUMS >/dev/null
)
command -v strace >/dev/null
command -v timeout >/dev/null
test -x "$python_bin"

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${expected_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic
test "$(sha256sum "$0" | awk '{print $1}')" = "$runner_sha"
git -C "$repo" show "${expected_commit}:${runner_rel}" >"/tmp/content-lineage-runner-${expected_commit}.sh"
cmp "$0" "/tmp/content-lineage-runner-${expected_commit}.sh"

mkdir -p "$output"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "$rc" >"$output/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

cat >"$output/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_question=does the disjoint Target-522 increment show hierarchy-conditioned content-parent concordance and low wrong-pointer acceptance; PASS
03_selection=${selection},COMPLETE and exact manifest,no alternate candidate; PASS
04_source_commit=${expected_commit},protocol/producer/verifier/test/runner hashes exact; PASS
05_population=complete new physical runs only,baseline 887 excluded and byte-unchanged; PASS
06_estimands=unique-top exact-depth recovery,uniform control,all wrong parents,two hierarchy ablations,and flat pair oracle; PASS
07_gates=exact fractions,hard support then content concordance then hierarchy complementarity; PASS
08_repetitions=producer A/B and non-importing verifier A/B byte identity; PASS
09_tests=focused integration/attack tests then complete phase1/tests in fresh detached worktree; PASS
10_integrity=independent snapshot readers/fingerprints/pair sweeps and immutable selection support; PASS
11_security=strace file/network audit,credential scan,identity-free aggregate output; PASS
12_forbidden=no label,outcome,prediction,accuracy,effect,utility,raw senior archive,GPU/API/model-fit/base-update; PASS
13_failure=new immutable output root,FAILED_RC on error,no same-candidate repair or threshold rescue; PASS
EOF

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"
cmp "$0" "$worktree/$runner_rel"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

printf '%s\n' "$python_bin -m pytest -q phase1/tests/test_tree_within_stratum_forward_target522_protocol.py phase1/tests/test_tree_within_stratum_forward_target522_audit.py $test_rel" \
  >"$output/focused_command.txt"
(
  cd "$worktree"
  "$python_bin" -m pytest -q \
    phase1/tests/test_tree_within_stratum_forward_target522_protocol.py \
    phase1/tests/test_tree_within_stratum_forward_target522_audit.py \
    "$test_rel"
) >"$output/focused_tests.txt" 2>&1
printf '%s\n' "$python_bin -m pytest -q phase1/tests" >"$output/full_command.txt"
(
  cd "$worktree"
  "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

producer=(
  "$python_bin" -m phase1.audit_tree_content_lineage_forward_target522
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
  --protocol "$worktree/$protocol_rel"
  --expect-protocol-sha256 "$protocol_sha"
  --source-commit "$expected_commit"
)
printf '%q ' "${producer[@]}" --out "$output/producer_a.json" >"$output/producer_command.txt"
printf '\n' >>"$output/producer_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/producer_a.time.txt" \
    timeout 1800s strace -ff -tt -yy -e trace=file,network -o "$output/producer_a.trace" \
    "${producer[@]}" --out "$output/producer_a.json"
) >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
(
  cd "$worktree"
  timeout 1800s "${producer[@]}" --out "$output/producer_b.json"
) >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
cmp "$output/producer_a.json" "$output/producer_b.json"
producer_receipt_sha=$(sha256sum "$output/producer_a.json" | awk '{print $1}')

verifier=(
  "$python_bin" -m phase1.verify_tree_content_lineage_forward_target522
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
  --protocol "$worktree/$protocol_rel"
  --expect-protocol-sha256 "$protocol_sha"
  --expect-receipt-sha256 "$producer_receipt_sha"
  --producer-source "$worktree/$producer_rel"
  --expect-producer-source-sha256 "$producer_sha"
  --source-commit "$expected_commit"
)
printf '%q ' "${verifier[@]}" --receipt "$output/producer_a.json" --out "$output/verifier_a.json" \
  >"$output/verifier_command.txt"
printf '\n' >>"$output/verifier_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/verifier_a.time.txt" \
    timeout 1800s strace -ff -tt -yy -e trace=file,network -o "$output/verifier_a.trace" \
    "${verifier[@]}" --receipt "$output/producer_a.json" --out "$output/verifier_a.json"
) >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
(
  cd "$worktree"
  timeout 1800s "${verifier[@]}" --receipt "$output/producer_b.json" --out "$output/verifier_b.json"
) >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verifier_a.json" "$output/verifier_b.json"

for role in producer_a verifier_a; do
  forbidden_hits=$( { grep -hEi \
    '/external/senior_data/|label_vault|outcome_vault|/outcomes?/|regrade|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|/\.env([" ]|$)' \
    "$output/${role}.trace"* || true; } | wc -l )
  network_hits=$( { grep -hEi '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' \
    "$output/${role}.trace"* || true; } | wc -l )
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done
printf 'producer_forbidden_path_hits=0\nverifier_forbidden_path_hits=0\nproducer_network_hits=0\nverifier_network_hits=0\n' \
  >"$output/trace_audit.txt"

jq -e --arg commit "$expected_commit" --arg protocol_sha "$protocol_sha" '
  .protocol == "tree-content-lineage-forward-target522-receipt-v1"
  and .status == "OUTCOME_BLIND_FORWARD_CONTENT_LINEAGE_AUDIT_COMPLETE"
  and .analysis_source_commit == $commit
  and .protocol_sha256 == $protocol_sha
  and .security.raw_senior_archives_opened == false
  and .security.prospective_label_grade_outcome_prediction_values_read == false
  and .security.task_run_card_parent_code_or_per_pair_values_emitted == false
  and .security.accuracy_effect_or_search_utility_computed == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
  and .reproducibility.decimal_values_used_for_gates == false
' "$output/producer_a.json" >/dev/null
jq -e '
  .protocol == "independent-tree-content-lineage-forward-target522-verifier-v1"
  and .status == "INDEPENDENT_FORWARD_CONTENT_LINEAGE_AUDIT_PASS"
  and .checks.imports_new_producer == false
  and .checks.append_only_increment_independently_rechecked == true
  and .checks.pair_graph_and_three_parent_modes_independently_recomputed == true
  and .security.prospective_label_grade_outcome_prediction_values_read == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
' "$output/verifier_a.json" >/dev/null
test "$(jq -r .classification "$output/producer_a.json")" = \
  "$(jq -r .classification "$output/verifier_a.json")"

git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$selection/SHA256SUMS" | awk '{print $1}')" = "$selection_manifest_sha"
(
  cd "$selection"
  sha256sum -c SHA256SUMS >/dev/null
)
filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security.txt --exclude=SHA256SUMS || true)
test "$filename_hits" = 0
test -z "$credential_files"
cat >"$output/security.txt" <<EOF
credential_filename_hits=0
boundary_aware_credential_content_file_hits=0
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_card_parent_code_or_per_pair_values_emitted=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
protocol_sha256=${protocol_sha}
producer_source_sha256=${producer_sha}
verifier_source_sha256=${verifier_sha}
test_source_sha256=${test_sha}
runner_source_sha256=${runner_sha}
selection_sha256sums_sha256=${selection_manifest_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=FORMAL_CONTENT_LINEAGE_TARGET522_COMPLETE\nclassification=%s\nmanifest_sha256=%s\n' \
  "$(jq -r .classification "$output/producer_a.json")" \
  "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
