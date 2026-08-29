#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export CUDA_VISIBLE_DEVICES=''
export WANDB_MODE=disabled
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export PYTHONHASHSEED=0
unset OPENAI_API_KEY OPENROUTER_API_KEY DASHSCOPE_API_KEY DEEPSEEK_API_KEY ANTHROPIC_API_KEY HF_TOKEN WANDB_API_KEY || true

analysis_commit=${1:?analysis commit required}
[[ $analysis_commit =~ ^[0-9a-f]{40}$ ]]

repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
old_root=/research/d7/spc/yzyang4/endpoint-label-efficiency-smoke/formal-9f9705a-r1
cards_root=/research/d7/spc/yzyang4/senior-0828-pair-audit/cards-f534114-v1
evidence_base=/research/d7/spc/yzyang4/endpoint-distribution-matched-yield-screen
v1_root=$evidence_base/formal-68e943d-r1
dp_root=$evidence_base/diagnostic-lower-bound-68e943d-r1
sha_tie_root=$evidence_base/diagnostic-dp-sha-tie-68e943d-r1
root=/research/d7/spc/yzyang4/endpoint-distribution-matched-yield-screen/formal-${analysis_commit:0:7}-r2
worktree=$root/worktree
protocol_rel=phase1/endpoint_budget_distribution_matched_yield_screen_v2.json
protocol_sha=37ad2fab68227d4aa236f1ce8c70c6197d1160b3f885adc466288ea1af41b06e
old_protocol_rel=phase1/endpoint_budget_label_efficiency_smoke_v1.json
task_audit_rel=phase1/results/endpoint_budget_task_heterogeneity_audit_20260829_d2fb68c/public.json

test ! -e "$root"
mkdir -p "$root"
chmod 700 "$root"
failure_receipt() {
  rc=$?
  if test "$rc" != 0 && test ! -e "$root/COMPLETE"; then printf '%s\n' "$rc" >"$root/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT

git -C "$repo" fetch fork phase1-value-critic
test "$(git -C "$repo" rev-parse FETCH_HEAD^{commit})" = "$analysis_commit"
GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$analysis_commit" >/dev/null
test "$(git -C "$worktree" rev-parse HEAD)" = "$analysis_commit"
test -z "$(git -C "$worktree" status --porcelain)"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_goal=test the frozen v2 distribution-matched yield rule with an exact DP lower-bound proof while matching old endpoint and induced-pair counts; PASS
03_context=old efficacy audit v1 RC1 and both structural diagnostics are disclosed; no v2 endpoint witness prediction or task metric was seen; PASS
04_population=bound 539-row train-only firewall with 401 outer-train and 138 held-run evaluation pairs; senior test and prospective cohorts forbidden; PASS
05_split=unchanged salted physical-run fold0 evaluation and folds1-4 training; post-audit historical development only and never confirmation; PASS
06_estimand=new minus old-yield task-macro accuracy at budgets 96 and 192 with pooled proper-score task-sign and robust-vs-uniform secondary checks; PASS
07_controls=exact same endpoints budgets induced-pair counts fixed critic code representation labels evaluation pairs and old prediction witness; only task allocation rule changes; PASS
08_thresholds=seven frozen screen gates including two-budget L1 and task-macro signs terminal pooled macro drop-dominant proper scores and task signs; no rescue; PASS
09_randomness=pinned numpy1.26.4 scipy1.16.2 HiGHS1.8.0 threads1 seed0 constant-objective witness with private A/B identity; LR random_state0; bootstraps fixed; PASS
10_resources=CPU single-thread two new critic fits under 30 minutes expected; GPU paid-API base-update 0/0/0; atomic per-budget resume; PASS
11_outputs=selection public/private A/B fit CSV aggregate and private probabilities plus zero-refit independent primal/aggregate verifier A/B; PASS
12_security=old formal manifest and 11 input SHA bindings checked; credential env unset; selection cannot open labels/cards/predictions and all stages forbid prospective/raw decision/network; PASS
13_stop=any hash mode DP-bound exact-count solver A/B fit checkpoint verifier scanner or manifest failure exits before COMPLETE; failed gates cannot be altered; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

test -f "$old_root/COMPLETE"
test ! -e "$old_root/FAILED_RC"
test "$(tr -d '\r\n' <"$old_root/MANIFEST_SHA256")" = 4995bdf6e936b2e7f62fb9f44174e69cc3752b203a950816b17d2dd01f4c6e38
(cd "$old_root" && sha256sum -c SHA256SUMS >/dev/null)
test "$(sha256sum "$old_root/firewall_a/receipt.json" | awk '{print $1}')" = 9291d9e715ccff4ecdfac39cd462379be2d6ecacedb9e6d38a1762c0e9d64ab3
test "$(sha256sum "$old_root/firewall_a/topology.json" | awk '{print $1}')" = 832d892a69046a8cef72263fac2ea63ce2a79be8a132f761112a625328273c70
test "$(sha256sum "$old_root/firewall_a/labels.json" | awk '{print $1}')" = 12240a6d67c31d1b17f1ac6ae2b2ebe7ef57303ff05c1d97bc71aabe4161a0e6
test "$(sha256sum "$old_root/selection_a.public.json" | awk '{print $1}')" = d1e4274b1046c4e4fea294818beb5522fcdd352a9379a2d72e8bc3255b59bd15
test "$(sha256sum "$old_root/selection_a.private.json" | awk '{print $1}')" = ab4c76721964b3a7c8554e551c5bc524043f111eb52c7a3eddec952553bb1445
test "$(sha256sum "$old_root/fit/summary.json" | awk '{print $1}')" = b8068e691c84c1413d1e21091bde4ef89914dc3a0777ff44ba92bfe57f1ed6ec
test "$(sha256sum "$old_root/fit/private_pairs.json" | awk '{print $1}')" = 1f9bcb84fe6652c8801ce3872f2c9bdc830c8d2dcaa8347eaaa9bb567f1300ce
test "$(sha256sum "$worktree/$task_audit_rel" | awk '{print $1}')" = 001f58d11f13016ba66e09bcee7aabe313f1defa4ad3756153254784343f6ab5
test "$(sha256sum "$cards_root/cards.safe.json" | awk '{print $1}')" = 5e0f38075d841b2e0d9406898f17ac1cc6e6d63667b256fd2880a9ba4266c343
test "$(sha256sum "$cards_root/security_scan.json" | awk '{print $1}')" = d41142279bdba7db4495664df6836eecec3a36016cd316164ee5e54d4518eccc
test "$(sha256sum "$evidence_base/launch-68e943d.log" | awk '{print $1}')" = 330e2058995c3955ff579e179132bc99e4d54e5df64b9f870a2192a716dd51a6
test "$(sha256sum "$v1_root/FAILED_RC" | awk '{print $1}')" = 4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865
test "$(tr -d '\r\n' <"$v1_root/FAILED_RC")" = 1
test ! -e "$v1_root/selection_a.public.json"
test ! -e "$v1_root/selection_a.private.json"
test ! -e "$v1_root/fit/summary.json"
test -f "$dp_root/COMPLETE"
test "$(sha256sum "$dp_root/public.json" | awk '{print $1}')" = 75e54acea9e5f797ab11d283c620ec332ee5ffc35ac8fa745f7c7f42a03cee54
test "$(sha256sum "$dp_root/preflight_13.txt" | awk '{print $1}')" = e1d96cae958d55389632b85f9791efb38cabdfcd6410234af195a4ecc83c36c0
test "$(sha256sum "$evidence_base/diagnose-dp-sha-tie-68e943d.log" | awk '{print $1}')" = bb4e51ca70bb3d260db2732147fb814ed242cf1baed4c2330b8d0ffb924fcecc
test "$(sha256sum "$sha_tie_root/preflight_13.txt" | awk '{print $1}')" = 55352253e15c5ef9c464f34b9bc4047ce201865e682e34bb6b53d25a1d1b5244
test ! -e "$sha_tie_root/public.json"
test ! -e "$sha_tie_root/COMPLETE"

(cd "$worktree" && "$python_bin" -m pytest -q \
  phase1/tests/test_endpoint_budget_distribution_matched_yield_screen.py \
  phase1/tests/test_endpoint_budget_label_efficiency_smoke.py \
  phase1/tests/test_endpoint_budget_task_heterogeneity_audit.py) >"$root/focused_tests.txt"
(cd "$worktree" && "$python_bin" -m pytest -q phase1/tests) >"$root/full_tests.txt"

selection_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --analysis-source-commit "$analysis_commit"
  --old-protocol "$worktree/$old_protocol_rel"
  --firewall-receipt "$old_root/firewall_a/receipt.json"
  --train-topology "$old_root/firewall_a/topology.json"
  --old-selection-public "$old_root/selection_a.public.json"
  --old-selection-private "$old_root/selection_a.private.json"
  --task-audit-public "$worktree/$task_audit_rel"
)
for replica in a b; do
  (cd "$worktree" && strace -ff -e trace=file,network -o "$root/selection_${replica}.strace" \
    "$python_bin" -m phase1.screen_endpoint_budget_distribution_matched_yield select \
    "${selection_common[@]}" --time-limit-seconds 300 \
    --public-output "$root/selection_${replica}.public.json" \
    --private-output "$root/selection_${replica}.private.json") >"$root/selection_${replica}.stdout.json"
done
cmp "$root/selection_a.public.json" "$root/selection_b.public.json"
cmp "$root/selection_a.private.json" "$root/selection_b.private.json"
test "$($python_bin -c 'import json,sys; print(json.load(open(sys.argv[1]))["classification"])' "$root/selection_a.public.json")" = DISTRIBUTION_MATCHED_YIELD_SELECTION_OPTIMAL

mkdir -p "$root/fit/checkpoints"
fit_common=(
  "${selection_common[@]}"
  --train-labels "$old_root/firewall_a/labels.json"
  --cards-root "$cards_root"
  --old-fit-summary "$old_root/fit/summary.json"
  --old-private-pairs "$old_root/fit/private_pairs.json"
  --selection-public "$root/selection_a.public.json"
  --selection-private "$root/selection_a.private.json"
  --checkpoint-dir "$root/fit/checkpoints"
)
(cd "$worktree" && strace -ff -e trace=file,network -o "$root/fit.strace" \
  "$python_bin" -m phase1.screen_endpoint_budget_distribution_matched_yield fit \
  "${fit_common[@]}" \
  --summary-output "$root/fit/summary.json" \
  --runs-csv "$root/fit/runs.csv" \
  --private-pairs-output "$root/fit/private_pairs.json") >"$root/fit/stdout.json"

verify_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --old-protocol "$worktree/$old_protocol_rel"
  --firewall-receipt "$old_root/firewall_a/receipt.json"
  --train-topology "$old_root/firewall_a/topology.json"
  --train-labels "$old_root/firewall_a/labels.json"
  --cards-root "$cards_root"
  --old-selection-public "$old_root/selection_a.public.json"
  --old-selection-private "$old_root/selection_a.private.json"
  --old-fit-summary "$old_root/fit/summary.json"
  --old-private-pairs "$old_root/fit/private_pairs.json"
  --task-audit-public "$worktree/$task_audit_rel"
  --selection-public "$root/selection_a.public.json"
  --selection-private "$root/selection_a.private.json"
  --fit-summary "$root/fit/summary.json"
  --runs-csv "$root/fit/runs.csv"
  --new-private-pairs "$root/fit/private_pairs.json"
  --checkpoint-dir "$root/fit/checkpoints"
)
for replica in a b; do
  (cd "$worktree" && strace -ff -e trace=file,network -o "$root/verifier_${replica}.strace" \
    "$python_bin" -m phase1.verify_endpoint_budget_distribution_matched_yield_screen \
    "${verify_common[@]}" --output "$root/verifier_${replica}.json") >"$root/verifier_${replica}.stdout.json"
done
cmp "$root/verifier_a.json" "$root/verifier_b.json"

grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "$root"/*.strace* >"$root/network_calls.txt" || true
test ! -s "$root/network_calls.txt"
grep -hEi '(first[-_]?960|target[-_]?300|target[-_]?522|decision(_clean)?[^/]*\.jsonl|outcome[^/]*\.json|prospective[^/]*\.(json|jsonl))' \
  "$root"/*.strace* >"$root/forbidden_path_opens.txt" || true
test ! -s "$root/forbidden_path_opens.txt"
grep -hEi '(labels\.json|cards\.safe\.json|private_pairs\.json|fit/summary\.json)' "$root"/selection_*.strace* \
  >"$root/selection_boundary_violations.txt" || true
test ! -s "$root/selection_boundary_violations.txt"
grep -RIlE '(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})' \
  "$root" --exclude-dir=worktree --exclude=credential_blob_hits.txt \
  >"$root/credential_blob_hits.txt" || true
test ! -s "$root/credential_blob_hits.txt"
git -C "$worktree" diff-tree --no-commit-id --name-only -r "$analysis_commit" \
  | grep -iE '(env|key|token|secret)' >"$root/credential_filename_hits.txt" || true
test ! -s "$root/credential_filename_hits.txt"
test -z "$(git -C "$worktree" status --porcelain)"

(
  cd "$root"
  find . -path ./worktree -prune -o -type f \
    ! -name SHA256SUMS ! -name MANIFEST_SHA256 ! -name COMPLETE ! -name FAILED_RC \
    -printf '%P\0' | sort -z | xargs -0 -r sha256sum
) >"$root/SHA256SUMS"
(cd "$root" && sha256sum -c SHA256SUMS >/dev/null)
sha256sum "$root/SHA256SUMS" | awk '{print $1}' >"$root/MANIFEST_SHA256"
touch "$root/COMPLETE"
chmod -R a-w "$root"
trap - EXIT
printf 'FORMAL_COMPLETE root=%s manifest=%s\n' "$root" "$(tr -d '\r\n' <"$root/MANIFEST_SHA256")"
