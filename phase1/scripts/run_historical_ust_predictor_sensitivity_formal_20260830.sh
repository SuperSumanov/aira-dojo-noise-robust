#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 7 ]]; then
  echo 'usage: run_historical_ust_predictor_sensitivity_formal_20260830.sh OUTPUT_ROOT EXPECTED_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
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
readonly static_root=/research/d7/spc/yzyang4/critic-component-static-suite/76c1b49_20260821T022057Z
readonly static_a=$static_root/producer_1/per_pair.jsonl
readonly static_b=$static_root/producer_2/per_pair.jsonl
readonly static_sha=ec5a9afd37e9fbf21a4a1e89c29e9a0c771a75f0f2090b99a163711a59515acd
readonly tfidf_sha=021f8b3c74db89c6b770714edb879731799b145744af7b765005eed72f9ecde6
readonly worktree=/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/worktree-${expected_commit:0:7}-v1
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly protocol_rel=phase1/historical_ust_predictor_sensitivity_v1.json
readonly producer_rel=phase1/analyze_historical_ust_predictor_sensitivity.py
readonly verifier_rel=phase1/verify_historical_ust_predictor_sensitivity.py
readonly test_rel=phase1/tests/test_historical_ust_predictor_sensitivity.py
readonly runner_rel=phase1/scripts/run_historical_ust_predictor_sensitivity_formal_20260830.sh
readonly tfidf_rel=phase1/results/critic_component_tfidf_20260821_a6075d1/per_pair.jsonl
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/historical-ust-predictor-sensitivity/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$output"
test ! -e "$worktree"
test -f "$static_a" && test ! -L "$static_a"
test -f "$static_b" && test ! -L "$static_b"
test "$(sha256sum "$static_a" | awk '{print $1}')" = "$static_sha"
test "$(sha256sum "$static_b" | awk '{print $1}')" = "$static_sha"
cmp "$static_a" "$static_b"
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
02_question=whether UST edge weighting changes historical same-pool predictor points uncertainty or rankings; PASS
03_disclosure=historical raw outcomes and published aggregates known,UST outcome aggregates ranking and shifts unseen; PASS
04_population=fixed 931 test pairs exact support across 11 static or heuristic arms plus fixed TFIDF; PASS
05_selection=dev-selected static_gbm_task champion and TFIDF reference fixed,no test reselection; PASS
06_estimands=raw and UST pair micro task macro parent macro paired shifts and paired deltas; PASS
07_inference=20000 deterministic task and parent clustered bootstrap repetitions plus champion LOTO; PASS
08_inputs=two byte-identical static producers and tracked TFIDF exact SHA,all historical only; PASS
09_independence=eigendecomposition producer and grounded-inverse verifier,hashseed A/B byte exact; PASS
10_tests=focused and complete phase1 tests in fresh detached exact-commit worktree; PASS
11_security=file and network trace,no prospective cohort vault senior outcome credential or raw identity output; PASS
12_failure=hash schema support graph Foster metric ranking identity trace test or arithmetic drift stops closed; PASS
13_resources=single CPU only,GPU paid-API model-fit base-update 0/0/0/0; PASS
EOF
test "$(wc -l <"$output/preflight_13.txt")" = 13

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
readonly tfidf=$worktree/$tfidf_rel
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"
test "$(sha256sum "$tfidf" | awk '{print $1}')" = "$tfidf_sha"
cmp "$0" "$worktree/$runner_rel"
jq -e --arg producer_sha "$producer_sha" --arg verifier_sha "$verifier_sha" \
  --arg test_sha "$test_sha" --arg runner_sha "$runner_sha" '
  .protocol == "historical-ust-predictor-sensitivity-v1"
  and .status == "FROZEN_AFTER_HISTORICAL_SCHEMA_DESERIALIZATION_BEFORE_UST_OUTCOME_AGGREGATION"
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
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
(
  cd "$worktree"
  env PYTHONHASHSEED=0 timeout 600s "$python_bin" -m pytest -q "$test_rel"
) >"$output/focused_tests.txt" 2>&1
(
  cd "$worktree"
  env PYTHONHASHSEED=0 timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

producer=(
  "$python_bin" -m phase1.analyze_historical_ust_predictor_sensitivity
  --static-per-pair "$static_a"
  --tfidf-per-pair "$tfidf"
)
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/producer_a.time.txt" \
    env PYTHONHASHSEED=0 timeout 1800s strace -ff -tt -yy -e trace=file,network \
    -o "$output/producer_a.trace" "${producer[@]}" --output "$output/result_a.json"
) >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
(
  cd "$worktree"
  env PYTHONHASHSEED=1 timeout 1800s "${producer[@]}" --output "$output/result_b.json"
) >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"
test "$(stat -c '%a' "$output/result_a.json")" = 600
test "$(stat -c '%a' "$output/result_b.json")" = 600

result_sha=$(sha256sum "$output/result_a.json" | awk '{print $1}')
verifier=(
  "$python_bin" -m phase1.verify_historical_ust_predictor_sensitivity
  --static-per-pair "$static_a"
  --tfidf-per-pair "$tfidf"
  --claimed-result "$output/result_a.json"
  --claimed-result-sha256 "$result_sha"
)
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/verifier_a.time.txt" \
    env PYTHONHASHSEED=2 timeout 1800s strace -ff -tt -yy -e trace=file,network \
    -o "$output/verifier_a.trace" "${verifier[@]}" --output "$output/verification_a.json"
) >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
(
  cd "$worktree"
  env PYTHONHASHSEED=3 timeout 1800s "${verifier[@]}" --output "$output/verification_b.json"
) >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"
test "$(stat -c '%a' "$output/verification_a.json")" = 600
test "$(stat -c '%a' "$output/verification_b.json")" = 600

for role in producer_a verifier_a; do
  forbidden_hits=$( { grep -hEi \
    '/external/senior_data/|senior-outcome|label_vault|outcome_vault|outcome-blind|prospective|first[-_]?960|target[-_]?522|/\.env([" ]|$)' \
    "$output/${role}.trace"* || true; } | wc -l )
  network_hits=$( { grep -hEi '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' \
    "$output/${role}.trace"* || true; } | wc -l )
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done
printf 'producer_forbidden_path_hits=0\nverifier_forbidden_path_hits=0\nproducer_network_hits=0\nverifier_network_hits=0\n' \
  >"$output/trace_audit.txt"

jq -e --arg static_sha "$static_sha" --arg tfidf_sha "$tfidf_sha" '
  .protocol == "historical-ust-predictor-sensitivity-result-v1"
  and .status == "HISTORICAL_SENSITIVITY_COMPLETE"
  and .classification == "HISTORICAL_UST_PREDICTOR_SENSITIVITY_AUDIT_COMPLETE"
  and .inputs.static_per_pair_sha256 == $static_sha
  and .inputs.tfidf_per_pair_sha256 == $tfidf_sha
  and .population.pairs == 931
  and .population.models == 12
  and .population.dev_selected_champion_fixed_before_analysis == "static_gbm_task"
  and .pair_graph.tasks == 28
  and .pair_graph.decision_parents == 550
  and .pair_graph.connected_components == 559
  and .pair_graph.task_identities_emitted == false
  and .ranking_sensitivity.frozen_champion_reselection_performed == false
  and .scope.historical_revealed_prediction_outcomes_read == true
  and .scope.prospective_values_read == false
  and .scope.model_fit == false
  and .scope.raw_pair_task_parent_endpoint_identities_emitted == false
' "$output/result_a.json" >/dev/null
jq -e --arg result_sha "$result_sha" '
  .status == "INDEPENDENT_GROUNDED_RECONSTRUCTION_EXACT_WITHIN_TOLERANCE"
  and .claimed_result_sha256 == $result_sha
  and .pairs == 931
  and .models == 12
  and .prospective_values_read == false
  and .gpu_paid_api_model_fit_base_update == "0/0/0/0"
' "$output/verification_a.json" >/dev/null

git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$static_a" | awk '{print $1}')" = "$static_sha"
test "$(sha256sum "$static_b" | awk '{print $1}')" = "$static_sha"
test "$(sha256sum "$tfidf" | awk '{print $1}')" = "$tfidf_sha"
filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security.txt --exclude=SHA256SUMS || true)
test "$filename_hits" = 0
test -z "$credential_files"
cat >"$output/security.txt" <<EOF
credential_filename_hits=0
boundary_aware_credential_content_file_hits=0
historical_revealed_prediction_outcomes_read=true
prospective_values_read=false
raw_pair_task_parent_endpoint_identities_emitted=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
scientific_protocol_sha256=${protocol_sha}
producer_source_sha256=${producer_sha}
verifier_source_sha256=${verifier_sha}
test_source_sha256=${test_sha}
runner_source_sha256=${runner_sha}
static_per_pair_sha256=${static_sha}
tfidf_per_pair_sha256=${tfidf_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=HISTORICAL_UST_PREDICTOR_SENSITIVITY_FORMAL_COMPLETE\nresult_sha256=%s\nmanifest_sha256=%s\n' \
  "$result_sha" "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
