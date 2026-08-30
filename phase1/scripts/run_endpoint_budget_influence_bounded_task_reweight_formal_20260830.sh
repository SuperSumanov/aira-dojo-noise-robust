#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -Eeo pipefail
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 7 ]]; then
  echo 'usage: run_endpoint_budget_influence_bounded_task_reweight_formal_20260830.sh OUTPUT_ROOT CONTROL_COMMIT PROTOCOL_SHA PRODUCER_SHA VERIFIER_SHA TEST_SHA RUNNER_SHA' >&2
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
readonly source_root=/research/d7/spc/yzyang4/endpoint-label-efficiency-smoke/formal-9f9705a-r1
readonly cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
readonly protocol_rel=phase1/endpoint_budget_influence_bounded_task_reweight_v1.json
readonly old_protocol_rel=phase1/endpoint_budget_label_efficiency_smoke_v1.json
readonly producer_rel=phase1/evaluate_endpoint_budget_influence_bounded_task_reweight.py
readonly verifier_rel=phase1/verify_endpoint_budget_influence_bounded_task_reweight.py
readonly test_rel=phase1/tests/test_endpoint_budget_influence_bounded_task_reweight.py
readonly runner_rel=phase1/scripts/run_endpoint_budget_influence_bounded_task_reweight_formal_20260830.sh

[[ $root =~ ^/research/d7/spc/yzyang4/endpoint-influence-bounded-task-reweight/formal-[A-Za-z0-9._-]+$ ]]
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
  if (( rc != 0 )); then
    printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; CURRENT_DIRECTION 2026-08-30 read before design; PASS
02_goal=retain both old yield-selected pair sets and test one closed-form influence-bounded task-density correction without changing acquisition representation optimizer or evaluation; PASS
03_context=all old fold0 uniform yield and failed distribution-matched-selection aggregates plus direct and square-root structural diagnostics are disclosed in protocol; no influence-bounded weight model prediction or metric existed at freeze; PASS
04_population=exact historical smoke firewall 539 intask-train rows with folds1-4 train and fold0 eval; old selection and prediction artifacts are SHA-bound; senior test and all prospective rows forbidden; PASS
05_split=physical-run SHA256 fold assignment unchanged; train/eval endpoint parent run overlap zero; same 138 evaluation pairs and old baseline prediction witnesses; PASS
06_estimand=primary task-macro accuracy delta new-minus-old-yield at budgets96 and192 with pooled proper-score task-sign and drop-dominant safeguards; historical development only; PASS
07_controls=old yield endpoint selections all induced pairs char-wb TFIDF C0.5 lbfgs and evaluation unchanged; only antisymmetrically duplicated sample weights change; PASS
08_weight=direct task availability-to-selected density ratio shrunk toward one by maximum closed-form lambda satisfying ESS fraction at least7/10 and single-pair share at most1/20; no grid clipping temperature or result choice; PASS
09_randomness=model random_state0 PYTHONHASHSEED0 single-thread BLAS; bootstrap seed20260830 with2000 task run and task-macro repetitions; PASS
10_resources=CPU only two critic fits with atomic mode0600 checkpoints expected20-45minutes; GPU paid-API base-model-update 0/0/0; PASS
11_outputs=CSV one row per fit aggregate summary structural weight receipts private hashed pair witness and two independent zero-refit verifier runs; all budgets reported; PASS
12_security=credential-first safe cards exact SHA and old firewall private modes checked; API variables unset; prospective vault and network forbidden; staged and commit blobs scanned including accessToken query values; PASS
13_stop=any hash mode split source support weight influence ESS L1 test verifier scanner network or manifest mismatch stops; any efficacy gate failure does not advance and cannot be rescued on fold0; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${control_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$control_commit" fork/phase1-value-critic
for item in \
  "$protocol_rel:$protocol_sha" \
  "$producer_rel:$producer_sha" \
  "$verifier_rel:$verifier_sha" \
  "$test_rel:$test_sha" \
  "$runner_rel:$runner_sha"; do
  relative=${item%%:*}
  expected=${item##*:}
  test "$(git -C "$repo" show "${control_commit}:${relative}" | sha256sum | awk '{print $1}')" = "$expected"
done

test -d "$source_root"
test "$(sha256sum "$source_root/selection_a.public.json" | awk '{print $1}')" = d1e4274b1046c4e4fea294818beb5522fcdd352a9379a2d72e8bc3255b59bd15
test "$(sha256sum "$source_root/selection_a.private.json" | awk '{print $1}')" = ab4c76721964b3a7c8554e551c5bc524043f111eb52c7a3eddec952553bb1445
test "$(sha256sum "$source_root/firewall_a/topology.json" | awk '{print $1}')" = 832d892a69046a8cef72263fac2ea63ce2a79be8a132f761112a625328273c70
test "$(sha256sum "$source_root/firewall_a/labels.json" | awk '{print $1}')" = 12240a6d67c31d1b17f1ac6ae2b2ebe7ef57303ff05c1d97bc71aabe4161a0e6
test "$(sha256sum "$source_root/fit/private_pairs.json" | awk '{print $1}')" = 1f9bcb84fe6652c8801ce3872f2c9bdc830c8d2dcaa8347eaaa9bb567f1300ce
test "$(sha256sum "$cards_root/cards.safe.json" | awk '{print $1}')" = 5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343
test "$(sha256sum "$cards_root/security_scan.json" | awk '{print $1}')" = d41142279bdba7db4495664df6836eecec3a36016cd316164ee5e54d4518eccc

readonly worktree=$root/worktree
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$control_commit"
test -z "$(git -C "$worktree" status --porcelain --untracked-files=all)"
for item in \
  "$protocol_rel:$protocol_sha" \
  "$producer_rel:$producer_sha" \
  "$verifier_rel:$verifier_sha" \
  "$test_rel:$test_sha" \
  "$runner_rel:$runner_sha"; do
  relative=${item%%:*}
  expected=${item##*:}
  test "$(sha256sum "$worktree/$relative" | awk '{print $1}')" = "$expected"
done

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
    phase1/tests/test_endpoint_budget_label_efficiency_smoke.py \
    phase1/tests/test_endpoint_budget_task_heterogeneity_audit.py \
    phase1/tests/test_endpoint_budget_distribution_matched_yield_screen.py >"$root/focused_tests.txt"
  "$python_bin" -m pytest -q phase1/tests >"$root/full_tests.txt"
)

mkdir -p "$root/fit/checkpoints"
cat >"$root/fit_resume_contract.txt" <<EOF
checkpoint_dir=$root/fit/checkpoints
completed cells are immutable mode-0600 JSON and are independently verified before reuse
rerun the exact producer command from control_commit=$control_commit with the same protocol source and cards roots
EOF

env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/producer.strace" \
  "$python_bin" -m phase1.evaluate_endpoint_budget_influence_bounded_task_reweight \
  --protocol "$worktree/$protocol_rel" \
  --protocol-sha256 "$protocol_sha" \
  --source-commit "$control_commit" \
  --old-protocol "$worktree/$old_protocol_rel" \
  --source-root "$source_root" \
  --cards-root "$cards_root" \
  --checkpoint-dir "$root/fit/checkpoints" \
  --summary-output "$root/fit/summary.json" \
  --runs-csv "$root/fit/runs.csv" \
  --private-pairs-output "$root/fit/private_pairs.json" >"$root/fit/stdout.json"

verifier_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --source-commit "$control_commit"
  --source-root "$source_root"
  --summary "$root/fit/summary.json"
  --runs-csv "$root/fit/runs.csv"
  --private-pairs "$root/fit/private_pairs.json"
  --checkpoint-dir "$root/fit/checkpoints"
)
env PYTHONHASHSEED=0 strace -ff -e trace=file,network -o "$root/verifier_a.strace" \
  "$python_bin" -m phase1.verify_endpoint_budget_influence_bounded_task_reweight \
  "${verifier_common[@]}" --output "$root/verifier_a.json" >"$root/verifier_a.stdout.json"
env PYTHONHASHSEED=1 strace -ff -e trace=file,network -o "$root/verifier_b.strace" \
  "$python_bin" -m phase1.verify_endpoint_budget_influence_bounded_task_reweight \
  "${verifier_common[@]}" --output "$root/verifier_b.json" >"$root/verifier_b.stdout.json"
cmp "$root/verifier_a.json" "$root/verifier_b.json"
cmp "$root/verifier_a.stdout.json" "$root/verifier_b.stdout.json"

readonly final_class=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/fit/summary.json")
printf '%s\n' "$final_class" >"$root/final_classification.txt"

if grep -Ehi '/prospective_decision_v1|/first[-_]?960|/target[-_]?(300|522)|/label_vault|/outcome_files|/\.env([" ]|$)' \
  "$root"/*.strace* >"$root/forbidden_all_stage_opens.txt"; then
  exit 81
fi
if grep -Ehi 'cards\.safe\.json' "$root"/verifier_*.strace* >"$root/verifier_card_violations.txt"; then
  exit 82
fi
if grep -Eh 'connect\(|sendto\(|socket\(' "$root"/*.strace* >"$root/network_calls.txt"; then
  exit 83
fi

git -C "$repo" diff-tree --no-commit-id --name-only -r -z "$control_commit" >"$root/changed_files.zlist"
if tr '\0' '\n' <"$root/changed_files.zlist" | grep -Ei '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' >"$root/credential_filename_hits.txt"; then
  exit 84
fi
readonly credential_pattern='(^|[^[:alnum:]_])s''k-(or-v1-|ws-)?[A-Za-z0-9._-]{20,}|access''Token=[A-Za-z0-9._-]{20,}|(api[_ -]?key|token|secret)[[:space:]]*[:=][[:space:]]*[^][[:space:]]{20,}'
synthetic_secret=$(printf 's%s%024d' 'k-' 0)
if ! printf '%s\n' "$synthetic_secret" | grep -E -i -q "$credential_pattern"; then
  exit 85
fi
while IFS= read -r -d '' relative; do
  git -C "$repo" show "${control_commit}:${relative}" >"$root/blob_scan.tmp"
  if grep -E -i -q "$credential_pattern" "$root/blob_scan.tmp"; then
    printf '%s\0' "$relative" >>"$root/credential_blob_hits.zlist"
  fi
done <"$root/changed_files.zlist"
rm -f "$root/blob_scan.tmp"
test ! -s "$root/credential_blob_hits.zlist"
: >"$root/credential_blob_hits.txt"

find "$root" -type f \
  ! -name 'SHA256SUMS' \
  ! -name 'MANIFEST_SHA256' \
  ! -name 'COMPLETE' \
  ! -name 'FAILED_RC' \
  ! -path "$root/worktree/.git" \
  -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >"$root/SHA256SUMS"
sha256sum "$root/SHA256SUMS" | awk '{print $1}' >"$root/MANIFEST_SHA256"
chmod -R a-w "$root/fit" "$root/verifier_a.json" "$root/verifier_b.json"
: >"$root/COMPLETE"
trap - EXIT
printf 'COMPLETE classification=%s root=%s manifest=%s\n' "$final_class" "$root" "$(cat "$root/MANIFEST_SHA256")"
