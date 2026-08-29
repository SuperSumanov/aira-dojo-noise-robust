#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export PYTHONHASHSEED=0
unset OPENAI_API_KEY DEEPSEEK_API_KEY DASHSCOPE_API_KEY OPENROUTER_API_KEY ANTHROPIC_API_KEY || true

analysis_commit=${1:?analysis commit required}
case "$analysis_commit" in
  *[!0-9a-f]*|'') printf 'invalid analysis commit\n' >&2; exit 64 ;;
esac
test "${#analysis_commit}" = 40

repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
input_root=/research/d7/spc/yzyang4/endpoint-label-efficiency-smoke/formal-9f9705a-r1
root=/research/d7/spc/yzyang4/endpoint-task-heterogeneity-audit/formal-${analysis_commit:0:7}-r1
worktree=${root}/worktree
protocol_rel=phase1/endpoint_budget_task_heterogeneity_audit_v1.json
protocol_sha=f3aea61901210b17acf2632c0c5a91541dae0fb2b9435ea231d0822657e0a99e

test ! -e "$root"
mkdir -p "$root"
chmod 700 "$root"
failure_receipt() {
  rc=$?
  if test "$rc" != 0 && test ! -e "$root/COMPLETE"; then
    printf '%s\n' "$rc" >"$root/FAILED_RC"
  fi
  exit "$rc"
}
trap failure_receipt EXIT

git -C "$repo" fetch fork phase1-value-critic
test "$(git -C "$repo" rev-parse FETCH_HEAD^{commit})" = "$analysis_commit"
git -C "$repo" worktree add --detach "$worktree" "$analysis_commit" >/dev/null
test "$(git -C "$worktree" rev-parse HEAD)" = "$analysis_commit"
test -z "$(git -C "$worktree" status --porcelain)"
test "$(sha256sum "$worktree/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"

cat >"$root/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_goal=map the already disclosed single-fold endpoint-acquisition gain heterogeneity without tuning or rescuing the failed smoke; PASS
03_context=overall two-budget deltas and terminal dominant-task reversal are disclosed in the frozen protocol while task signs coverage correlations LOTO and concentration were unseen; PASS
04_population=the exact bound senior-0819 train-only firewall topology and completed private pair witness only; senior test and all prospective cohorts forbidden; PASS
05_split=the original salted physical-run fold0 evaluation and folds1-4 training are reconstructed with 401/138 rows and no new split choice; PASS
06_estimand=task-level net-correct and proper-score deltas versus endpoint run and induced-pair coverage deltas at frozen budgets 96 and 192; exploratory mechanism audit only; PASS
07_controls=same four fitted models and same evaluation pairs are reused; no refit task removal reweighting threshold seed or budget selection; PASS
08_thresholds=no efficacy promotion threshold and no rescue gate; all zero negative and positive tasks retained; PASS
09_randomness=none; deterministic binary64 ranks correlations concentration and leave-one-task-out summaries; PASS
10_resources=CPU single-thread under five minutes expected; GPU paid-API critic-fit base-update 0/0/0/0; PASS
11_outputs=public aggregate without raw or hashed identities plus mode0600 private task rows; producer A/B and independent verifier A/B; PASS
12_security=all six input SHA bindings and private modes checked; credential environment unset; strace network and forbidden prospective/raw-label paths must be empty; PASS
13_stop=any hash mode schema identity leakage A/B verifier scanner or manifest failure exits before COMPLETE and cannot alter the failed smoke classification; PASS
EOF
test "$(wc -l <"$root/preflight_13.txt")" = 13

test -f "$input_root/COMPLETE"
test ! -e "$input_root/FAILED_RC"
test "$(tr -d '\r\n' <"$input_root/MANIFEST_SHA256")" = 4995bdf6e936b2e7f62fb9f44174e69cc3752b203a950816b17d2dd01f4c6e38
(
  cd "$input_root"
  sha256sum -c SHA256SUMS >/dev/null
)
test "$(sha256sum "$input_root/firewall_a/receipt.json" | awk '{print $1}')" = 9291d9e715ccff4ecdfac39cd462379be2d6ecacedb9e6d38a1762c0e9d64ab3
test "$(sha256sum "$input_root/firewall_a/topology.json" | awk '{print $1}')" = 832d892a69046a8cef72263fac2ea63ce2a79be8a132f761112a625328273c70
test "$(sha256sum "$input_root/selection_a.public.json" | awk '{print $1}')" = d1e4274b1046c4e4fea294818beb5522fcdd352a9379a2d72e8bc3255b59bd15
test "$(sha256sum "$input_root/selection_a.private.json" | awk '{print $1}')" = ab4c76721964b3a7c8554e551c5bc524043f111eb52c7a3eddec952553bb1445
test "$(sha256sum "$input_root/fit/summary.json" | awk '{print $1}')" = b8068e691c84c1413d1e21091bde4ef89914dc3a0777ff44ba92bfe57f1ed6ec
test "$(sha256sum "$input_root/fit/private_pairs.json" | awk '{print $1}')" = 1f9bcb84fe6652c8801ce3872f2c9bdc830c8d2dcaa8347eaaa9bb567f1300ce
for path in "$input_root/firewall_a/topology.json" "$input_root/selection_a.private.json" "$input_root/fit/private_pairs.json"; do
  test "$(stat -c '%a' "$path")" = 600
done

(cd "$worktree" && "$python_bin" -m pytest -q phase1/tests/test_endpoint_budget_task_heterogeneity_audit.py) >"$root/focused_tests.txt"
(cd "$worktree" && "$python_bin" -m pytest -q phase1) >"$root/full_tests.txt"

common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --analysis-source-commit "$analysis_commit"
  --firewall-receipt "$input_root/firewall_a/receipt.json"
  --train-topology "$input_root/firewall_a/topology.json"
  --selection-public "$input_root/selection_a.public.json"
  --selection-private "$input_root/selection_a.private.json"
  --fit-summary "$input_root/fit/summary.json"
  --private-pairs "$input_root/fit/private_pairs.json"
)
for replica in a b; do
  (cd "$worktree" && strace -ff -e trace=file,network -o "$root/producer_${replica}.strace" \
    "$python_bin" -m phase1.audit_endpoint_budget_task_heterogeneity \
    "${common[@]}" \
    --public-output "$root/public_${replica}.json" \
    --private-output "$root/private_${replica}.json") >"$root/producer_${replica}.stdout.json"
done
cmp "$root/public_a.json" "$root/public_b.json"
cmp "$root/private_a.json" "$root/private_b.json"
test "$(stat -c '%a' "$root/private_a.json")" = 600
test "$(stat -c '%a' "$root/private_b.json")" = 600

verify_common=(
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --firewall-receipt "$input_root/firewall_a/receipt.json"
  --train-topology "$input_root/firewall_a/topology.json"
  --selection-public "$input_root/selection_a.public.json"
  --selection-private "$input_root/selection_a.private.json"
  --fit-summary "$input_root/fit/summary.json"
  --private-pairs "$input_root/fit/private_pairs.json"
  --public-result "$root/public_a.json"
  --private-result "$root/private_a.json"
)
for replica in a b; do
  (cd "$worktree" && strace -ff -e trace=file,network -o "$root/verifier_${replica}.strace" \
    "$python_bin" -m phase1.verify_endpoint_budget_task_heterogeneity \
    "${verify_common[@]}" --output "$root/verifier_${replica}.json") >"$root/verifier_${replica}.stdout.json"
done
cmp "$root/verifier_a.json" "$root/verifier_b.json"

grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "$root"/*.strace* >"$root/network_calls.txt" || true
test ! -s "$root/network_calls.txt"
grep -hEi '(first[-_]?960|target[-_]?300|target[-_]?522|decision(_clean)?[^/]*\.jsonl|labels\.json|outcome[^/]*\.json|cards[^/]*\.jsonl)' \
  "$root"/*.strace* >"$root/forbidden_path_opens.txt" || true
test ! -s "$root/forbidden_path_opens.txt"
grep -RIlE '(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})' \
  "$root/public_a.json" "$root/verifier_a.json" "$root/preflight_13.txt" >"$root/credential_blob_hits.txt" || true
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
