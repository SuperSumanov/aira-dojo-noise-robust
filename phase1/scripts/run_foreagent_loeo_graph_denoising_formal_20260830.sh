#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

if (( $# != 7 )); then
  echo 'usage: runner OUTPUT EXPECTED_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
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
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly master=/research/d7/spc/yzyang4/scratch/pbe_alignment_cache_v1/all_predictions.compact.jsonl
readonly worktree=${output}-worktree
readonly manifest_sha=3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e
readonly master_sha=480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

fail() {
  rc=$?
  if test -d "$output" && (( rc != 0 )); then
    printf '%s\n' "$rc" >"$output/FAILED_RC" 2>/dev/null || true
  fi
  if test -d "$worktree"; then
    git -C "$repo" worktree remove --force "$worktree" >/dev/null 2>&1 || true
  fi
  exit "$rc"
}
trap fail EXIT

test ! -e "$output"
test ! -e "$worktree"
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
mkdir -m 700 -p "$output"
cat >"$output/preflight_13.txt" <<'EOF'
01_direction=Decision Corpus Predictor Benchmark Audit Protocol public external benchmark baseline only; PASS
02_goal=test whether target-edge-excluded graph consistency denoising improves fixed FOREAGENT judges; PASS
03_population=exact 18381-pair 26-task common finite grid fixed before denoising outcomes; PASS
04_inputs=official 156-file manifest and 110620-row compact primitive at fixed SHA256; PASS
05_estimand=raw-majority versus full-coverage LOEO hybrid task macro primary with pair micro secondary; PASS
06_method=task-local Hodge least squares where each target edge is analytically excluded; PASS
07_controls=raw majority bridge fallback brute-force LOEO synthetic orientation reversal and known raw reproduction; PASS
08_inference=20000 task-clustered bootstraps plus LOTO with no pair-IID claim; PASS
09_leakage=historical public labels evaluate only after label-free projection and prospective sources are forbidden; PASS
10_resources=single CPU only GPU paid-API model-fit base-update 0/0/0/0; PASS
11_scoop=classical graph ranking and 2026 TCR are prior art so algorithmic novelty is explicitly forbidden; PASS
12_abort=any hash schema support graph test trace repeat verifier security or byte mismatch fails closed; PASS
13_artifacts=exact command commit hashes tests traces A-B repeats independent verifier manifest and read-only tree retained; PASS
EOF
test "$(grep -c '; PASS$' "$output/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic >"$output/fetch.stdout" 2>"$output/fetch.stderr"
test "$(git -C "$repo" rev-parse "$expected_commit")" = "$expected_commit"
git -C "$repo" merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic
git -C "$repo" worktree add --detach "$worktree" "$expected_commit" >"$output/worktree.stdout" 2>"$output/worktree.stderr"

readonly protocol=$worktree/phase1/foreagent_loeo_graph_denoising_v1.json
readonly producer=$worktree/phase1/analyze_foreagent_loeo_graph_denoising.py
readonly verifier=$worktree/phase1/verify_foreagent_loeo_graph_denoising.py
readonly test_source=$worktree/phase1/tests/test_foreagent_loeo_graph_denoising.py
readonly runner=$worktree/phase1/scripts/run_foreagent_loeo_graph_denoising_formal_20260830.sh
readonly manifest=$worktree/phase1/foreagent_alignment_manifest_v1.json

test "$(sha256sum "$protocol" | cut -d ' ' -f1)" = "$protocol_sha"
test "$(sha256sum "$producer" | cut -d ' ' -f1)" = "$producer_sha"
test "$(sha256sum "$verifier" | cut -d ' ' -f1)" = "$verifier_sha"
test "$(sha256sum "$test_source" | cut -d ' ' -f1)" = "$test_sha"
test "$(sha256sum "$runner" | cut -d ' ' -f1)" = "$runner_sha"
test "$(sha256sum "$manifest" | cut -d ' ' -f1)" = "$manifest_sha"
test "$(sha256sum "$master" | cut -d ' ' -f1)" = "$master_sha"

cd "$worktree"
env PYTHONHASHSEED=0 "$python" -m pytest phase1/tests/test_foreagent_loeo_graph_denoising.py -q \
  >"$output/focused_tests.stdout" 2>"$output/focused_tests.stderr"
env PYTHONHASHSEED=0 "$python" -m pytest -q \
  >"$output/full_tests.stdout" 2>"$output/full_tests.stderr"

producer_cmd=("$python" -m phase1.analyze_foreagent_loeo_graph_denoising --manifest "$manifest" --master "$master")
env PYTHONHASHSEED=1 timeout 2400s strace -ff -tt -yy -e trace=file,network \
  -o "$output/producer_a.trace" "${producer_cmd[@]}" --output "$output/result_a.json" \
  >"$output/producer_a.stdout" 2>"$output/producer_a.stderr"
env PYTHONHASHSEED=17 timeout 2400s "${producer_cmd[@]}" --output "$output/result_b.json" \
  >"$output/producer_b.stdout" 2>"$output/producer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"

verifier_cmd=("$python" -m phase1.verify_foreagent_loeo_graph_denoising --manifest "$manifest" --master "$master" --result "$output/result_a.json")
env PYTHONHASHSEED=3 timeout 2400s strace -ff -tt -yy -e trace=file,network \
  -o "$output/verifier_a.trace" "${verifier_cmd[@]}" --output "$output/verification_a.json" \
  >"$output/verifier_a.stdout" 2>"$output/verifier_a.stderr"
env PYTHONHASHSEED=29 timeout 2400s "${verifier_cmd[@]}" --output "$output/verification_b.json" \
  >"$output/verifier_b.stdout" 2>"$output/verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"

test ! -s "$output/producer_a.stdout"
test ! -s "$output/producer_b.stdout"
test ! -s "$output/verifier_a.stdout"
test ! -s "$output/verifier_b.stdout"
test ! -s "$output/producer_a.stderr"
test ! -s "$output/producer_b.stderr"
test ! -s "$output/verifier_a.stderr"
test ! -s "$output/verifier_b.stderr"

jq -e '
  .protocol == "foreagent-loeo-graph-denoising-result-v1"
  and .status == "HISTORICAL_PUBLIC_GRAPH_CONSISTENCY_BASELINE_COMPLETE"
  and (.classification == "SUPPORTING_GRAPH_CONSISTENCY_BASELINE_IMPROVES"
       or .classification == "NO_DENOISING_GAIN_MODEL_COMPARISON_REMAINS_STABLE"
       or .classification == "NO_POSITIVE_GRAPH_CONSISTENCY_RESULT")
  and .inputs.manifest_sha256 == "3df2715b2d2e5f3cc6193c07c99eb682e042e8aa6cb724b046b2469b35773a4e"
  and .inputs.master_sha256 == "480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe"
  and .inputs.prospective_sources_read == false
  and .inputs.confidence_values_read == false
  and .population.tasks == 26
  and .population.common_pairs == 18381
  and .population.vertices == 894
  and .population.incidence_rank == 868
  and .method.target_edge_excluded == true
  and .method.labels_used_for_projection == false
  and .claim_boundary.algorithmic_novelty_claimed == false
' "$output/result_a.json" >/dev/null
jq -e '
  .protocol == "foreagent-loeo-graph-denoising-verification-v1"
  and .status == "PASS"
  and .prospective_sources_read == false
  and .confidence_values_read == false
' "$output/verification_a.json" >/dev/null

test -z "$(grep -RIl '/prospective_decision_v1\|first-960\|target522\|score-channel-future-identity-cohort' "$output" --include='*.trace*' || true)"
network_hits=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "$output"/*.trace* | wc -l)
test "$network_hits" = 0
filename_hits=$(find "$output" -type f -printf '%f\n' | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_hits=$(grep -RIlE "$credential_pattern" "$output" || true)
test "$filename_hits" = 0
test -z "$credential_hits"
test -z "$(find "$output" -type l -print -quit)"
test -z "$(find "$output" -type f -perm /022 -print -quit)"
git -C "$worktree" diff --exit-code
git -C "$worktree" diff --cached --exit-code
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"

result_sha=$(sha256sum "$output/result_a.json" | cut -d ' ' -f1)
verification_sha=$(sha256sum "$output/verification_a.json" | cut -d ' ' -f1)
cat >"$output/security_summary.txt" <<EOF
producer_network_hits=$network_hits
credential_filename_hits=$filename_hits
credential_content_hits=0
prospective_sources_read=false
confidence_values_read=false
raw_task_or_endpoint_identities_emitted=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=$expected_commit
protocol_sha256=$protocol_sha
producer_sha256=$producer_sha
verifier_sha256=$verifier_sha
test_sha256=$test_sha
runner_sha256=$runner_sha
manifest_sha256=$manifest_sha
master_sha256=$master_sha
result_sha256=$result_sha
verification_sha256=$verification_sha
EOF

git -C "$repo" worktree remove --force "$worktree"
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=FOREAGENT_LOEO_GRAPH_DENOISING_FORMAL_COMPLETE\nresult_sha256=%s\nverification_sha256=%s\nmanifest_sha256=%s\n' \
  "$result_sha" "$verification_sha" "$(sha256sum "$output/SHA256SUMS" | cut -d ' ' -f1)"
