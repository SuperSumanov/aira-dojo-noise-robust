#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 10 ]]; then
  echo 'usage: run_target522_linear_contrast_rank_audit_formal_20260830.sh OUTPUT_ROOT EXPECTED_COMMIT EXECUTION_SHA PROTOCOL_SHA ANALYZER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA MONITOR_SHA STAGE_A_MANIFEST_SHA' >&2
  exit 64
fi
readonly output=$1
readonly expected_commit=$2
readonly execution_sha=$3
readonly protocol_sha=$4
readonly analyzer_sha=$5
readonly verifier_sha=$6
readonly test_sha=$7
readonly runner_sha=$8
readonly monitor_sha=$9
readonly stage_a_manifest_sha=${10}
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly stage_a=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-4fc9c3e-selection-v1
readonly worktree=/research/d7/spc/yzyang4/target522-linear-contrast-rank/worktree-${expected_commit:0:7}-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly execution_rel=phase1/target522_linear_contrast_rank_execution_v1.json
readonly protocol_rel=phase1/target522_linear_contrast_rank_audit_v1.json
readonly analyzer_rel=phase1/audit_target522_linear_contrast_rank.py
readonly verifier_rel=phase1/verify_target522_linear_contrast_rank.py
readonly test_rel=phase1/tests/test_target522_linear_contrast_rank.py
readonly runner_rel=phase1/scripts/run_target522_linear_contrast_rank_audit_formal_20260830.sh
readonly monitor_rel=phase1/scripts/monitor_target522_linear_contrast_rank_audit_formal_20260830.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$execution_sha" "$protocol_sha" "$analyzer_sha" "$verifier_sha" \
  "$test_sha" "$runner_sha" "$monitor_sha" "$stage_a_manifest_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$output"
test ! -e "$worktree"
test -d "$stage_a" && test ! -L "$stage_a"
test -f "$stage_a/COMPLETE"
test ! -e "$stage_a/FAILED_RC"
test "$(sha256sum "$stage_a/SHA256SUMS" | awk '{print $1}')" = "$stage_a_manifest_sha"
for public_name in producer_a.json producer_b.json; do
  test "$(awk -v name="./$public_name" '$2 == name {count += 1} END {print count + 0}' "$stage_a/SHA256SUMS")" = 1
  expected_public_sha=$(awk -v name="./$public_name" '$2 == name {print $1}' "$stage_a/SHA256SUMS")
  test "$(sha256sum "$stage_a/$public_name" | awk '{print $1}')" = "$expected_public_sha"
done
cmp "$stage_a/producer_a.json" "$stage_a/producer_b.json"
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
02_question=do untouched Target-522 public sibling graphs contain materially more pair rows than endpoint-incidence rank; PASS
03_freeze=historical v11 exploration disclosed and thresholds frozen while Target-522 candidate READY COMPLETE were absent; PASS
04_input=only immutable Stage-A public producer A/B after COMPLETE,no private selection or candidate identity; PASS
05_quantity=rank of endpoint-edge incidence design for exact disjoint sibling cliques,not effective sample size or information; PASS
06_partition=acquisition and evaluation physical runs disjoint and both must independently pass the same fixed gate; PASS
07_gate=pair-rows per incidence-rank at least 6/5 plus fixed size task and concentration support; PASS
08_repetitions=analyzer A/B and non-importing verifier A/B must be byte exact; PASS
09_tests=focused and full phase1 tests in a fresh detached exact-commit worktree; PASS
10_integrity=exact source hashes,Stage-A public hashes,mode 0600,and independent arithmetic reconstruction; PASS
11_security=strace file and network audit,no private selection label outcome prediction gap accuracy runtime utility or credential access; PASS
12_failure=hash schema duplicate output trace test arithmetic or support drift stops closed or yields limited support; PASS
13_resources=single CPU only,GPU paid-API model-fit base-update 0/0/0/0,first-960 closure unopened; PASS
EOF
test "$(wc -l <"$output/preflight_13.txt")" = 13

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test "$(sha256sum "$worktree/$execution_rel" | awk '{print $1}')" = "$execution_sha"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$analyzer_rel" | awk '{print $1}')" = "$analyzer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"
test "$(sha256sum "$worktree/$monitor_rel" | awk '{print $1}')" = "$monitor_sha"
cmp "$0" "$worktree/$runner_rel"
jq -e \
  --arg protocol_sha "$protocol_sha" --arg analyzer_sha "$analyzer_sha" \
  --arg verifier_sha "$verifier_sha" --arg test_sha "$test_sha" \
  --arg runner_sha "$runner_sha" --arg monitor_sha "$monitor_sha" '
  .protocol == "target522-linear-contrast-rank-execution-v1"
  and .status == "FROZEN_AFTER_DISCLOSED_HISTORICAL_EXPLORATION_BEFORE_TARGET522_CANDIDATE"
  and .scientific_protocol.sha256 == $protocol_sha
  and .bindings.analyzer.sha256 == $analyzer_sha
  and .bindings.independent_verifier.sha256 == $verifier_sha
  and .bindings.test.sha256 == $test_sha
  and .bindings.runner.sha256 == $runner_sha
  and .bindings.monitor.sha256 == $monitor_sha
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
ulimit -v 16777216

"$python_bin" - <<'PY' >"$output/environment.json"
import json
import os
import platform

print(json.dumps({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "pythonhashseed": os.environ["PYTHONHASHSEED"],
    "thread_limits": {
        key: os.environ[key]
        for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    },
}, sort_keys=True))
PY
git --version >"$output/git_version.txt"

(
  cd "$worktree"
  timeout 600s "$python_bin" -m pytest -q "$test_rel"
) >"$output/focused_tests.txt" 2>&1
(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

stage_a_sha=$(sha256sum "$stage_a/producer_a.json" | awk '{print $1}')
analyzer=(
  "$python_bin" -m phase1.audit_target522_linear_contrast_rank
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --stage-a-public "$stage_a/producer_a.json"
  --stage-a-public-sha256 "$stage_a_sha"
)
printf '%q ' "${analyzer[@]}" --output "$output/result_a.json" >"$output/analyzer_command.txt"
printf '\n' >>"$output/analyzer_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/analyzer_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/analyzer_a.trace" \
    "${analyzer[@]}" --output "$output/result_a.json"
) >"$output/analyzer_a.stdout" 2>"$output/analyzer_a.stderr"
(
  cd "$worktree"
  timeout 300s "${analyzer[@]}" --output "$output/result_b.json"
) >"$output/analyzer_b.stdout" 2>"$output/analyzer_b.stderr"
test ! -s "$output/analyzer_a.stderr"
test ! -s "$output/analyzer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"
test "$(stat -c '%a' "$output/result_a.json")" = 600
test "$(stat -c '%a' "$output/result_b.json")" = 600

claimed_sha=$(sha256sum "$output/result_a.json" | awk '{print $1}')
verifier=(
  "$python_bin" -m phase1.verify_target522_linear_contrast_rank
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --stage-a-public "$stage_a/producer_a.json"
  --stage-a-public-sha256 "$stage_a_sha"
  --claimed-result "$output/result_a.json"
  --claimed-result-sha256 "$claimed_sha"
)
printf '%q ' "${verifier[@]}" --output "$output/verification_a.json" >"$output/verifier_command.txt"
printf '\n' >>"$output/verifier_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/verifier_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/verifier_a.trace" \
    "${verifier[@]}" --output "$output/verification_a.json"
) >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
(
  cd "$worktree"
  timeout 300s "${verifier[@]}" --output "$output/verification_b.json"
) >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"
test "$(stat -c '%a' "$output/verification_a.json")" = 600
test "$(stat -c '%a' "$output/verification_b.json")" = 600

for role in analyzer_a verifier_a; do
  forbidden_hits=$( { grep -hEi \
    '/external/senior_data/|label_vault|outcome_vault|/outcomes?/|regrade|private_[ab]\.json|private_selection|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|/\.env([" ]|$)' \
    "$output/${role}.trace"* || true; } | wc -l )
  network_hits=$( { grep -hEi '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' \
    "$output/${role}.trace"* || true; } | wc -l )
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done
printf 'analyzer_forbidden_path_hits=0\nverifier_forbidden_path_hits=0\nanalyzer_network_hits=0\nverifier_network_hits=0\n' \
  >"$output/trace_audit.txt"

jq -e --arg protocol_sha "$protocol_sha" --arg stage_a_sha "$stage_a_sha" '
  .protocol == "target522-linear-contrast-rank-audit-result-v1"
  and .status == "COMPLETE"
  and (.classification == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED"
       or .classification == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_NOT_CONFIRMED"
       or .classification == "TARGET522_LINEAR_CONTRAST_RANK_AUDIT_LIMITED_SUPPORT")
  and .protocol_sha256 == $protocol_sha
  and .stage_a_public_sha256 == $stage_a_sha
  and .exact_disjoint_sibling_clique_basis == true
  and .run_partition_overlap == 0
  and .scope.public_stage_a_aggregate_only == true
  and .scope.private_selection_opened == false
  and .scope.candidate_profile_or_identity_opened == false
  and .scope.label_grade_gap_prediction_accuracy_utility_runtime_used == false
  and .scope.prospective_values_read == false
  and .scope.first960_closure_opened == false
  and .scope.gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/result_a.json" >/dev/null
jq -e --arg result_sha "$claimed_sha" '
  .protocol == "target522-linear-contrast-rank-independent-verification-v1"
  and .status == "INDEPENDENT_RECONSTRUCTION_EXACT"
  and .claimed_result_sha256 == $result_sha
  and .graphs_reconstructed == 2
  and .private_selection_opened == false
  and .candidate_profile_or_identity_opened == false
  and .prospective_values_read == false
  and .gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/verification_a.json" >/dev/null
test "$(jq -r .classification "$output/result_a.json")" = \
  "$(jq -r .classification "$output/verification_a.json")"

git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$stage_a/SHA256SUMS" | awk '{print $1}')" = "$stage_a_manifest_sha"
test "$(sha256sum "$stage_a/producer_a.json" | awk '{print $1}')" = "$stage_a_sha"

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
private_selection_opened=false
candidate_profile_or_identity_opened=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
execution_protocol_sha256=${execution_sha}
scientific_protocol_sha256=${protocol_sha}
analyzer_source_sha256=${analyzer_sha}
verifier_source_sha256=${verifier_sha}
test_source_sha256=${test_sha}
runner_source_sha256=${runner_sha}
monitor_source_sha256=${monitor_sha}
stage_a_sha256sums_sha256=${stage_a_manifest_sha}
stage_a_public_sha256=${stage_a_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=TARGET522_LINEAR_CONTRAST_RANK_AUDIT_COMPLETE\nclassification=%s\nmanifest_sha256=%s\n' \
  "$(jq -r .classification "$output/result_a.json")" \
  "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
