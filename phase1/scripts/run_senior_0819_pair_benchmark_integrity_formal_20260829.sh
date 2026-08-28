#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 7 ]]; then
  echo 'usage: run_senior_0819_pair_benchmark_integrity_formal_20260829.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi

readonly root=$1
readonly control_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly test_sha=$6
readonly runner_sha=$7
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly data_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/input-f534114-v3
readonly cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
readonly senior_commit=f534114e60658043c07f7a15d6440492caffc8ad
readonly protocol_rel=phase1/senior_0819_pair_benchmark_integrity_v1.json
readonly producer_rel=phase1/audit_senior_0819_pair_benchmark_integrity.py
readonly verifier_rel=phase1/verify_senior_0819_pair_benchmark_integrity.py
readonly test_rel=phase1/tests/test_senior_0819_pair_benchmark_integrity.py
readonly runner_rel=phase1/scripts/run_senior_0819_pair_benchmark_integrity_formal_20260829.sh
[[ $root =~ ^/research/d7/spc/yzyang4/senior-0828-pair-audit/formal-[A-Za-z0-9._-]+$ ]]
[[ $control_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$root"
mkdir -p "$root"
exec 9>"$root/formal.lock"
flock -n 9
printf '%s\n' "$$" >"$root/formal.pid"
failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_role=historical senior-0819 pair benchmark integrity and dependency audit,not effect scoring; PASS
03_inputs=exact Git-LFS OIDs and credential-cleared Card map bound by protocol ${protocol_sha}; PASS
04_known_before=reported proxy values,row counts,and schemas only; overlap/component/run results unseen at freeze; PASS
05_population=mixed historical train/test with decision/value/hardware-time source support; PASS
06_estimand=run/endpoint separation,test preservation,and dependence breadth; no accuracy or search utility; PASS
07_controls=exact decision test multiset and declared source train union; PASS
08_randomness=none,producer/verifier repeated under PYTHONHASHSEED 0 and 1; PASS
09_resources=CPU only,0 GPU,0 API,0 model fit,0 base update; PASS
10_leakage=no first-960,target-300,prospective state,raw archive,outcome,or prediction files; PASS
11_security=Card credential scan precedes JSON parse; aggregate output contains no identities or row values; PASS
12_stop=hash/schema/run/split/source ambiguity fails closed; no result-dependent threshold rescue; PASS
13_reproducibility=exact commit/source hashes,commands,tests,strace,and manifest recorded; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
git -C "$repo" cat-file -e "${senior_commit}^{commit}"
test "$(git -C "$repo" show "${senior_commit}:src/mle_critic/src/postprocess/build_decision_augment_pairs.py" | sha256sum | awk '{print $1}')" = e7302d5fe7b914682b3327ea23022d2560fb54c348ed80e6fe40a5a065e71e63
test "$(git -C "$repo" show "${senior_commit}:src/mle_critic/src/preprocess/build_bt_pairs/apply_runsplit.py" | sha256sum | awk '{print $1}')" = 4c110661b39cb5cb83bd2cd7670420d9a38cb77f0de3f66e2b53a3f10363fc08
test "$(git -C "$repo" show "${senior_commit}:src/mle_critic/src/preprocess/download_and_resolve/build_runsplit.py" | sha256sum | awk '{print $1}')" = bb5b5c98cbe5ce6b38f350eb72d7e34ba4b9c4b9c633eeab88ea7568b564402b
test "$(git -C "$repo" show "${control_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${control_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${control_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$data_root/mixed.jsonl" | awk '{print $1}')" = 7792a7da4119bb607cf76628fcdde19923898651ac734ff6afffb0732883cf6e
test "$(sha256sum "$data_root/decision.jsonl" | awk '{print $1}')" = 1a01d3a1202b35f21b9cd6c87237b29c50b1c293138b407cc453674108411442
test "$(sha256sum "$data_root/value.jsonl" | awk '{print $1}')" = 8a01dfb90c2c3d8498174ebe78df43ee21d6d0eac9f4ff81f63700b315473405
test "$(sha256sum "$data_root/value_hardware_time.jsonl" | awk '{print $1}')" = 60e9bbfba56ef94dfd70bb717694fa5b3b400f9458a13b92321bb1cb2ecdf3d9
test "$(sha256sum "$data_root/runsplit_holdruns.json" | awk '{print $1}')" = 593117cfe0b34e1d2e3c9b718866a7751d7f008701add77b31cfd604282103bb
test "$(sha256sum "$cards_root/cards.safe.json" | awk '{print $1}')" = 5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343
"$python_bin" - "$cards_root/security_scan.json" <<'PY'
import json, pathlib, sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert value["status"] == "CREDENTIAL_SCAN_AND_REDACTION_PASS"
assert value["input_sha256"] == value["safe_sha256"] == "5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343"
assert value["remaining_credential_hits"] == value["private_key_markers"] == 0
assert value["json_parsed_before_scan"] is False
PY

readonly worktree=$root/worktree
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$control_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"

export CUDA_VISIBLE_DEVICES=''
export WANDB_MODE=disabled
export PYTHONPATH="$worktree"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1
unset OPENAI_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

(
  cd "$worktree"
  "$python_bin" -m pytest -q "$test_rel" >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$senior_commit"
  --cards "$cards_root/cards.safe.json"
  --cards-security-receipt "$cards_root/security_scan.json"
  --run-split "$data_root/runsplit_holdruns.json"
  --mixed "$data_root/mixed.jsonl"
  --decision "$data_root/decision.jsonl"
  --value "$data_root/value.jsonl"
  --value-hardware-time "$data_root/value_hardware_time.jsonl"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer_a.strace" \
  "$python_bin" -m phase1.audit_senior_0819_pair_benchmark_integrity \
  "${common[@]}" --output "$root/producer_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/producer_b.strace" \
  "$python_bin" -m phase1.audit_senior_0819_pair_benchmark_integrity \
  "${common[@]}" --output "$root/producer_b.json"
cmp "$root/producer_a.json" "$root/producer_b.json"

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" -m phase1.verify_senior_0819_pair_benchmark_integrity \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" -m phase1.verify_senior_0819_pair_benchmark_integrity \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_b.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"

"$python_bin" - "$root/producer_a.json" "$root/verifier_a.json" <<'PY'
import json, pathlib, sys
producer = json.loads(pathlib.Path(sys.argv[1]).read_text())
verifier = json.loads(pathlib.Path(sys.argv[2]).read_text())
allowed = {
    "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_BROAD_SUPPORT",
    "HISTORICAL_RUN_ENDPOINT_DISJOINT_EXACT_TEST_PRESERVATION_LIMITED_BREADTH",
    "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_GATE_FAIL",
}
assert producer["classification"] in allowed
assert producer["status"] == "HISTORICAL_PAIR_BENCHMARK_INTEGRITY_AUDIT_COMPLETE"
assert verifier["status"] == "INDEPENDENT_HISTORICAL_PAIR_BENCHMARK_INTEGRITY_VERIFIED"
assert verifier["classification"] == producer["classification"]
assert verifier["all_aggregate_fields_equal"] is True
assert verifier["producer_imported"] is False
assert producer["scope"]["prospective_first960_or_target300_values_read"] is False
assert producer["scope"]["test_accuracy_or_scaling_computed"] is False
assert producer["scope"]["gpu_jobs"] == producer["scope"]["api_calls"] == 0
assert producer["scope"]["model_fits"] == producer["scope"]["base_llm_updates"] == 0
PY

if grep -Ehi '/external/senior_data|prospective_decision_v1|first[-_]?960|target[-_]?300|/\.env([" ]|$)|label_vault|outcome_files|prediction[^/]*\.(json|jsonl|csv)' "$root"/*.strace* >"$root/forbidden_opens.txt"; then
  exit 87
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 88
fi

printf '%s\n' \
  'prospective_first960_or_target300_values_read=false' \
  'test_accuracy_or_scaling_computed=false' \
  'raw_senior_archives_opened=false' \
  'identities_or_row_values_emitted=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' >"$root/security_scope.txt"

find "$root" -type f ! -path "$root/worktree/*" ! -name SHA256SUMS ! -name COMPLETE -print0 \
  | sort -z | xargs -0 sha256sum >"$root/SHA256SUMS"
printf '%s\n' "$(sha256sum "$root/SHA256SUMS" | awk '{print $1}')" >"$root/MANIFEST_SHA256"
touch "$root/COMPLETE"
trap - EXIT
printf 'FORMAL_COMPLETE root=%s classification=%s manifest=%s\n' \
  "$root" \
  "$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/producer_a.json")" \
  "$(tr -d '\r\n' <"$root/MANIFEST_SHA256")"
