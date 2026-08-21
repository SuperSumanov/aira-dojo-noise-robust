#!/usr/bin/env bash
# Stage-resumable execution of the frozen parent-relative transition OOF audit.

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
draft="$semantic_root/eligible_draft.jsonl"
improve="$semantic_root/eligible_improve.jsonl"

case "$repo" in
  /research/d7/spc/yzyang4/worktrees/*) ;;
  *) echo "repo is outside the expected clean-worktree root" >&2; exit 3 ;;
esac
case "$output_root" in
  /research/d7/spc/yzyang4/critic-transition-static-oof/*) ;;
  *) echo "output is outside the dedicated result root" >&2; exit 3 ;;
esac
[[ -x "$python_bin" ]] || { echo "CPU environment is missing" >&2; exit 4; }
[[ "$(git -C "$repo" rev-parse HEAD)" == "$expected_commit" ]] || {
  echo "clean-worktree commit mismatch" >&2
  exit 5
}
[[ -z "$(git -C "$repo" status --porcelain --untracked-files=all)" ]] || {
  echo "clean-worktree is dirty" >&2
  exit 5
}
cd "$repo"
for input in "$cards" "$train" "$dev" "$draft" "$improve"; do
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

mkdir -p "$(dirname "$output_root")"
mkdir -p "$output_root"
[[ ! -f "$output_root/output_manifest.sha256" ]] || {
  echo "sealed output cannot be resumed" >&2
  exit 7
}

identity_expected="$output_root/.run_identity.expected.$$"
{
  echo "protocol=critic-parent-relative-transition-component-oof-execution-v1"
  echo "commit=$expected_commit"
  echo "cards=$cards"
  echo "train=$train"
  echo "dev=$dev"
  echo "draft=$draft"
  echo "improve=$improve"
} > "$identity_expected"
if [[ -f "$output_root/run_identity.txt" ]]; then
  cmp "$identity_expected" "$output_root/run_identity.txt"
  rm "$identity_expected"
else
  mv "$identity_expected" "$output_root/run_identity.txt"
fi

{
  echo "matrix=producer_1,producer_2,independent_full_refit_verifier_1,independent_full_refit_verifier_2"
  echo "arms=child_code,transition_only,child_plus_transition"
  echo "producer_gbm_fits_each=15"
  echo "verifier_gbm_fits_each=15"
  echo "total_gbm_fits=60"
  echo "folds=5"
  echo "fold_seed=20260823"
  echo "task_bootstrap_seed=20260825"
  echo "parent_bootstrap_seed=20260826"
  echo "bootstrap_replicates=20000"
  echo "cpu_threads_each=1"
  echo "gpu_runs=0"
  echo "gpu_hours=0"
  echo "api_calls=0"
  echo "base_llm_updates=0"
  echo "heldout_test_arguments=0"
  echo "tfidf_arguments=0"
  echo "prospective_arguments=0"
  echo "resume_unit=completed_producer_or_verifier_replicate"
} > "$output_root/preflight_matrix.txt"

{
  "$python_bin" --version
  "$python_bin" -c 'import numpy, scipy, sklearn; print("numpy=" + numpy.__version__); print("scipy=" + scipy.__version__); print("sklearn=" + sklearn.__version__)'
  uname -a
  lscpu | grep -E '^(Architecture|CPU\(s\)|Model name|Thread|Core|Socket)'
  git -C "$repo" rev-parse HEAD
  git -C "$repo" status --porcelain --untracked-files=all
} > "$output_root/software_cpu_receipt.txt" 2>&1
sha256sum "$cards" "$train" "$dev" "$draft" "$improve" > "$output_root/input_sha256.txt"

filename_hits="$(git -C "$repo" show --format= --name-only "$expected_commit" \
  | grep -icE 'env|key|token|secret' || true)"
content_hits="$(git -C "$repo" show --format= "$expected_commit" -- \
  phase1/critic_transition_static_component_oof.py \
  phase1/verify_critic_transition_static_component_oof.py \
  phase1/tests/test_critic_transition_static_component_oof.py \
  phase1/scripts/run_critic_transition_static_component_oof_20260821.sh \
  | grep -icE '(sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' || true)"
{
  echo "commit_filename_credential_shape_hits=$filename_hits"
  echo "commit_content_credential_shape_hits=$content_hits"
} > "$output_root/security_precheck.txt"
[[ "$filename_hits" == 0 && "$content_hits" == 0 ]] || {
  echo "credential-shape precheck failed" >&2
  exit 8
}

if [[ ! -s "$output_root/focused_tests.txt" ]]; then
  /usr/bin/time -v -o "$output_root/focused_tests.time.txt" \
    "$python_bin" -m pytest -q \
      "$repo/phase1/tests/test_critic_transition_static_component_oof.py" \
      "$repo/phase1/tests/test_critic_static_source_component_oof.py" \
    > "$output_root/focused_tests.txt" 2>&1
fi

producer=(
  "$python_bin" -m phase1.critic_transition_static_component_oof
  "$cards" "$train" "$dev" "$draft" "$improve"
)
verifier=(
  "$python_bin" -m phase1.verify_critic_transition_static_component_oof
  "$cards" "$train" "$dev" "$draft" "$improve"
)
printf '%q ' "${producer[@]}" > "$output_root/producer_command.txt"
printf 'OUTPUT_DIRECTORY\n' >> "$output_root/producer_command.txt"
printf '%q ' "${verifier[@]}" > "$output_root/verifier_command.txt"
printf 'PRODUCER_ARTIFACT_DIRECTORY\n' >> "$output_root/verifier_command.txt"

artifact_valid() {
  "$python_bin" - "$1" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest_path = root / "artifact_manifest.json"
if not manifest_path.is_file():
    raise SystemExit(1)
manifest = json.loads(manifest_path.read_text())
expected = {}
for name in ("summary.json", "per_pair.jsonl"):
    path = root / name
    if not path.is_file():
        raise SystemExit(1)
    expected[name] = hashlib.sha256(path.read_bytes()).hexdigest()
if manifest != expected:
    raise SystemExit(1)
PY
}

next_attempt() {
  local prefix="$1"
  local count
  count="$(find "$output_root" -maxdepth 1 -type f -name "${prefix}.attempt_*.time.txt" | wc -l)"
  echo $((count + 1))
}

run_producer() {
  local name="$1"
  local artifact="$output_root/$name"
  if [[ -d "$artifact" ]] && ! artifact_valid "$artifact"; then
    local quarantine="$output_root/${name}.incomplete.$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$artifact" "$quarantine"
    echo "$quarantine" >> "$output_root/incomplete_artifacts_preserved.txt"
  fi
  if [[ ! -d "$artifact" ]]; then
    local attempt
    attempt="$(next_attempt "$name")"
    /usr/bin/time -v -o "$output_root/${name}.attempt_${attempt}.time.txt" \
      "${producer[@]}" "$artifact" \
      > "$output_root/${name}.attempt_${attempt}.stdout.json" \
      2> "$output_root/${name}.attempt_${attempt}.stderr.txt"
    echo "$attempt" > "$output_root/${name}.success_attempt.txt"
    cp "$output_root/${name}.attempt_${attempt}.stdout.json" "$output_root/${name}.stdout.json"
    cp "$output_root/${name}.attempt_${attempt}.time.txt" "$output_root/${name}.time.txt"
    cp "$output_root/${name}.attempt_${attempt}.stderr.txt" "$output_root/${name}.stderr.txt"
  fi
  artifact_valid "$artifact"
  if [[ ! -s "$output_root/${name}.stdout.json" ]]; then
    cp "$artifact/summary.json" "$output_root/${name}.stdout.json"
    echo "canonical stdout recovered from sealed producer summary" \
      > "$output_root/${name}.recovery_receipt.txt"
  fi
}

run_verifier() {
  local name="$1"
  local final="$output_root/${name}.json"
  if [[ -s "$final" ]] && ! "$python_bin" -c 'import json,sys; json.load(open(sys.argv[1]))' "$final"; then
    local quarantine="$output_root/${name}.invalid.$(date -u +%Y%m%dT%H%M%SZ).json"
    mv "$final" "$quarantine"
    echo "$quarantine" >> "$output_root/incomplete_artifacts_preserved.txt"
  fi
  if [[ ! -s "$final" ]]; then
    local attempt
    attempt="$(next_attempt "$name")"
    local temporary="$output_root/${name}.attempt_${attempt}.json"
    /usr/bin/time -v -o "$output_root/${name}.attempt_${attempt}.time.txt" \
      "${verifier[@]}" "$output_root/producer_1" \
      > "$temporary" 2> "$output_root/${name}.attempt_${attempt}.stderr.txt"
    "$python_bin" -c 'import json,sys; json.load(open(sys.argv[1]))' "$temporary"
    cp "$temporary" "$final"
    cp "$output_root/${name}.attempt_${attempt}.time.txt" "$output_root/${name}.time.txt"
    cp "$output_root/${name}.attempt_${attempt}.stderr.txt" "$output_root/${name}.stderr.txt"
    echo "$attempt" > "$output_root/${name}.success_attempt.txt"
  fi
  "$python_bin" -c 'import json,sys; json.load(open(sys.argv[1]))' "$final"
}

run_producer producer_1
run_producer producer_2
diff -r "$output_root/producer_1" "$output_root/producer_2" \
  > "$output_root/producer_reproducibility.diff"
diff "$output_root/producer_1.stdout.json" "$output_root/producer_2.stdout.json" \
  > "$output_root/producer_stdout_reproducibility.diff"

run_verifier verifier_1
run_verifier verifier_2
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
    "protocol": "critic-parent-relative-transition-final-combined-v1",
    "producer_status": summary["status"],
    "independent_verification_status": verification["status"],
    "producer_valid": summary["producer_valid"],
    "positive_claim_allowed": verification["positive_claim_allowed"],
    "controls": verification["verified_controls"],
    "effect_gates": verification["verified_effect_gates"],
}
(root / "combined_conclusion.json").write_text(
    json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
)
PY

if [[ ! -s "$output_root/full_phase_tests.txt" ]]; then
  /usr/bin/time -v -o "$output_root/full_phase_tests.time.txt" \
    "$python_bin" -m pytest -q "$repo/phase1/tests" \
    > "$output_root/full_phase_tests.txt" 2>&1
fi

output_content_hits="$(
  { grep -RIlE \
    '(sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[^[:space:]]+|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,})' \
    "$output_root" || true; } | wc -l
)"
echo "output_content_credential_shape_files=$output_content_hits" \
  > "$output_root/security_postcheck.txt"
[[ "$output_content_hits" == 0 ]] || { echo "credential-shape postcheck failed" >&2; exit 9; }

find "$output_root" -type f ! -name output_manifest.sha256 -print0 \
  | sort -z | xargs -0 sha256sum > "$output_root/output_manifest.sha256"
chmod -R a-w "$output_root"
echo "TRANSITION_STATIC_OOF_DONE $output_root"
