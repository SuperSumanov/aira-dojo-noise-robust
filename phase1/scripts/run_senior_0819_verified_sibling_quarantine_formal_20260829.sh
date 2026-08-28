#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 7 ]]; then
  echo 'usage: run_senior_0819_verified_sibling_quarantine_formal_20260829.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
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
readonly protocol_rel=phase1/senior_0819_verified_sibling_quarantine_v1.json
readonly producer_rel=phase1/audit_senior_0819_verified_sibling_quarantine.py
readonly verifier_rel=phase1/verify_senior_0819_verified_sibling_quarantine.py
readonly test_rel=phase1/tests/test_senior_0819_verified_sibling_quarantine.py
readonly runner_rel=phase1/scripts/run_senior_0819_verified_sibling_quarantine_formal_20260829.sh
readonly parent_package=phase1/results/senior_0819_decision_relation_taxonomy_20260829_827fe55

[[ $root =~ ^/research/d7/spc/yzyang4/senior-0828-sibling-quarantine/formal-[A-Za-z0-9._-]+$ ]]
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
02_goal=test deterministic aggregate-only quarantine feasibility for a partition-closed historical sibling core; PASS
03_context=senior f534114 immutable Cards run-split decision inputs plus published 0HT certificate; PASS
04_known_before=class counts full overlap and sibling support known; sibling-only closure mismatch distribution and quarantine fingerprint unseen; PASS
05_population=all 7644 historical decision rows with fixed core rule and exhaustive quarantine; PASS
06_estimand=core parent task run split closure and three-level train-test isolation; no predictor accuracy or utility; PASS
07_controls=fixed direct-sibling rule parent-certificate fingerprints and all excluded rows retained as aggregate quarantine; PASS
08_thresholds=16 hard gates; descriptive support thresholds reused and explicitly known before this freeze; PASS
09_randomness=none; producer and independent verifier repeated under PYTHONHASHSEED 0 and 1; PASS
10_resources=CPU only with one-thread caps; GPU API model-fit base-update 0/0/0/0; PASS
11_leakage=no prospective first960 target300 raw archive outcome prediction grade or pair-orientation use; PASS
12_security=credential-cleared Card map required before parse; identities never emitted; strace and credential scan; PASS
13_stop=hash certificate partition duplicate overlap or verifier ambiguity fails closed with no rule or threshold rescue; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${control_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${control_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
test "$(git -C "$repo" show "${control_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$data_root/decision.jsonl" | awk '{print $1}')" = 1a01d3a1202b35f21b9cd6c87237b29c50b1c293138b407cc453674108411442
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
test "$(sha256sum "$worktree/$parent_package/formal_summary.json" | awk '{print $1}')" = b75df026fdab24a5a3da6f01d734820ad908e505df0140f13586c2386624c6d3
test "$(sha256sum "$worktree/$parent_package/verification.json" | awk '{print $1}')" = d5613fe7780df6a7c4c894780a44d971ac470af9070d804705b26e729bc0b66a
test "$(sha256sum "$worktree/$parent_package/MANIFEST.sha256" | awk '{print $1}')" = 6ce816faec31d0e807e8859539e05d3ace814954ceea9db4c326828ae928faa7
(
  cd "$worktree/$parent_package"
  sha256sum -c MANIFEST.sha256 >"$root/parent_package_manifest_check.txt"
)

export CUDA_VISIBLE_DEVICES=''
export WANDB_MODE=disabled
export PYTHONPATH="$worktree"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
unset OPENAI_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

(
  cd "$worktree"
  "$python_bin" -m pytest -q "$test_rel" >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --cards "$cards_root/cards.safe.json"
  --run-split "$data_root/runsplit_holdruns.json"
  --decision "$data_root/decision.jsonl"
  --parent-summary "$worktree/$parent_package/formal_summary.json"
  --parent-verification "$worktree/$parent_package/verification.json"
  --parent-package-manifest "$worktree/$parent_package/MANIFEST.sha256"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer_a.strace" \
  "$python_bin" -m phase1.audit_senior_0819_verified_sibling_quarantine \
  "${common[@]}" --output "$root/producer_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/producer_b.strace" \
  "$python_bin" -m phase1.audit_senior_0819_verified_sibling_quarantine \
  "${common[@]}" --output "$root/producer_b.json"
cmp "$root/producer_a.json" "$root/producer_b.json"

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" -m phase1.verify_senior_0819_verified_sibling_quarantine \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" -m phase1.verify_senior_0819_verified_sibling_quarantine \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_b.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"

"$python_bin" - "$root/producer_a.json" "$root/verifier_a.json" <<'PY'
import json, pathlib, sys
p = json.loads(pathlib.Path(sys.argv[1]).read_text())
v = json.loads(pathlib.Path(sys.argv[2]).read_text())
allowed = {
    "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_FEASIBLE",
    "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_LIMITED_SUPPORT",
    "HISTORICAL_VERIFIED_SIBLING_CORE_QUARANTINE_INTEGRITY_GATE_FAIL",
}
assert p["classification"] in allowed
assert p["status"] == "HISTORICAL_VERIFIED_SIBLING_QUARANTINE_AUDIT_COMPLETE"
assert v["status"] == "INDEPENDENT_HISTORICAL_VERIFIED_SIBLING_QUARANTINE_VERIFIED"
assert v["classification"] == p["classification"]
assert v["all_aggregate_fields_equal"] is True
assert v["producer_imported"] is False
assert p["scope"]["support_counts_known_before_freeze"] is True
assert p["scope"]["pair_orientation_used"] is False
assert p["scope"]["prospective_first960_or_target300_values_read"] is False
assert p["scope"]["model_predictions_or_accuracy_read"] is False
assert p["scope"]["identities_or_row_values_emitted"] is False
assert p["scope"]["row_level_release_created"] is False
assert p["scope"]["gpu_jobs"] == p["scope"]["api_calls"] == 0
assert p["scope"]["model_fits"] == p["scope"]["base_llm_updates"] == 0
PY

if grep -Ehi '/external/senior_data|prospective_decision_v1|first[-_]?960|target[-_]?300|/\.env([" ]|$)|label_vault|outcome_files|prediction[^/]*\.(json|jsonl|csv)' "$root"/*.strace* >"$root/forbidden_opens.txt"; then
  exit 87
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 88
fi

printf '%s\n' \
  'prospective_first960_or_target300_values_read=false' \
  'model_predictions_or_accuracy_read=false' \
  'support_counts_known_before_freeze=true' \
  'pair_orientation_used=false' \
  'raw_senior_archives_opened=false' \
  'identities_or_row_values_emitted=false' \
  'row_level_release_created=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' >"$root/scope_receipt.txt"

find "$root" -type f ! -path "$root/worktree/*" ! -name SHA256SUMS ! -name COMPLETE -print0 \
  | sort -z | xargs -0 sha256sum >"$root/SHA256SUMS"
printf '%s\n' "$(sha256sum "$root/SHA256SUMS" | awk '{print $1}')" >"$root/MANIFEST_SHA256"
touch "$root/COMPLETE"
trap - EXIT
printf 'FORMAL_COMPLETE root=%s classification=%s manifest=%s\n' \
  "$root" \
  "$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/producer_a.json")" \
  "$(tr -d '\r\n' <"$root/MANIFEST_SHA256")"
