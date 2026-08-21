#!/usr/bin/env bash
# Execute the preregistered CPU-only static suite twice and verify it twice.

set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
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
semantic_root=/research/d7/spc/yzyang4/decision-semantic-exact-config-support/21a4d4e-baf6bdd-v2/producer_1
train="$component_root/train.jsonl"
dev="$component_root/dev.jsonl"
test="$component_root/heldout_test.jsonl"
draft="$semantic_root/eligible_draft.jsonl"
improve="$semantic_root/eligible_improve.jsonl"
tfidf="$repo/phase1/results/critic_component_tfidf_20260821_a6075d1/per_pair.jsonl"

case "$repo" in
  /research/d7/spc/yzyang4/worktrees/*) ;;
  *) echo "repo is outside the expected clean-worktree root" >&2; exit 3 ;;
esac
case "$output_root" in
  /research/d7/spc/yzyang4/critic-component-static-suite/*) ;;
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
for input in "$cards" "$train" "$dev" "$test" "$draft" "$improve" "$tfidf"; do
  [[ -f "$input" ]] || { echo "missing input: $input" >&2; exit 6; }
done

export PYTHONPATH="$repo"
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

mkdir -p "$output_root"

{
  echo "protocol=critic-component-static-suite-execution-v1"
  echo "commit=$expected_commit"
  echo "matrix=producer_1,producer_2,verifier_1,verifier_2"
  echo "total_computations=4"
  echo "cpu_threads_each=1"
  echo "gpu_runs=0"
  echo "gpu_hours=0"
  echo "api_calls=0"
  echo "warmup=focused_tests"
  echo "measurement=producer_and_verifier_wall_clock_separately"
  echo "task_bootstrap_seed=20260821"
  echo "parent_bootstrap_seed=20260822"
  echo "bootstrap_replicates=20000"
  echo "test_is_prediction_only=true"
  echo "test_used_for_selection=false"
} > "$output_root/preflight_matrix.txt"

{
  "$python_bin" --version
  "$python_bin" -c 'import numpy, scipy, sklearn; print("numpy=" + numpy.__version__); print("scipy=" + scipy.__version__); print("sklearn=" + sklearn.__version__)'
  uname -a
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread|Core|Socket)'
  git -C "$repo" status --porcelain --untracked-files=all
} > "$output_root/environment.txt" 2>&1

sha256sum "$cards" "$train" "$dev" "$test" "$draft" "$improve" "$tfidf" \
  > "$output_root/input_sha256.txt"

filename_hits="$(git -C "$repo" show --format= --name-only "$expected_commit" \
  | grep -icE 'env|key|token|secret' || true)"
content_hits="$(git -C "$repo" show --format= "$expected_commit" -- \
  phase1/critic_component_static_suite.py \
  phase1/verify_critic_component_static_suite.py \
  phase1/tests/test_critic_component_static_suite.py \
  phase1/scripts/run_critic_component_static_suite_20260821.sh \
  | grep -icE '(sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' || true)"
{
  echo "commit_filename_credential_shape_hits=$filename_hits"
  echo "commit_content_credential_shape_hits=$content_hits"
} > "$output_root/security_precheck.txt"
[[ "$filename_hits" == 0 && "$content_hits" == 0 ]] || {
  echo "credential-shape precheck failed" >&2
  exit 7
}

/usr/bin/time -v -o "$output_root/focused_tests.time.txt" \
  "$python_bin" -m pytest -q \
  "$repo/phase1/tests/test_critic_component_static_suite.py" \
  "$repo/phase1/tests/test_critic_component_tfidf_baseline.py" \
  > "$output_root/focused_tests.txt" 2>&1

producer=(
  "$python_bin" -m phase1.critic_component_static_suite
  "$cards" "$train" "$dev" "$test" "$draft" "$improve" "$tfidf"
)
verifier=(
  "$python_bin" -m phase1.verify_critic_component_static_suite
  "$cards" "$train" "$dev" "$test" "$draft" "$improve" "$tfidf"
)

printf '%q ' "${producer[@]}" > "$output_root/producer_command.txt"
printf 'OUTPUT_DIRECTORY\n' >> "$output_root/producer_command.txt"
printf '%q ' "${verifier[@]}" > "$output_root/verifier_command.txt"
printf 'PRODUCER_ARTIFACT_DIRECTORY\n' >> "$output_root/verifier_command.txt"

for replicate in 1 2; do
  /usr/bin/time -v -o "$output_root/producer_${replicate}.time.txt" \
    "${producer[@]}" "$output_root/producer_${replicate}" \
    > "$output_root/producer_${replicate}.stdout.json" 2> "$output_root/producer_${replicate}.stderr.txt"
done

diff -r "$output_root/producer_1" "$output_root/producer_2" \
  > "$output_root/producer_reproducibility.diff"

for replicate in 1 2; do
  /usr/bin/time -v -o "$output_root/verifier_${replicate}.time.txt" \
    "${verifier[@]}" "$output_root/producer_1" \
    > "$output_root/verifier_${replicate}.json" 2> "$output_root/verifier_${replicate}.stderr.txt"
done

diff "$output_root/verifier_1.json" "$output_root/verifier_2.json" \
  > "$output_root/verifier_reproducibility.diff"
cp "$output_root/verifier_1.json" "$output_root/final_verification_receipt.json"

"$python_bin" - "$output_root" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
summary = json.loads((root / "producer_1" / "summary.json").read_text())
verification = json.loads((root / "final_verification_receipt.json").read_text())
receipt = {
    "protocol": "critic-component-static-suite-final-combined-v1",
    "producer_effect_gates_pass": summary["producer_effect_gates_pass"],
    "independent_verification_status": verification["status"],
    "strong_positive_claim_allowed": verification["strong_positive_claim_allowed"],
    "champion": summary["selection"]["champion"],
    "status": verification["status"],
}
(root / "combined_conclusion.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
)
PY

output_content_hits="$(
  { grep -RIlE \
    '(sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' \
    "$output_root" || true; } | wc -l
)"
echo "output_content_credential_shape_files=$output_content_hits" \
  > "$output_root/security_postcheck.txt"
[[ "$output_content_hits" == 0 ]] || { echo "credential-shape postcheck failed" >&2; exit 8; }

find "$output_root" -type f ! -name output_manifest.sha256 -print0 \
  | sort -z | xargs -0 sha256sum > "$output_root/output_manifest.sha256"
chmod -R a-w "$output_root"
echo "STATIC_SUITE_DONE $output_root"
