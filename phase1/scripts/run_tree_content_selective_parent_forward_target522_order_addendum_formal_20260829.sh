#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 6 ]]; then
  echo 'usage: run_tree_content_selective_parent_forward_target522_order_addendum_formal_20260829.sh EXPECTED_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi
readonly expected_commit=$1
readonly protocol_sha=$2
readonly producer_sha=$3
readonly verifier_sha=$4
readonly test_sha=$5
readonly runner_sha=$6
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly upstream=/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522/formal-349b9ca-target522-v1
readonly output=/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522-order-addendum/formal-${expected_commit:0:7}-target522-v1
readonly worktree=/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522-order-addendum/worktree-${expected_commit:0:7}-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly protocol_rel=phase1/tree_content_selective_parent_forward_target522_order_addendum_v1.json
readonly producer_rel=phase1/audit_tree_content_selective_parent_forward_target522_order_addendum.py
readonly verifier_rel=phase1/verify_tree_content_selective_parent_forward_target522_order_addendum.py
readonly test_rel=phase1/tests/test_tree_content_selective_parent_forward_target522_order_addendum.py
readonly runner_rel=phase1/scripts/run_tree_content_selective_parent_forward_target522_order_addendum_formal_20260829.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test "$protocol_sha" = 81df44e9194fb194611d6ffb7f3fba6c0a3fd1d7d2c0aa1ba6be19d33f84ce87
test ! -e "$output"
test ! -e "$worktree"
test -d "$selection" && test ! -L "$selection"
test -f "$selection/COMPLETE"
test ! -e "$selection/FAILED_RC"
test ! -e "$selection/CONTINUITY_GAP"
test ! -e "$selection/TIMEOUT_RC"
test -d "$upstream" && test ! -L "$upstream"
test -f "$upstream/COMPLETE"
test ! -e "$upstream/FAILED_RC"
command -v strace >/dev/null
command -v timeout >/dev/null
command -v jq >/dev/null
test -x "$python_bin"

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${expected_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic
test "$(sha256sum "$0" | awk '{print $1}')" = "$runner_sha"
git -C "$repo" show "${expected_commit}:${runner_rel}" >"/tmp/order-addendum-runner-${expected_commit}.sh"
cmp "$0" "/tmp/order-addendum-runner-${expected_commit}.sh"

mkdir -p "$output"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then printf '%s\n' "$rc" >"$output/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

selection_manifest_sha=$(sha256sum "$selection/SHA256SUMS" | awk '{print $1}')
upstream_manifest_sha=$(sha256sum "$upstream/SHA256SUMS" | awk '{print $1}')
(
  cd "$selection"
  sha256sum -c SHA256SUMS >/dev/null
)
(
  cd "$upstream"
  sha256sum -c SHA256SUMS >/dev/null
)
cat >"$output/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_question=does fixed future content add beyond valid max-prior-step on the same selected decisions; PASS
03_selection=${selection},first crossing COMPLETE and exact manifest,no alternate root; PASS
04_upstream=${upstream},selective-parent formal COMPLETE and exact manifest,no rescue authority; PASS
05_source_commit=${expected_commit},protocol/producer/verifier/test/runner hashes exact; PASS
06_population=fixed content-selected Target-522 increment rows,development and baseline rows excluded; PASS
07_control=max-prior-step fixed before candidate,no fitting,manifest row and timestamps have no authority; PASS
08_gates=upstream strongest required,then integrity/support,paired half-error/twofold-win and breadth; PASS
09_repetitions=producer A/B and non-importing verifier A/B byte identity; PASS
10_tests=focused attack tests and complete phase1/tests in fresh detached worktree; PASS
11_security=strace file/network audit,credential scan,identity-free aggregate output; PASS
12_forbidden=no first960 Target300 value vault raw senior archive predictor effect utility GPU API fit or base update; PASS
13_failure=new fixed output root,FAILED_RC on error,no threshold population gate candidate or interpretation repair; PASS
EOF
test "$(wc -l <"$output/preflight_13.txt")" = 13

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"
cmp "$0" "$worktree/$runner_rel"
test -z "$(git -C "$worktree" status --porcelain=v1 --untracked-files=all)"

export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q \
    "$test_rel" \
    phase1/tests/test_tree_content_selective_parent_forward_target522.py \
    phase1/tests/test_selective_parent_order_baseline_falsification_result.py \
    phase1/tests/test_tree_within_stratum_forward_target522_protocol.py
) >"$output/focused_tests.txt" 2>"$output/focused_tests.stderr"
(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>"$output/full_tests.stderr"

producer=(
  "$python_bin" -m phase1.audit_tree_content_selective_parent_forward_target522_order_addendum
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
  --protocol "$worktree/$protocol_rel"
  --expect-protocol-sha256 "$protocol_sha"
  --source-commit "$expected_commit"
)
PYTHONHASHSEED=0 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "$output/producer_a.trace" \
  "${producer[@]}" --out "$output/producer_a.json" \
  >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${producer[@]}" --out "$output/producer_b.json" \
  >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
test ! -s "$output/producer_a.stdout"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stdout"
test ! -s "$output/producer_b.stderr"
cmp "$output/producer_a.json" "$output/producer_b.json"
producer_receipt_sha=$(sha256sum "$output/producer_a.json" | awk '{print $1}')

verifier=(
  "$python_bin" -m phase1.verify_tree_content_selective_parent_forward_target522_order_addendum
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
  --protocol "$worktree/$protocol_rel"
  --expect-protocol-sha256 "$protocol_sha"
  --receipt "$output/producer_a.json"
  --expect-receipt-sha256 "$producer_receipt_sha"
  --producer-source "$worktree/$producer_rel"
  --expect-producer-source-sha256 "$producer_sha"
  --source-commit "$expected_commit"
)
PYTHONHASHSEED=0 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "$output/verifier_a.trace" \
  "${verifier[@]}" --out "$output/verifier_a.json" \
  >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${verifier[@]}" --out "$output/verifier_b.json" \
  >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stdout"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stdout"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verifier_a.json" "$output/verifier_b.json"

for trace in "$output"/producer_a.trace* "$output"/verifier_a.trace*; do
  test -f "$trace"
  forbidden_hits=$(grep -Eic \
    '/external/senior_data/|label_vault|outcome_vault|/outcomes?/|regrade|pair_predictions\.jsonl|endpoint_scores\.csv|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|/\.env([" ]|$)' \
    "$trace" || true)
  network_hits=$(grep -Eic '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' "$trace" || true)
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done

jq -e '
  .security.task_run_card_parent_code_or_per_edge_values_emitted == false
  and .security.prospective_first960_or_target300_values_read == false
  and .security.raw_senior_archives_opened == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
' "$output/producer_a.json" >/dev/null
jq -e '
  .producer_imported == false
  and .task_run_card_parent_code_or_per_edge_values_emitted == false
  and .prospective_first960_or_target300_values_read == false
  and .raw_senior_archives_opened == false
  and .gpu_api_model_fit_base_update == [0,0,0,0]
' "$output/verifier_a.json" >/dev/null

filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "$filename_hits" = 0
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security_receipt.txt --exclude=SHA256SUMS || true)
test -z "$credential_files"
printf '%s\n' \
  'forbidden_path_hits=0' \
  'network_hits=0' \
  'credential_filename_hits=0' \
  'boundary_aware_credential_content_file_hits=0' \
  'prospective_first960_or_target300_values_read=false' \
  'raw_senior_archives_opened=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' \
  >"$output/security_receipt.txt"

jq '{
  protocol,
  status,
  classification,
  protocol_sha256,
  analysis_source_commit,
  known_development_evidence,
  upstream_target522_binding,
  snapshot_bindings,
  append_only_and_increment,
  inventory,
  fixed_content_rule,
  selected_population_paired_comparison,
  all_ambiguous_max_prior_step_supplementary,
  anonymous_disagreement_breadth,
  pre_registered_gate,
  claim_boundary,
  security,
  reproducibility
}' "$output/producer_a.json" >"$output/formal_summary.json"
test -z "$(git -C "$worktree" status --porcelain=v1 --untracked-files=all)"
cat >"$output/source_bindings.txt" <<EOF
selection_manifest_sha256=${selection_manifest_sha}
upstream_formal_manifest_sha256=${upstream_manifest_sha}
source_commit=${expected_commit}
protocol_sha256=${protocol_sha}
producer_sha256=${producer_sha}
verifier_sha256=${verifier_sha}
test_sha256=${test_sha}
runner_sha256=${runner_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
jq -c '{classification,upstream_target522_binding,inventory,selected_population_paired_comparison,anonymous_disagreement_breadth,pre_registered_gate}' \
  "$output/formal_summary.json"
sha256sum "$output/producer_a.json" "$output/verifier_a.json" "$output/SHA256SUMS"
