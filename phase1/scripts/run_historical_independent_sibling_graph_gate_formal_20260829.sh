#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 8 ]]; then
  echo 'usage: run_historical_independent_sibling_graph_gate_formal_20260829.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA PRODUCER_TEST_SHA VERIFIER_TEST_SHA RUNNER_SHA' >&2
  exit 64
fi

readonly root=$1
readonly control_commit=$2
readonly protocol_sha=$3
readonly producer_sha=$4
readonly verifier_sha=$5
readonly producer_test_sha=$6
readonly verifier_test_sha=$7
readonly runner_sha=$8
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly data_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/input-f534114-v3
readonly cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
readonly protocol_rel=phase1/historical_independent_sibling_graph_gate_v1.json
readonly producer_rel=phase1/audit_historical_independent_sibling_graph_gate.py
readonly verifier_rel=phase1/verify_historical_independent_sibling_graph_gate.py
readonly producer_test_rel=phase1/tests/test_historical_independent_sibling_graph_gate.py
readonly verifier_test_rel=phase1/tests/test_verify_historical_independent_sibling_graph_gate.py
readonly runner_rel=phase1/scripts/run_historical_independent_sibling_graph_gate_formal_20260829.sh
readonly v11_rel=phase1/v11_decision/decision_train_v11_b0.jsonl
readonly lineage_rel=phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/formal/producer_a.json
readonly senior_protocol_rel=phase1/senior_0819_verified_sibling_quarantine_v1.json
readonly senior_package=phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80

[[ $root =~ ^/research/d7/spc/yzyang4/historical-independent-sibling-graph/formal-[A-Za-z0-9._-]+$ ]]
[[ $control_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$producer_sha" "$verifier_sha" "$producer_test_sha" "$verifier_test_sha" "$runner_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$root"
mkdir -p "$root"
exec 9>"$root/formal.lock"
flock -n 9
printf '%s\n' "$$" >"$root/formal.pid"
failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_goal=qualify one historical train-only direct-sibling graph strictly independent of v11 b0 before any second acquisition curve; PASS
03_context=frozen v11 lineage and senior-0819 quarantine certificates plus credential-cleared immutable inputs; PASS
04_known_before=v11 b0 curve and budget-variant collision known; senior crosswalk residual counts and curves unseen; PASS
05_population=exact 952 senior-0819 train core rows; all 318 test core rows forbidden; PASS
06_estimand=deterministic residual support after endpoint parent and physical-run exclusion; no accuracy effect or utility; PASS
07_controls=fixed v11 b0 identity union fixed direct-sibling core exact parent certificates and independent decoder; PASS
08_thresholds=eight support gates and eight integrity gates frozen before crosswalk with no rescue; PASS
09_randomness=none; producer and non-importing verifier repeated under PYTHONHASHSEED 0 and 1; PASS
10_resources=CPU only with one-thread caps; GPU API model-fit base-update 0/0/0/0; PASS
11_leakage=no senior test orientation gap grade code runtime prediction or prospective first960 target300 value use; PASS
12_security=credential receipt required before safe Cards parse; raw senior archives and identity release forbidden; PASS
13_stop=hash certificate overlap duplicate verifier or scanner ambiguity fails closed and cannot alter residual rule or thresholds; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${control_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_test_rel}" | sha256sum | awk '{print $1}')" = "$producer_test_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_test_rel}" | sha256sum | awk '{print $1}')" = "$verifier_test_sha"
test "$(git -C "$repo" show "${control_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$data_root/decision.jsonl" | awk '{print $1}')" = 1a01d3a1202b35f21b9cd6c87237b29c50b1c293138b407cc453674108411442
test "$(sha256sum "$data_root/runsplit_holdruns.json" | awk '{print $1}')" = 593117cfe0b34e1d2e3c9b718866a7751d7f008701add77b31cfd604282103bb
test "$(sha256sum "$cards_root/cards.safe.json" | awk '{print $1}')" = 5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343
test "$(sha256sum "$cards_root/security_scan.json" | awk '{print $1}')" = d41142279bdba7db4495664df6836eecec3a36016cd316164ee5e54d4518eccc
"$python_bin" - "$cards_root/security_scan.json" <<'PY'
import json
import pathlib
import sys

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
test "$(sha256sum "$worktree/$producer_test_rel" | awk '{print $1}')" = "$producer_test_sha"
test "$(sha256sum "$worktree/$verifier_test_rel" | awk '{print $1}')" = "$verifier_test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"

test "$(sha256sum "$worktree/$lineage_rel" | awk '{print $1}')" = 23e9a8139be60ee4c34d3c44eda9afaed3034a68f6749ebcb0555c10a15f0032
test "$(sha256sum "$worktree/$senior_protocol_rel" | awk '{print $1}')" = f4d09f1203ba72181046ac620862eb10351736cd01a25ac3597b21e4b931b680
test "$(sha256sum "$worktree/$senior_package/formal_summary.json" | awk '{print $1}')" = 4f4902ce365523b01a0cca1eadb716b978aa0771d15286be1bf4aecca6456315
test "$(sha256sum "$worktree/$senior_package/verification.json" | awk '{print $1}')" = 8b0eb84365aa3cb16bfd3b9a4ca3affabfc4fd24774071a6cbba366b88f57ca0
test "$(sha256sum "$worktree/$senior_package/MANIFEST.sha256" | awk '{print $1}')" = 3f6202fb14b044a23fbcae722c0c38ab48253bbd5ac9ebe2b4b011f3b7f84a28
(
  cd "$worktree/$senior_package"
  sha256sum -c MANIFEST.sha256 >"$root/senior_package_manifest_check.txt"
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
unset OPENAI_API_KEY OPENROUTER_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

(
  cd "$worktree"
  "$python_bin" -m pytest -q "$producer_test_rel" "$verifier_test_rel" >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --v11-pairs "$worktree/$v11_rel"
  --v11-lineage "$worktree/$lineage_rel"
  --senior-quarantine-protocol "$worktree/$senior_protocol_rel"
  --senior-quarantine-result "$worktree/$senior_package/formal_summary.json"
  --senior-quarantine-verification "$worktree/$senior_package/verification.json"
  --senior-quarantine-manifest "$worktree/$senior_package/MANIFEST.sha256"
  --senior-security-receipt "$cards_root/security_scan.json"
  --senior-cards "$cards_root/cards.safe.json"
  --senior-run-split "$data_root/runsplit_holdruns.json"
  --senior-decision "$data_root/decision.jsonl"
)

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer_a.strace" \
  "$python_bin" -m phase1.audit_historical_independent_sibling_graph_gate \
  "${common[@]}" --output "$root/producer_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/producer_b.strace" \
  "$python_bin" -m phase1.audit_historical_independent_sibling_graph_gate \
  "${common[@]}" --output "$root/producer_b.json"
cmp "$root/producer_a.json" "$root/producer_b.json"

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" -m phase1.verify_historical_independent_sibling_graph_gate \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_a.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" -m phase1.verify_historical_independent_sibling_graph_gate \
  "${common[@]}" --producer-result "$root/producer_a.json" --output "$root/verifier_b.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"

"$python_bin" - "$root/producer_a.json" "$root/verifier_a.json" <<'PY'
import json
import pathlib
import sys

producer = json.loads(pathlib.Path(sys.argv[1]).read_text())
verifier = json.loads(pathlib.Path(sys.argv[2]).read_text())
allowed = {
    "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_INTEGRITY_FAIL",
    "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_LIMITED_SUPPORT",
    "HISTORICAL_SENIOR0819_INDEPENDENT_SIBLING_GRAPH_FEASIBLE",
}
assert producer["classification"] in allowed
assert producer["status"] == "HISTORICAL_INDEPENDENT_SIBLING_GRAPH_GATE_COMPLETE"
assert verifier["status"] == "INDEPENDENT_HISTORICAL_SIBLING_GRAPH_GATE_VERIFIED"
assert verifier["classification"] == producer["classification"]
assert verifier["all_aggregate_fields_equal"] is True
assert verifier["producer_imported"] is False
assert producer["scope"]["population_qualification_only"] is True
assert producer["scope"]["acquisition_curves_computed"] is False
assert producer["scope"]["senior_test_rows_used"] is False
assert producer["scope"]["prospective_first960_target300_values_read"] is False
assert producer["scope"]["raw_senior_archives_opened"] is False
assert producer["scope"]["identities_emitted"] is False
assert producer["scope"]["gpu_api_model_fit_base_update"] == "0/0/0/0"
PY

if grep -Ehi '/external/senior_data|prospective_decision_v1|first[-_]?960|target[-_]?300|/\.env([" ]|$)|label_vault|outcome_files|prediction[^/]*\.(json|jsonl|csv)' "$root"/*.strace* >"$root/forbidden_opens.txt"; then
  exit 87
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 88
fi

git -C "$repo" diff-tree --no-commit-id --name-only -r -z "$control_commit" >"$root/changed_files.zlist"
if tr '\0' '\n' <"$root/changed_files.zlist" | grep -Ei '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' >"$root/credential_filename_hits.txt"; then
  exit 89
fi
: >"$root/credential_blob_hits.txt"
while IFS= read -r -d '' changed; do
  if git -C "$repo" cat-file -e "${control_commit}:${changed}" 2>/dev/null; then
    if git -C "$repo" show "${control_commit}:${changed}" \
      | grep -E -i -n 'sk-[A-Za-z0-9._-]{12,}|(api[_ -]?key|token|secret)[[:space:]]*[:=][[:space:]]*[^][[:space:]]+' \
      >>"$root/credential_blob_hits.txt"; then
      exit 90
    fi
  fi
done <"$root/changed_files.zlist"

printf '%s\n' \
  'population_qualification_only=true' \
  'acquisition_curves_computed=false' \
  'senior_test_rows_used=false' \
  'pair_orientation_gap_grade_code_prediction_runtime_used=false' \
  'prospective_first960_target300_values_read=false' \
  'raw_senior_archives_opened=false' \
  'identities_emitted=false' \
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
