#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 8 ]]; then
  echo 'usage: run_endpoint_budget_label_efficiency_smoke_formal_20260829.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA FIREWALL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
  exit 64
fi

readonly root=$1
readonly control_commit=$2
readonly protocol_sha=$3
readonly firewall_sha=$4
readonly producer_sha=$5
readonly verifier_sha=$6
readonly test_sha=$7
readonly runner_sha=$8
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly data_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/input-f534114-v3
readonly cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
readonly protocol_rel=phase1/endpoint_budget_label_efficiency_smoke_v1.json
readonly firewall_rel=phase1/export_endpoint_budget_train_only_firewall.py
readonly producer_rel=phase1/endpoint_budget_label_efficiency_smoke.py
readonly verifier_rel=phase1/verify_endpoint_budget_label_efficiency_smoke.py
readonly test_rel=phase1/tests/test_endpoint_budget_label_efficiency_smoke.py
readonly runner_rel=phase1/scripts/run_endpoint_budget_label_efficiency_smoke_formal_20260829.sh

[[ $root =~ ^/research/d7/spc/yzyang4/endpoint-label-efficiency-smoke/formal-[A-Za-z0-9._-]+$ ]]
[[ $control_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$protocol_sha" "$firewall_sha" "$producer_sha" "$verifier_sha" "$test_sha" "$runner_sha"; do
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
02_goal=test whether topology-only yield-guarded breadth produces a more label-efficient held-run char-TFIDF critic than exact-endpoint-budget uniform-edge at two frozen budgets; PASS
03_context=historical topology feasibility and prior predictor aggregates are disclosed; no endpoint-budget-matched accuracy/logloss/Brier comparison or this witness was seen before protocol freeze; PASS
04_population=certified 539-pair senior-0819 strict residual; trusted firewall alone reads raw decision and exports 539 train-only rows; selection and fit receive no raw decision path; PASS
05_split=physical-run SHA256 five-fold split; fold0 evaluation and folds1-4 training; endpoint parent run overlap all zero; senior test and all prospective rows forbidden; PASS
06_estimand=yield-minus-uniform pairwise accuracy at both budgets with terminal logloss Brier and drop-dominant-task safeguards; single-fold smoke only; PASS
07_controls=same outer train/eval population same exact endpoint budgets same fixed code representation and LR; only topology acquisition arm differs; PASS
08_thresholds=eval at least 80 pairs 8 tasks max task share 7/20 and at least 30 induced train pairs per cell; advancement gates frozen with no rescue; PASS
09_randomness=256 fixed uniform seeds; deterministic representative rule; solver seed0/thread1; model random_state0; bootstrap seed20260829 with 2000 task/run-cluster repetitions; PASS
10_resources=CPU single-thread only; four critic fits with atomic per-cell resume; expected 20-45 minutes; GPU/API/base-model-update 0/0/0; PASS
11_outputs=one CSV row per fit plus aggregate summary; private topology labels selection and pair-probability witnesses mode0600; independent verifier performs zero refits; PASS
12_security=credential receipt and exact safe-card hash checked before card parse; key environment unset; raw senior archive and prospective vault paths forbidden; PASS
13_stop=any input hash mode split overlap support solver A/B verifier scanner or network failure stops; limited support or unresolved selection produces no fit; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
test "$(git -C "$repo" show "${control_commit}:${protocol_rel}" | sha256sum | awk '{print $1}')" = "$protocol_sha"
test "$(git -C "$repo" show "${control_commit}:${firewall_rel}" | sha256sum | awk '{print $1}')" = "$firewall_sha"
test "$(git -C "$repo" show "${control_commit}:${producer_rel}" | sha256sum | awk '{print $1}')" = "$producer_sha"
test "$(git -C "$repo" show "${control_commit}:${verifier_rel}" | sha256sum | awk '{print $1}')" = "$verifier_sha"
test "$(git -C "$repo" show "${control_commit}:${test_rel}" | sha256sum | awk '{print $1}')" = "$test_sha"
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
test "$(sha256sum "$worktree/$firewall_rel" | awk '{print $1}')" = "$firewall_sha"
test "$(sha256sum "$worktree/$producer_rel" | awk '{print $1}')" = "$producer_sha"
test "$(sha256sum "$worktree/$verifier_rel" | awk '{print $1}')" = "$verifier_sha"
test "$(sha256sum "$worktree/$test_rel" | awk '{print $1}')" = "$test_sha"
test "$(sha256sum "$worktree/$runner_rel" | awk '{print $1}')" = "$runner_sha"

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

{
  "$python_bin" --version
  "$python_bin" - <<'PY'
import numpy, scipy, sklearn
print("numpy=" + numpy.__version__)
print("scipy=" + scipy.__version__)
print("sklearn=" + sklearn.__version__)
PY
  git -C "$worktree" rev-parse HEAD
  git -C "$worktree" status --porcelain --untracked-files=all
} >"$root/environment.txt" 2>&1

(
  cd "$worktree"
  "$python_bin" -m pytest -q "$test_rel" \
    phase1/tests/test_historical_independent_sibling_graph_gate.py \
    phase1/tests/test_historical_independent_label_scarce_yield.py \
    phase1/tests/test_historical_run_split_breadth_pareto.py >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

mkdir -p "$root/firewall_a" "$root/firewall_b"
firewall_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$control_commit"
  --worktree "$worktree"
  --data-root "$data_root"
  --cards-root "$cards_root"
)
env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/firewall_a.strace" \
  "$python_bin" -m phase1.export_endpoint_budget_train_only_firewall \
  "${firewall_common[@]}" \
  --receipt-output "$root/firewall_a/receipt.json" \
  --topology-output "$root/firewall_a/topology.json" \
  --labels-output "$root/firewall_a/labels.json" >"$root/firewall_a/stdout.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/firewall_b.strace" \
  "$python_bin" -m phase1.export_endpoint_budget_train_only_firewall \
  "${firewall_common[@]}" \
  --receipt-output "$root/firewall_b/receipt.json" \
  --topology-output "$root/firewall_b/topology.json" \
  --labels-output "$root/firewall_b/labels.json" >"$root/firewall_b/stdout.json"
for name in receipt.json topology.json labels.json stdout.json; do
  cmp "$root/firewall_a/$name" "$root/firewall_b/$name"
done

selection_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$control_commit"
  --firewall-receipt "$root/firewall_a/receipt.json"
  --train-topology "$root/firewall_a/topology.json"
)
env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/selection_a.strace" \
  "$python_bin" -m phase1.endpoint_budget_label_efficiency_smoke select \
  "${selection_common[@]}" \
  --public-output "$root/selection_a.public.json" \
  --private-output "$root/selection_a.private.json" >"$root/selection_a.stdout.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/selection_b.strace" \
  "$python_bin" -m phase1.endpoint_budget_label_efficiency_smoke select \
  "${selection_common[@]}" \
  --public-output "$root/selection_b.public.json" \
  --private-output "$root/selection_b.private.json" >"$root/selection_b.stdout.json"
cmp "$root/selection_a.public.json" "$root/selection_b.public.json"
cmp "$root/selection_a.stdout.json" "$root/selection_b.stdout.json"
readonly selection_class=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/selection_a.public.json")
printf '%s\n' "$selection_class" >"$root/selection_classification.txt"

if [[ $selection_class = ENDPOINT_BUDGET_LABEL_EFFICIENCY_SMOKE_SELECTION_READY ]]; then
  test -f "$root/selection_a.private.json"
  test -f "$root/selection_b.private.json"
  cmp "$root/selection_a.private.json" "$root/selection_b.private.json"
  mkdir -p "$root/fit/checkpoints"
  cat >"$root/fit_resume_contract.txt" <<EOF
checkpoint_dir=$root/fit/checkpoints
completed cells are immutable mode-0600 JSON and are verified before reuse
rerun the exact fit command from this public commit with the same protocol/firewall/selection paths and fresh final output paths
EOF
  env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/fit.strace" \
    "$python_bin" -m phase1.endpoint_budget_label_efficiency_smoke fit \
    "${selection_common[@]}" \
    --train-labels "$root/firewall_a/labels.json" \
    --cards-root "$cards_root" \
    --selection-public "$root/selection_a.public.json" \
    --selection-private "$root/selection_a.private.json" \
    --checkpoint-dir "$root/fit/checkpoints" \
    --summary-output "$root/fit/summary.json" \
    --runs-csv "$root/fit/runs.csv" \
    --private-pairs-output "$root/fit/private_pairs.json" >"$root/fit/stdout.json"

  verifier_common=(
    --protocol "$worktree/$protocol_rel"
    --protocol-sha256 "$protocol_sha"
    --firewall-receipt "$root/firewall_a/receipt.json"
    --train-topology "$root/firewall_a/topology.json"
    --selection-public "$root/selection_a.public.json"
    --selection-private "$root/selection_a.private.json"
    --summary "$root/fit/summary.json"
    --runs-csv "$root/fit/runs.csv"
    --private-pairs "$root/fit/private_pairs.json"
    --checkpoint-dir "$root/fit/checkpoints"
  )
  env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
    "$python_bin" -m phase1.verify_endpoint_budget_label_efficiency_smoke \
    "${verifier_common[@]}" --output "$root/verifier_a.json" >"$root/verifier_a.stdout.json"
  env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
    "$python_bin" -m phase1.verify_endpoint_budget_label_efficiency_smoke \
    "${verifier_common[@]}" --output "$root/verifier_b.json" >"$root/verifier_b.stdout.json"
  cmp "$root/verifier_a.json" "$root/verifier_b.json"
  cmp "$root/verifier_a.stdout.json" "$root/verifier_b.stdout.json"
  readonly final_class=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/fit/summary.json")
else
  test ! -e "$root/selection_a.private.json"
  test ! -e "$root/selection_b.private.json"
  readonly final_class=$selection_class
fi
printf '%s\n' "$final_class" >"$root/final_classification.txt"

if grep -Ehi '/prospective_decision_v1|/first[-_]?960|/target[-_]?(300|522)|/label_vault|/outcome_files|/\.env([" ]|$)' "$root"/*.strace* >"$root/forbidden_all_stage_opens.txt"; then
  exit 81
fi
if grep -Ehi 'decision\.jsonl|runsplit_holdruns\.json|firewall_a/labels\.json|cards\.safe\.json' "$root"/selection_*.strace* >"$root/selection_boundary_violations.txt"; then
  exit 82
fi
if test -e "$root/fit/summary.json"; then
  if grep -Ehi 'decision\.jsonl|runsplit_holdruns\.json' "$root"/fit.strace* >"$root/fit_raw_decision_violations.txt"; then
    exit 83
  fi
  if grep -Ehi 'decision\.jsonl|runsplit_holdruns\.json|firewall_a/labels\.json|cards\.safe\.json' "$root"/verifier_*.strace* >"$root/verifier_boundary_violations.txt"; then
    exit 84
  fi
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 85
fi

git -C "$repo" diff-tree --no-commit-id --name-only -r -z "$control_commit" >"$root/changed_files.zlist"
if tr '\0' '\n' <"$root/changed_files.zlist" | grep -Ei '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' >"$root/credential_filename_hits.txt"; then
  exit 86
fi
readonly credential_value_pattern='(^|[^[:alpha:]])sk-(or-v1-|ws-)?[A-Za-z0-9._-]{20,}|(api[_ -]?key|token|secret)[[:space:]]*[:=][[:space:]]*[^][[:space:]]{20,}'
synthetic_secret=$(printf 's%s%024d' 'k-' 0)
if ! printf '%s\n' "$synthetic_secret" | grep -E -i -q "$credential_value_pattern"; then
  exit 87
fi
unset synthetic_secret
: >"$root/credential_blob_hits.txt"
while IFS= read -r -d '' changed; do
  if git -C "$repo" cat-file -e "${control_commit}:${changed}" 2>/dev/null; then
    if git -C "$repo" show "${control_commit}:${changed}" \
      | grep -E -i -n "$credential_value_pattern" \
      >>"$root/credential_blob_hits.txt"; then
      exit 88
    fi
  fi
done <"$root/changed_files.zlist"

printf '%s\n' \
  'historical_train_only=true' \
  'raw_decision_path_passed_to_selection=false' \
  'raw_decision_path_passed_to_fit=false' \
  'senior_test_rows_exported=0' \
  'prospective_values_used=false' \
  'gpu_api_base_model_update=0/0/0' \
  'critic_model_fits=0_or_4_after_structural_gate' \
  'independent_verifier_model_refits=0' >"$root/scope_receipt.txt"

find "$root" -type f ! -path "$root/worktree/*" ! -name SHA256SUMS ! -name COMPLETE -print0 \
  | sort -z | xargs -0 sha256sum >"$root/SHA256SUMS"
printf '%s\n' "$(sha256sum "$root/SHA256SUMS" | awk '{print $1}')" >"$root/MANIFEST_SHA256"
touch "$root/COMPLETE"
trap - EXIT
printf 'FORMAL_COMPLETE root=%s classification=%s manifest=%s\n' \
  "$root" "$final_class" "$(tr -d '\r\n' <"$root/MANIFEST_SHA256")"
