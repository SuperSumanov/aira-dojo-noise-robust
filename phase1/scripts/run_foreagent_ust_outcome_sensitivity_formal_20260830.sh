#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

if [[ $# -ne 10 ]]; then
  printf 'usage: %s OUTPUT EXPECTED_COMMIT PROTOCOL_SHA EXECUTION_ADDENDUM_SHA IDENTITY_ADDENDUM_SHA NUMERIC_ADDENDUM_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA\n' "$0" >&2
  exit 2
fi

readonly output=$1
readonly expected_commit=$2
readonly protocol_sha=$3
readonly addendum_sha=$4
readonly identity_addendum_sha=$5
readonly numeric_addendum_sha=$6
readonly producer_sha=$7
readonly verifier_sha=$8
readonly test_sha=$9
readonly runner_sha=${10}
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly master=/research/d7/spc/yzyang4/scratch/pbe_alignment_cache_v1/all_predictions.compact.jsonl
readonly worktree="${output}-worktree"
readonly manifest_sha=3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e
readonly master_sha=480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

test ! -e "$output"
test ! -e "$worktree"
mkdir -m 700 -p "$output"
trap 'rc=$?; printf "%s\n" "$rc" >"$output/FAILED_RC"; exit "$rc"' EXIT

cat >"$output/preflight_13.txt" <<'EOF'
01_question=Does graph-rank/UST weighting change released FOREAGENT prediction metrics on one exact common finite pair support?; PASS
02_estimands=raw pair micro,UST rank micro,raw task macro,UST task macro,and paired model deltas fixed before new graph-weighted outcome computation; PASS
03_unit=three release predictions averaged within model-task-pair before any aggregation; PASS
04_population=DeepSeek exact grid,GPT three-release intersection,cross-model common finite directional support; PASS
05_sample_size=156 files,110620 primitive rows,26 tasks,known support counts fixed; PASS
06_randomness=20000 task bootstraps with seeds 20260830 and 20260831; PASS
07_positive_controls=K4 leverage 1/2,tree leverage 1,triangle-plus-bridge nonuniform weighting,orientation reversal; PASS
08_baselines=published-support raw reproduction plus raw pair and task metrics on exact common support; PASS
09_leakage=historical public outcomes only,no prospective source or model fit,raw identities forbidden from output; PASS
10_resources=single CPU only,0 GPU,0 API,0 model fit,0 base update; PASS
11_inference=task-clustered bootstrap and leave-one-task-out,not pair-iid inference; PASS
12_abort=any hash,schema,grid,truth,duplicate,graph,Foster,test,trace,byte,identity or verifier mismatch fails closed; PASS
13_artifacts=exact command,commit,source hashes,input hashes,tests,traces,A-B repeats,manifest and read-only tree retained; PASS
EOF

git -C "$repo" fetch fork phase1-value-critic >"$output/fetch.stdout" 2>"$output/fetch.stderr"
test "$(git -C "$repo" rev-parse fork/phase1-value-critic)" = "$expected_commit"
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"

readonly protocol="$worktree/phase1/foreagent_ust_outcome_sensitivity_v1.json"
readonly addendum="$worktree/phase1/foreagent_ust_outcome_sensitivity_execution_addendum_v2.json"
readonly identity_addendum="$worktree/phase1/foreagent_ust_outcome_sensitivity_identity_addendum_v3.json"
readonly numeric_addendum="$worktree/phase1/foreagent_ust_outcome_sensitivity_numeric_addendum_v4.json"
readonly producer_source="$worktree/phase1/analyze_foreagent_ust_outcome_sensitivity.py"
readonly verifier_source="$worktree/phase1/verify_foreagent_ust_outcome_sensitivity.py"
readonly test_source="$worktree/phase1/tests/test_foreagent_ust_outcome_sensitivity.py"
readonly runner_source="$worktree/phase1/scripts/run_foreagent_ust_outcome_sensitivity_formal_20260830.sh"
readonly manifest="$worktree/phase1/foreagent_alignment_manifest_v1.json"

test "$(sha256sum "$protocol" | cut -d ' ' -f1)" = "$protocol_sha"
test "$(sha256sum "$addendum" | cut -d ' ' -f1)" = "$addendum_sha"
test "$(sha256sum "$identity_addendum" | cut -d ' ' -f1)" = "$identity_addendum_sha"
test "$(sha256sum "$numeric_addendum" | cut -d ' ' -f1)" = "$numeric_addendum_sha"
test "$(sha256sum "$producer_source" | cut -d ' ' -f1)" = "$producer_sha"
test "$(sha256sum "$verifier_source" | cut -d ' ' -f1)" = "$verifier_sha"
test "$(sha256sum "$test_source" | cut -d ' ' -f1)" = "$test_sha"
test "$(sha256sum "$runner_source" | cut -d ' ' -f1)" = "$runner_sha"
test "$(sha256sum "$manifest" | cut -d ' ' -f1)" = "$manifest_sha"
test "$(sha256sum "$master" | cut -d ' ' -f1)" = "$master_sha"

cd "$worktree"
env PYTHONHASHSEED=0 "$python" -m pytest phase1/tests/test_foreagent_ust_outcome_sensitivity.py -q \
  >"$output/focused_tests.txt" 2>&1
env PYTHONHASHSEED=0 "$python" -m pytest phase1/tests -q \
  >"$output/full_tests.txt" 2>&1

producer=(
  "$python" -m phase1.analyze_foreagent_ust_outcome_sensitivity
  --manifest "$manifest"
  --master "$master"
)
verifier=(
  "$python" -m phase1.verify_foreagent_ust_outcome_sensitivity
  --manifest "$manifest"
  --master "$master"
)

env PYTHONHASHSEED=1 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "$output/producer_a.trace" "${producer[@]}" --output "$output/result_a.json" \
  >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
env PYTHONHASHSEED=2 timeout 1800s "${producer[@]}" --output "$output/result_b.json" \
  >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
readonly result_sha="$(sha256sum "$output/result_a.json" | cut -d ' ' -f1)"

env PYTHONHASHSEED=3 timeout 1800s strace -ff -tt -yy -e trace=file,network \
  -o "$output/verifier_a.trace" "${verifier[@]}" \
  --claimed-result "$output/result_a.json" --claimed-result-sha256 "$result_sha" \
  --output "$output/verification_a.json" \
  >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
env PYTHONHASHSEED=4 timeout 1800s "${verifier[@]}" \
  --claimed-result "$output/result_a.json" --claimed-result-sha256 "$result_sha" \
  --output "$output/verification_b.json" \
  >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"

producer_forbidden=$(grep -hEi '/prospective_decision_v1|src/mle_critic/docs/outcomes|/\.env([^A-Za-z0-9_]|$)' \
  "$output"/producer_a.trace.* | wc -l || true)
verifier_forbidden=$(grep -hEi '/prospective_decision_v1|src/mle_critic/docs/outcomes|/\.env([^A-Za-z0-9_]|$)' \
  "$output"/verifier_a.trace.* | wc -l || true)
producer_network=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "$output"/producer_a.trace.* \
  | wc -l || true)
verifier_network=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "$output"/verifier_a.trace.* \
  | wc -l || true)
test "$producer_forbidden" = 0
test "$verifier_forbidden" = 0
test "$producer_network" = 0
test "$verifier_network" = 0
cat >"$output/trace_audit.txt" <<EOF
producer_forbidden_path_hits=0
verifier_forbidden_path_hits=0
producer_network_hits=0
verifier_network_hits=0
EOF

jq -e --arg manifest_sha "$manifest_sha" --arg master_sha "$master_sha" '
  .protocol == "foreagent-ust-outcome-sensitivity-result-v1"
  and .status == "HISTORICAL_PUBLIC_OUTCOME_SENSITIVITY_COMPLETE"
  and .classification == "POSTDISCLOSURE_GRAPH_WEIGHTED_SENSITIVITY_COMPLETE"
  and .inputs.manifest_sha256 == $manifest_sha
  and .inputs.master_sha256 == $master_sha
  and .inputs.source_files == 156
  and .inputs.source_records == 110620
  and .population.tasks == 26
  and .population.common_finite_directional_pairs == 18381
  and .population.confidence_values_read == false
  and .common_support_graph.task_identities_emitted == false
  and .scope.prospective_values_read == false
  and .scope.raw_task_or_endpoint_identities_emitted == false
  and .scope.gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/result_a.json" >/dev/null
jq -e --arg result_sha "$result_sha" '
  .status == "INDEPENDENT_GROUNDED_RECONSTRUCTION_EXACT_WITHIN_TOLERANCE"
  and .claimed_result_sha256 == $result_sha
  and .pairs == 18381
  and .tasks == 26
  and .confidence_values_read == false
  and .prospective_values_read == false
  and .raw_identities_emitted == false
  and .gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/verification_a.json" >/dev/null

git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$manifest" | cut -d ' ' -f1)" = "$manifest_sha"
test "$(sha256sum "$master" | cut -d ' ' -f1)" = "$master_sha"

filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security.txt --exclude=SHA256SUMS || true)
test "$filename_hits" = 0
test -z "$credential_files"
cat >"$output/security.txt" <<'EOF'
credential_filename_hits=0
boundary_aware_credential_content_file_hits=0
historical_public_scores_and_predictions_read=true
confidence_values_read=false
prospective_values_read=false
raw_task_or_endpoint_identities_emitted=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=$expected_commit
scientific_protocol_sha256=$protocol_sha
execution_addendum_sha256=$addendum_sha
identity_addendum_sha256=$identity_addendum_sha
numeric_addendum_sha256=$numeric_addendum_sha
producer_source_sha256=$producer_sha
verifier_source_sha256=$verifier_sha
test_source_sha256=$test_sha
runner_source_sha256=$runner_sha
manifest_sha256=$manifest_sha
master_sha256=$master_sha
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=FOREAGENT_UST_OUTCOME_SENSITIVITY_FORMAL_COMPLETE\nresult_sha256=%s\nmanifest_sha256=%s\n' \
  "$result_sha" "$(sha256sum "$output/SHA256SUMS" | cut -d ' ' -f1)"
