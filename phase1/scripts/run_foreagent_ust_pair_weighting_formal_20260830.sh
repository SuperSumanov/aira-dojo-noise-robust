#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 7 ]]; then
  echo 'usage: run_foreagent_ust_pair_weighting_formal_20260830.sh OUTPUT_ROOT EXPECTED_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi
readonly output=$1
readonly expected_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly test_sha=$6
readonly runner_sha=$7
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly input=/tmp/pbe_predict_before_execute.parquet
readonly input_sha=79363b7ef0b6154061f18e81f6c6fdf380e71ae3f1d7b9a262cc79acb08f0b5f
readonly worktree=/research/d7/spc/yzyang4/foreagent-ust-pair-weighting/worktree-${expected_commit:0:7}-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly protocol_rel=phase1/foreagent_ust_pair_weighting_addendum_v1.json
readonly producer_rel=phase1/audit_foreagent_ust_pair_weighting.py
readonly verifier_rel=phase1/verify_foreagent_ust_pair_weighting.py
readonly test_rel=phase1/tests/test_foreagent_ust_pair_weighting.py
readonly runner_rel=phase1/scripts/run_foreagent_ust_pair_weighting_formal_20260830.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/foreagent-ust-pair-weighting/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$output"
test ! -e "$worktree"
test -f "$input" && test ! -L "$input"
test "$(sha256sum "$input" | awk '{print $1}')" = "$input_sha"
command -v strace >/dev/null
test -x "$python_bin"

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${expected_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic
test "$(sha256sum "$0" | awk '{print $1}')" = "$runner_sha"
test "$(git -C "$repo" show "${expected_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

mkdir -p "$output"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then printf '%s\n' "$rc" >"$output/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

cat >"$output/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_question=how uniform-spanning-tree edge weights redistribute FOREAGENT public pair rows; PASS
03_disclosure=18361 rows 895 vertices 26 components rank 869 known,edge weights and task redistribution unseen; PASS
04_input=public immutable parquet SHA ${input_sha},paths column only; PASS
05_quantity=unweighted effective resistance equals UST edge inclusion probability and sums to V-C; PASS
06_special_cases=K_k edge weight 2/k and tree edge weight 1,verified synthetically; PASS
07_not_claimed=no new graph theorem ESS independence information predictor effect or accuracy invalidity; PASS
08_source=exact public commit protocol eigendecomposition producer grounded-inverse verifier test runner hashes; PASS
09_repetitions=producer A/B and verifier A/B must be byte exact; PASS
10_tests=focused and complete phase1 tests in fresh detached exact-commit worktree; PASS
11_security=file/network trace,no score prediction solution code credential or senior outcome access; PASS
12_failure=input hash schema numeric identity source result trace test or arithmetic drift stops closed; PASS
13_resources=single CPU only,GPU paid-API model-fit base-update 0/0/0/0; PASS
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
jq -e --arg producer_sha "$producer_sha" --arg verifier_sha "$verifier_sha" \
  --arg test_sha "$test_sha" --arg runner_sha "$runner_sha" '
  .protocol == "foreagent-public-ust-pair-weighting-addendum-v1"
  and .status == "FROZEN_BEFORE_EDGE_LEVERAGE_OR_TASK_WEIGHT_READOUT"
  and .source_bindings.producer.sha256 == $producer_sha
  and .source_bindings.independent_verifier.sha256 == $verifier_sha
  and .source_bindings.test.sha256 == $test_sha
  and .source_bindings.runner.sha256 == $runner_sha
  and .resources.gpu == 0
  and .resources.paid_api_calls == 0
  and .resources.model_fits == 0
  and .resources.base_updates == 0
' "$worktree/$protocol_rel" >/dev/null

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
(
  cd "$worktree"
  timeout 600s "$python_bin" -m pytest -q "$test_rel"
) >"$output/focused_tests.txt" 2>&1
(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

producer=(
  "$python_bin" -m phase1.audit_foreagent_ust_pair_weighting
  --input "$input"
  --input-sha256 "$input_sha"
)
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/producer_a.time.txt" \
    timeout 600s strace -ff -tt -yy -e trace=file,network -o "$output/producer_a.trace" \
    "${producer[@]}" --output "$output/result_a.json"
) >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
(
  cd "$worktree"
  timeout 600s "${producer[@]}" --output "$output/result_b.json"
) >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"
test "$(stat -c '%a' "$output/result_a.json")" = 600
test "$(stat -c '%a' "$output/result_b.json")" = 600

result_sha=$(sha256sum "$output/result_a.json" | awk '{print $1}')
verifier=(
  "$python_bin" -m phase1.verify_foreagent_ust_pair_weighting
  --input "$input"
  --input-sha256 "$input_sha"
  --claimed-result "$output/result_a.json"
  --claimed-result-sha256 "$result_sha"
)
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/verifier_a.time.txt" \
    timeout 600s strace -ff -tt -yy -e trace=file,network -o "$output/verifier_a.trace" \
    "${verifier[@]}" --output "$output/verification_a.json"
) >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
(
  cd "$worktree"
  timeout 600s "${verifier[@]}" --output "$output/verification_b.json"
) >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"
test "$(stat -c '%a' "$output/verification_a.json")" = 600
test "$(stat -c '%a' "$output/verification_b.json")" = 600

for role in producer_a verifier_a; do
  forbidden_hits=$( { grep -hEi \
    '/external/senior_data/|senior-outcome|label_vault|outcome_vault|/outcomes?/|prediction|solution[^/]*code|/\.env([" ]|$)' \
    "$output/${role}.trace"* || true; } | wc -l )
  network_hits=$( { grep -hEi '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' \
    "$output/${role}.trace"* || true; } | wc -l )
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done
printf 'producer_forbidden_path_hits=0\nverifier_forbidden_path_hits=0\nproducer_network_hits=0\nverifier_network_hits=0\n' \
  >"$output/trace_audit.txt"

jq -e --arg source_sha "$input_sha" '
  .protocol == "foreagent-public-ust-pair-weighting-result-v1"
  and .status == "DESCRIPTIVE_COMPLETE"
  and .classification == "DESCRIPTIVE_UST_PAIR_WEIGHTING_AUDIT_COMPLETE"
  and .source_sha256 == $source_sha
  and .pair_rows == 18361
  and .vertices == 895
  and .tasks == 26
  and .connected_components == 26
  and .endpoint_edge_incidence_rank == 869
  and .ust_edge_weight.expected_sum_rank == 869
  and .scope.columns_read == ["paths"]
  and .scope.scores_or_predictions_read == false
  and .scope.solution_code_read == false
  and .scope.raw_identities_emitted == false
  and .scope.gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/result_a.json" >/dev/null
jq -e --arg result_sha "$result_sha" '
  .status == "INDEPENDENT_GROUNDED_LAPLACIAN_RECONSTRUCTION_WITHIN_TOLERANCE"
  and .claimed_result_sha256 == $result_sha
  and .pair_rows == 18361
  and .endpoint_edge_incidence_rank == 869
  and .scores_or_predictions_read == false
' "$output/verification_a.json" >/dev/null

git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$input" | awk '{print $1}')" = "$input_sha"
filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security.txt --exclude=SHA256SUMS || true)
test "$filename_hits" = 0
test -z "$credential_files"
cat >"$output/security.txt" <<EOF
credential_filename_hits=0
boundary_aware_credential_content_file_hits=0
scores_or_predictions_read=false
solution_code_read=false
raw_identities_emitted=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
scientific_protocol_sha256=${protocol_sha}
producer_source_sha256=${producer_sha}
verifier_source_sha256=${verifier_sha}
test_source_sha256=${test_sha}
runner_source_sha256=${runner_sha}
input_sha256=${input_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=FOREAGENT_UST_PAIR_WEIGHTING_FORMAL_COMPLETE\nresult_sha256=%s\nmanifest_sha256=%s\n' \
  "$result_sha" "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
