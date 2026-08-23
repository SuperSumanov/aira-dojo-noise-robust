#!/usr/bin/env bash
# Run the preregistered outer-train-only component-clean data learning curve.

set -eo pipefail
source "$HOME/env_setup.sh"
set -u

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
contract="$repo/phase1/critic_component_data_learning_curve_v1.json"

case "$repo" in
  /research/d7/spc/yzyang4/worktrees/*) ;;
  *) echo "repo is outside the expected clean-worktree root" >&2; exit 3 ;;
esac
case "$output_root" in
  /research/d7/spc/yzyang4/critic-component-data-curve/*) ;;
  *) echo "output is outside the dedicated result root" >&2; exit 3 ;;
esac
[[ ! -e "$output_root" ]] || { echo "output already exists" >&2; exit 4; }
[[ -x "$python_bin" ]] || { echo "CPU environment is missing" >&2; exit 4; }
[[ "$(git -C "$repo" rev-parse HEAD)" == "$expected_commit" ]] || {
  echo "clean-worktree commit mismatch" >&2
  exit 5
}
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || {
  echo "clean-worktree is dirty" >&2
  exit 5
}
for input in "$cards" "$train" "$dev" "$contract"; do
  [[ -f "$input" ]] || { echo "missing input: $input" >&2; exit 6; }
done

export PYTHONPATH="$repo"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
mkdir -p "$output_root"
exec > >(tee "$output_root/run.log") 2>&1
cd "$repo"

cat > "$output_root/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=current clean critic scaling support; old HCE/probe/multifidelity remain closed
PREFLIGHT_02_QUESTION=does more independent pair-component-clean outer-train support improve fixed char-TFIDF on component-clean dev
PREFLIGHT_03_KNOWN=full-dev accuracy endpoint seen; intermediate fractions, proper-score curve, and contrasts unseen before contract
PREFLIGHT_04_INPUTS=cards/train/dev exact SHA and byte identities; heldout test pair path is absent from CLI and launcher
PREFLIGHT_05_LEAKAGE=train/dev pair, endpoint, physical-run, and component overlap must all be zero; test/prospective truth forbidden
PREFLIGHT_06_UNIT=pair_component_id; every task gets one deterministic coverage-floor component before global hash prefix
PREFLIGHT_07_MATRIX=fractions 0.25,0.5,0.75,1.0 x selection seeds 20260823,20260824,20260825; full subset cached once
PREFLIGHT_08_MODEL=fixed char_wb 3-5 TFIDF 30k min_df3 plus symmetric LR C0.5; no intercept in pair margin
PREFLIGHT_09_INFERENCE=task-macro log-loss primary, accuracy secondary; 20000 task bootstraps seed 20260826 plus LOTO
PREFLIGHT_10_RESOURCES=sequential single-thread CPU; producer x2 plus independent full-refit verifier x2; GPU/API/base-LLM update 0/0/0
PREFLIGHT_11_OUTPUT=summary, curve, per-task, per-pair, manifests, exact logs/times, source-refit receipts, and recursive hashes
PREFLIGHT_12_DURATION=estimated 1.5-2.5 hours; each fit is short and deterministic; a failed producer/verifier restarts from a fresh output root
PREFLIGHT_13_STOP=fail closed on identity/support/overlap/nesting/anchor/determinism/verifier/security/test failure; no threshold or fraction rescue
EOF

{
  "$python_bin" --version
  "$python_bin" -c 'import numpy, scipy, sklearn; print("numpy=" + numpy.__version__); print("scipy=" + scipy.__version__); print("sklearn=" + sklearn.__version__)'
  uname -a
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread|Core|Socket)'
  printf 'OMP_NUM_THREADS=%s\n' "$OMP_NUM_THREADS"
  printf 'OPENBLAS_NUM_THREADS=%s\n' "$OPENBLAS_NUM_THREADS"
  printf 'MKL_NUM_THREADS=%s\n' "$MKL_NUM_THREADS"
  printf 'NUMEXPR_NUM_THREADS=%s\n' "$NUMEXPR_NUM_THREADS"
} > "$output_root/environment.txt" 2>&1

sha256sum "$cards" "$train" "$dev" "$contract" > "$output_root/input_sha256.txt"
filename_hits="$(git -C "$repo" diff-tree --no-commit-id --name-only -r "$expected_commit" | grep -icE 'env|key|token|secret' || true)"
content_hits="$(git -C "$repo" show --format= "$expected_commit" -- \
  phase1/critic_component_data_learning_curve.py \
  phase1/verify_critic_component_data_learning_curve.py \
  phase1/critic_component_data_learning_curve_v1.json \
  phase1/tests/test_critic_component_data_learning_curve.py \
  phase1/scripts/run_critic_component_data_learning_curve_20260823.sh \
  | grep -icE '(sk-[A-Za-z0-9._-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' || true)"
printf 'commit_filename_credential_shape_hits=%s\n' "$filename_hits" > "$output_root/security_precheck.txt"
printf 'commit_content_credential_shape_hits=%s\n' "$content_hits" >> "$output_root/security_precheck.txt"
[[ "$filename_hits" -eq 0 && "$content_hits" -eq 0 ]] || exit 7

"$python_bin" -m py_compile \
  phase1/critic_component_data_learning_curve.py \
  phase1/verify_critic_component_data_learning_curve.py
PYTHONHASHSEED=0 /usr/bin/time -f 'focused_wall=%e max_rss_kib=%M' -o "$output_root/focused_time.txt" \
  "$python_bin" -m pytest -q phase1/tests/test_critic_component_data_learning_curve.py \
  > "$output_root/focused_tests.txt" 2>&1
PYTHONHASHSEED=0 /usr/bin/time -f 'full_wall=%e max_rss_kib=%M' -o "$output_root/full_time.txt" \
  "$python_bin" -m pytest -q phase1/tests \
  > "$output_root/full_phase1_tests.txt" 2>&1

PYTHONHASHSEED=0 /usr/bin/time -v -o "$output_root/producer_1_time.txt" \
  "$python_bin" -m phase1.critic_component_data_learning_curve \
  "$cards" "$train" "$dev" "$output_root/producer_1" --contract "$contract" \
  > "$output_root/producer_1_stdout.txt" 2> "$output_root/producer_1_stderr.txt"
PYTHONHASHSEED=271828 /usr/bin/time -v -o "$output_root/producer_2_time.txt" \
  "$python_bin" -m phase1.critic_component_data_learning_curve \
  "$cards" "$train" "$dev" "$output_root/producer_2" --contract "$contract" \
  > "$output_root/producer_2_stdout.txt" 2> "$output_root/producer_2_stderr.txt"
diff -rq "$output_root/producer_1" "$output_root/producer_2" > "$output_root/producer_reproducibility.diff"

PYTHONHASHSEED=0 /usr/bin/time -v -o "$output_root/verifier_1_time.txt" \
  "$python_bin" -m phase1.verify_critic_component_data_learning_curve \
  "$cards" "$train" "$dev" "$output_root/producer_1" "$output_root/verification_1.json" --contract "$contract" \
  > "$output_root/verifier_1_stdout.txt" 2> "$output_root/verifier_1_stderr.txt"
PYTHONHASHSEED=271828 /usr/bin/time -v -o "$output_root/verifier_2_time.txt" \
  "$python_bin" -m phase1.verify_critic_component_data_learning_curve \
  "$cards" "$train" "$dev" "$output_root/producer_2" "$output_root/verification_2.json" --contract "$contract" \
  > "$output_root/verifier_2_stdout.txt" 2> "$output_root/verifier_2_stderr.txt"
diff -u "$output_root/verification_1.json" "$output_root/verification_2.json" > "$output_root/verifier_reproducibility.diff"

cp "$output_root/producer_1/summary.json" "$output_root/decision_summary.json"
cp "$output_root/producer_1/curve.csv" "$output_root/decision_curve.csv"
post_content_hits="$( (grep -RIElo '(sk-[A-Za-z0-9._-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' "$output_root" || true) | wc -l)"
printf 'output_content_credential_shape_hits=%s\n' "$post_content_hits" > "$output_root/security_postcheck.txt"
[[ "$post_content_hits" -eq 0 ]] || exit 8
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || exit 9

(
  cd "$output_root"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
printf 'formal_status='
"$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$output_root/decision_summary.json"
printf 'producer_reproducibility_diff_bytes=%s\n' "$(stat -c %s "$output_root/producer_reproducibility.diff")"
printf 'verifier_reproducibility_diff_bytes=%s\n' "$(stat -c %s "$output_root/verifier_reproducibility.diff")"
printf 'COMPONENT_CURVE_FORMAL_COMPLETE\n'
