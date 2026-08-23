#!/usr/bin/env bash
# Exact-commit retrospective train/dev qualification for gap-aware critic training.

set -euo pipefail

if [[ "$#" -ne 3 ]]; then
  echo "usage: $0 REPO OUTPUT_ROOT EXPECTED_COMMIT" >&2
  exit 2
fi

repo="$(readlink -f "$1")"
output_root="$2"
expected_commit="$3"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
cards=/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json
component_root=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1
train="$component_root/train.jsonl"
dev="$component_root/dev.jsonl"
contract="$repo/phase1/critic_gap_aware_qualification_v1.json"

case "$repo" in
  /research/d7/spc/yzyang4/worktrees/*) ;;
  *) echo "repo is outside the expected clean-worktree root" >&2; exit 3 ;;
esac
case "$output_root" in
  /research/d7/spc/yzyang4/critic-gap-aware-qualification/*) ;;
  *) echo "output is outside the dedicated result root" >&2; exit 3 ;;
esac
[[ ! -e "$output_root" ]] || { echo "output already exists" >&2; exit 4; }
[[ -x "$python_bin" ]] || { echo "CPU environment is missing" >&2; exit 4; }
[[ "$(git -C "$repo" rev-parse HEAD)" == "$expected_commit" ]] || { echo "commit mismatch" >&2; exit 5; }
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || { echo "worktree is dirty" >&2; exit 5; }
for input in "$cards" "$train" "$dev" "$contract"; do
  [[ -f "$input" ]] || { echo "missing input: $input" >&2; exit 6; }
done

mkdir -p "$output_root"
exec > >(tee "$output_root/run.log") 2>&1
cd "$repo"

cat > "$output_root/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus plus Predictor Benchmark; this is a retrospective dev-only method qualification and does not reopen HCE, TD/RL, probe, multifidelity, or old score-channel effect lines
PREFLIGHT_02_QUESTION=does within-task raw-gap strength weighting improve released sibling decision ranking over the otherwise identical binary BT critic
PREFLIGHT_03_KNOWN=binary dev pair-micro 0.604355716878403 and task-macro pair accuracy 0.5643959081886237 were already observed; therefore no confirmation claim is allowed
PREFLIGHT_04_INPUTS=exact component-clean train/dev and exact Cards identity; outer test pair path and prospective truth path are absent from every CLI
PREFLIGHT_05_LEAKAGE=train/dev pair endpoint physical-run and comparison-component overlap must all equal zero; task scales use train rows only
PREFLIGHT_06_MATRIX=binary_bt fixed baseline; gap_weighted_bt sole candidate; gap_permuted_bt same-within-task-weight-multiset control; gap_ridge non-rescuing diagnostic; exactly four CPU fits per implementation
PREFLIGHT_07_INTERVENTION=same TFIDF features and train rows; weighted arm changes only within-task pair strength while renormalizing every task to mean weight one; hash cyclic control isolates true pair-gap alignment from generic nonuniform weighting
PREFLIGHT_08_MODEL=char_wb 3-5 TFIDF 30k min_df3; mirrored LR C0.5; ridge alpha1 lsqr; margins exclude intercept and must be antisymmetric
PREFLIGHT_09_INFERENCE=pair to released parent/group to task; 20000 paired task bootstraps seed 20260901; LOTO; versus-binary point floor 0.015 and versus-permuted point above zero; both CI LOTO and positive-task-fraction gates required
PREFLIGHT_10_RESOURCES=producer x2 plus non-importing verifier x2; single-thread CPU; GPU API base-LLM-update equals 0 0 0
PREFLIGHT_11_OUTPUT=summary arm task scale and per-pair tables; manifests; exact environment logs; byte reproducibility and independent refit receipts
PREFLIGHT_12_DURATION=estimated 20-40 minutes; any failed formal attempt is preserved and a scientific change requires a new commit and fresh output root
PREFLIGHT_13_STOP=no same-pool tuning; true-gap must beat binary and permuted control; ridge weighted utility micro or subgroup cannot rescue; pass only permits a separately named future pre-truth escrow and never GPU replay
EOF

run_env=(
  /usr/bin/env -i
  "HOME=$HOME"
  "USER=${USER:-yzyang4}"
  "PATH=/usr/local/bin:/usr/bin:/bin"
  "LANG=C.UTF-8"
  "LC_ALL=C.UTF-8"
  "PYTHONPATH=$repo"
  OMP_NUM_THREADS=1
  OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1
  NUMEXPR_NUM_THREADS=1
  VECLIB_MAXIMUM_THREADS=1
  BLIS_NUM_THREADS=1
)

{
  "${run_env[@]}" "$python_bin" --version
  "${run_env[@]}" "$python_bin" -c 'import numpy, scipy, sklearn; print("numpy=" + numpy.__version__); print("scipy=" + scipy.__version__); print("sklearn=" + sklearn.__version__)'
  uname -a
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread|Core|Socket)'
} > "$output_root/environment.txt" 2>&1

sha256sum "$cards" "$train" "$dev" "$contract" > "$output_root/input_sha256.txt"
git -C "$repo" diff-tree --root --no-commit-id --name-only -r "$expected_commit" > "$output_root/changed_files.txt"
filename_hits="$(grep -icE 'env|key|token|secret' "$output_root/changed_files.txt" || true)"
content_hits="$(git -C "$repo" show --format= "$expected_commit" -- \
  phase1/critic_gap_aware_qualification.py \
  phase1/verify_critic_gap_aware_qualification.py \
  phase1/critic_gap_aware_qualification_v1.json \
  phase1/tests/test_critic_gap_aware_qualification.py \
  phase1/tests/test_verify_critic_gap_aware_qualification.py \
  phase1/scripts/run_critic_gap_aware_qualification_20260824.sh \
  phase1/实验记录/2026-08-24/GapAwareCritic_TrainDev资格实验_结果前冻结.md \
  | grep -icE '(sk-[A-Za-z0-9._-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' || true)"
printf 'commit_filename_credential_shape_hits=%s\n' "$filename_hits" > "$output_root/security_precheck.txt"
printf 'commit_content_credential_shape_hits=%s\n' "$content_hits" >> "$output_root/security_precheck.txt"
[[ "$filename_hits" -eq 0 && "$content_hits" -eq 0 ]] || exit 7

"${run_env[@]}" "$python_bin" -m py_compile \
  phase1/critic_gap_aware_qualification.py \
  phase1/verify_critic_gap_aware_qualification.py
"${run_env[@]}" PYTHONHASHSEED=0 /usr/bin/time -f 'focused_wall=%e max_rss_kib=%M' -o "$output_root/focused_time.txt" \
  "$python_bin" -m pytest -q \
  phase1/tests/test_critic_gap_aware_qualification.py \
  phase1/tests/test_verify_critic_gap_aware_qualification.py \
  > "$output_root/focused_tests.txt" 2>&1
"${run_env[@]}" PYTHONHASHSEED=0 /usr/bin/time -f 'full_wall=%e max_rss_kib=%M' -o "$output_root/full_time.txt" \
  "$python_bin" -m pytest -q phase1/tests \
  > "$output_root/full_phase1_tests.txt" 2>&1

"${run_env[@]}" PYTHONHASHSEED=0 /usr/bin/time -v -o "$output_root/producer_1_time.txt" \
  "$python_bin" -m phase1.critic_gap_aware_qualification \
  "$cards" "$train" "$dev" "$output_root/producer_1" --contract "$contract" \
  > "$output_root/producer_1_stdout.txt" 2> "$output_root/producer_1_stderr.txt"
"${run_env[@]}" PYTHONHASHSEED=271828 /usr/bin/time -v -o "$output_root/producer_2_time.txt" \
  "$python_bin" -m phase1.critic_gap_aware_qualification \
  "$cards" "$train" "$dev" "$output_root/producer_2" --contract "$contract" \
  > "$output_root/producer_2_stdout.txt" 2> "$output_root/producer_2_stderr.txt"
diff -rq "$output_root/producer_1" "$output_root/producer_2" > "$output_root/producer_reproducibility.diff"

"${run_env[@]}" PYTHONHASHSEED=0 /usr/bin/time -v -o "$output_root/verifier_1_time.txt" \
  "$python_bin" -m phase1.verify_critic_gap_aware_qualification \
  "$cards" "$train" "$dev" "$output_root/producer_1" "$output_root/verification_1.json" --contract "$contract" \
  > "$output_root/verifier_1_stdout.txt" 2> "$output_root/verifier_1_stderr.txt"
"${run_env[@]}" PYTHONHASHSEED=271828 /usr/bin/time -v -o "$output_root/verifier_2_time.txt" \
  "$python_bin" -m phase1.verify_critic_gap_aware_qualification \
  "$cards" "$train" "$dev" "$output_root/producer_2" "$output_root/verification_2.json" --contract "$contract" \
  > "$output_root/verifier_2_stdout.txt" 2> "$output_root/verifier_2_stderr.txt"
diff -u "$output_root/verification_1.json" "$output_root/verification_2.json" > "$output_root/verifier_reproducibility.diff"

cp "$output_root/producer_1/summary.json" "$output_root/decision_summary.json"
cp "$output_root/producer_1/arm_metrics.csv" "$output_root/decision_arm_metrics.csv"
post_content_hits="$( (grep -RIElo '(sk-[A-Za-z0-9._-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' "$output_root" || true) | wc -l)"
printf 'output_content_credential_shape_hits=%s\n' "$post_content_hits" > "$output_root/security_postcheck.txt"
[[ "$post_content_hits" -eq 0 ]] || exit 8
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || exit 9

(
  cd "$output_root"
  find . -type f ! -name SHA256SUMS ! -name run.log -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
printf 'formal_status='
"${run_env[@]}" "$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$output_root/decision_summary.json"
printf 'producer_reproducibility_diff_bytes=%s\n' "$(stat -c %s "$output_root/producer_reproducibility.diff")"
printf 'verifier_reproducibility_diff_bytes=%s\n' "$(stat -c %s "$output_root/verifier_reproducibility.diff")"
printf 'CRITIC_GAP_AWARE_QUALIFICATION_COMPLETE\n'
