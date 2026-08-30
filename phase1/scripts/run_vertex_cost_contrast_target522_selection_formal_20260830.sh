#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 10 ]]; then
  echo 'usage: run_vertex_cost_contrast_target522_selection_formal_20260830.sh OUTPUT_ROOT EXPECTED_COMMIT EXECUTION_SHA PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA MONITOR_SHA SELECTION_SHA256SUMS_SHA' >&2
  exit 64
fi
readonly output=$1
readonly expected_commit=$2
readonly execution_sha=$3
readonly protocol_sha=$4
readonly producer_sha=$5
readonly verifier_sha=$6
readonly test_sha=$7
readonly runner_sha=$8
readonly monitor_sha=$9
readonly selection_manifest_sha=${10}
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly worktree=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/worktree-${expected_commit:0:7}-selection-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly execution_rel=phase1/vertex_cost_contrast_target522_execution_v1.json
readonly protocol_rel=phase1/vertex_cost_contrast_target522_effect_v1.json
readonly producer_rel=phase1/freeze_vertex_cost_contrast_target522_selection.py
readonly verifier_rel=phase1/verify_vertex_cost_contrast_target522_selection.py
readonly test_rel=phase1/tests/test_vertex_cost_contrast_target522_runner.py
readonly runner_rel=phase1/scripts/run_vertex_cost_contrast_target522_selection_formal_20260830.sh
readonly monitor_rel=phase1/scripts/monitor_vertex_cost_contrast_target522_selection_formal_20260830.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$execution_sha" "$protocol_sha" "$producer_sha" "$verifier_sha" \
  "$test_sha" "$runner_sha" "$monitor_sha" "$selection_manifest_sha"; do
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
test "$(git -C "$repo" show "${expected_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

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
02_question=at equal paid endpoint budgets does code-only VCCD improve future run-clean critic transfer over representative uniform and frozen yield breadth; PASS
03_selection=one automatic Target-522 package COMPLETE and exact manifest,alternate candidate argument forbidden; PASS
04_source=exact public commit plus execution protocol producer verifier test runner and monitor hashes; PASS
05_population=complete physical runs absent from frozen snapshot 887,task-stratified acquisition versus evaluation split; PASS
06_stage=Stage A code and sibling topology only,no grade orientation gap outcome prediction runtime or utility; PASS
07_arms=representative exact-B uniform edge,frozen yield-guarded breadth,and VCCD at six nested checkpoints; PASS
08_cost=one executed endpoint is one paid unit,dependent clique labels are not counted as independent executions; PASS
09_repetitions=producer A/B,private selection A/B,and non-importing verifier A/B must be byte exact; PASS
10_tests=focused and full phase1 tests in a fresh detached exact-commit worktree; PASS
11_integrity=manifest rechecked before and after,run split disjoint,public identity guard,private mode 0600; PASS
12_security=strace file/network audit,no external senior data vault outcome prediction or credential access; PASS
13_resources=single CPU only,GPU paid-API model-fit base-update 0/0/0/0,first-960 closure remains unopened; PASS
EOF
test "$(wc -l <"$output/preflight_13.txt")" = 13

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test "$(sha256sum "$worktree/$execution_rel" | awk '{print $1}')" = "$execution_sha"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"
test "$(sha256sum "$worktree/$monitor_rel" | awk '{print $1}')" = "$monitor_sha"
cmp "$0" "$worktree/$runner_rel"
jq -e \
  --arg execution_sha "$execution_sha" --arg protocol_sha "$protocol_sha" \
  --arg producer_sha "$producer_sha" --arg verifier_sha "$verifier_sha" \
  --arg test_sha "$test_sha" --arg runner_sha "$runner_sha" --arg monitor_sha "$monitor_sha" '
  .protocol == "vertex-cost-contrast-target522-stage-a-execution-v1"
  and .status == "FROZEN_BEFORE_TARGET522_CANDIDATE"
  and .scientific_protocol.sha256 == $protocol_sha
  and .bindings.producer.sha256 == $producer_sha
  and .bindings.independent_verifier.sha256 == $verifier_sha
  and .bindings.test.sha256 == $test_sha
  and .bindings.runner.sha256 == $runner_sha
  and .bindings.monitor.sha256 == $monitor_sha
  and .activation.first960_closure_required_for_stage_a == false
  and .activation.first960_closure_required_for_any_fit == true
  and .resources.gpu == 0
  and .resources.paid_api_calls == 0
  and .resources.model_fits == 0
  and .resources.base_updates == 0
' "$worktree/$execution_rel" >/dev/null

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

"$python_bin" - <<'PY' >"$output/environment.json"
import json
import os
import platform

import numpy
import scipy

print(
    json.dumps(
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": numpy.__version__,
            "scipy": scipy.__version__,
            "pythonhashseed": os.environ["PYTHONHASHSEED"],
            "thread_limits": {
                name: os.environ[name]
                for name in (
                    "OPENBLAS_NUM_THREADS",
                    "OMP_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS",
                    "BLIS_NUM_THREADS",
                )
            },
        },
        sort_keys=True,
    )
)
PY
git --version >"$output/git_version.txt"

printf '%s\n' "$python_bin -m pytest -q phase1/tests/test_vertex_cost_contrast_design.py phase1/tests/test_freeze_vertex_cost_contrast_target522_selection.py $test_rel" \
  >"$output/focused_command.txt"
(
  cd "$worktree"
  timeout 600s "$python_bin" -m pytest -q \
    phase1/tests/test_vertex_cost_contrast_design.py \
    phase1/tests/test_freeze_vertex_cost_contrast_target522_selection.py \
    "$test_rel"
) >"$output/focused_tests.txt" 2>&1
printf '%s\n' "$python_bin -m pytest -q phase1/tests" >"$output/full_command.txt"
(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

producer=(
  "$python_bin" -m phase1.freeze_vertex_cost_contrast_target522_selection
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$expected_commit"
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
)
printf '%q ' "${producer[@]}" --public-output "$output/producer_a.json" --private-output "$output/private_a.json" \
  >"$output/producer_command.txt"
printf '\n' >>"$output/producer_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/producer_a.time.txt" \
    timeout 1800s strace -ff -tt -yy -e trace=file,network -o "$output/producer_a.trace" \
    "${producer[@]}" --public-output "$output/producer_a.json" --private-output "$output/private_a.json"
) >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
(
  cd "$worktree"
  timeout 1800s "${producer[@]}" --public-output "$output/producer_b.json" --private-output "$output/private_b.json"
) >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
cmp "$output/producer_a.json" "$output/producer_b.json"
if test -e "$output/private_a.json" || test -e "$output/private_b.json"; then
  test -f "$output/private_a.json" && test -f "$output/private_b.json"
  test "$(stat -c '%a' "$output/private_a.json")" = 600
  test "$(stat -c '%a' "$output/private_b.json")" = 600
  cmp "$output/private_a.json" "$output/private_b.json"
else
  test ! -e "$output/private_a.json" && test ! -e "$output/private_b.json"
fi

verifier=(
  "$python_bin" -m phase1.verify_vertex_cost_contrast_target522_selection
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$expected_commit"
  --state-root "$state"
  --selection-root "$selection"
  --repo-root "$worktree"
)
printf '%q ' "${verifier[@]}" --public-result "$output/producer_a.json" \
  --private-selection "$output/private_a.json" --verification-output "$output/verifier_a.json" \
  >"$output/verifier_command.txt"
printf '\n' >>"$output/verifier_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/verifier_a.time.txt" \
    timeout 1800s strace -ff -tt -yy -e trace=file,network -o "$output/verifier_a.trace" \
    "${verifier[@]}" --public-result "$output/producer_a.json" \
      --private-selection "$output/private_a.json" --verification-output "$output/verifier_a.json"
) >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
(
  cd "$worktree"
  timeout 1800s "${verifier[@]}" --public-result "$output/producer_b.json" \
    --private-selection "$output/private_b.json" --verification-output "$output/verifier_b.json"
) >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verifier_a.json" "$output/verifier_b.json"
test "$(stat -c '%a' "$output/verifier_a.json")" = 600
test "$(stat -c '%a' "$output/verifier_b.json")" = 600

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
  .protocol == "vertex-cost-contrast-target522-selection-public-v1"
  and .status == "COMPLETE"
  and .analysis_source_commit == $commit
  and .protocol_sha256 == $protocol_sha
  and (.classification == "VCCD_TARGET522_SELECTION_LIMITED_SUPPORT"
       or .classification == "VCCD_TARGET522_SELECTION_READY_THREE_ARMS"
       or .classification == "VCCD_TARGET522_SELECTION_READY_YIELD_BASELINE_UNAVAILABLE")
  and .append_only.baseline_runs_exact_subset == true
  and .append_only.baseline_endpoints_exact_subset == true
  and .append_only.increment_contains_only_complete_new_physical_runs == true
  and .run_partition.overlap == 0
  and .scope.outcome_blind_code_and_topology_only == true
  and .scope.label_grade_gap_prediction_accuracy_utility_runtime_used == false
  and .scope.prospective_values_read == false
  and .scope.first960_closure_opened == false
  and .scope.raw_identities_publicly_emitted == false
  and .scope.gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/producer_a.json" >/dev/null
jq -e --arg protocol_sha "$protocol_sha" '
  .protocol == "vertex-cost-contrast-target522-selection-verification-v1"
  and .status == "VERIFIED"
  and .protocol_sha256 == $protocol_sha
  and .prospective_values_read == false
' "$output/verifier_a.json" >/dev/null
test "$(jq -r .classification "$output/producer_a.json")" = \
  "$(jq -r .classification "$output/verifier_a.json")"
test "$(jq -r .public_result_sha256 "$output/verifier_a.json")" = \
  "$(sha256sum "$output/producer_a.json" | awk '{print $1}')"
if test -f "$output/private_a.json"; then
  test "$(jq -r .private_selection_sha256 "$output/verifier_a.json")" = \
    "$(sha256sum "$output/private_a.json" | awk '{print $1}')"
else
  test "$(jq -r .private_selection_sha256 "$output/verifier_a.json")" = null
fi

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
prospective_values_read=false
first960_closure_opened=false
raw_senior_archives_opened=false
public_endpoint_task_run_parent_identities_emitted=false
private_selection_remote_mode_0600=true
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
execution_protocol_sha256=${execution_sha}
scientific_protocol_sha256=${protocol_sha}
producer_source_sha256=${producer_sha}
verifier_source_sha256=${verifier_sha}
test_source_sha256=${test_sha}
runner_source_sha256=${runner_sha}
monitor_source_sha256=${monitor_sha}
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
printf 'status=VCCD_TARGET522_STAGE_A_FORMAL_COMPLETE\nclassification=%s\nmanifest_sha256=%s\n' \
  "$(jq -r .classification "$output/producer_a.json")" \
  "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
