#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u

repo=${REPO:-/research/d7/spc/yzyang4/aira-dojo}
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
source_root=/research/d7/spc/yzyang4/external/senior_data/mle
run_manifest=${repo}/phase1/results/senior_augmented_train_dev_support_20260819/run_manifest.jsonl
pair_structure=${repo}/phase1/results/senior_augmented_train_dev_support_20260819/pair_structure.jsonl
support_summary=${repo}/phase1/results/senior_augmented_train_dev_support_20260819/summary.json
result_parent=${RESULT_PARENT:-/research/d7/spc/yzyang4/senior-true-batch-identity-support}
expected_global_inventory=3f23943b81f8d39367a4e503dfbf5de2d78b65fc36a1918499a722e689dbb5b3

export BLIS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONHASHSEED=0
umask 077

commit=$(git -C "$repo" rev-parse HEAD)
short=${commit:0:7}
output=${result_parent}/${short}-v3
[[ ! -e "$output" ]] || { echo "output exists: $output" >&2; exit 2; }
mkdir -p "$output"
cp "$repo/phase1/scripts/run_senior_augmented_batch_identity_support_20260821.sh" "$output/runner_source.sh"

{
  echo "PASS 1: CURRENT_DIRECTION 0CR and dated prereg are frozen at the exact source commit."
  echo "PASS 2: producer/verifier/tests are registered files at HEAD; all outputs are new paths."
  echo "PASS 3: three anonymous structural inputs are SHA-locked; global source metadata inventory is frozen."
  echo "PASS 4: units are physical run, true source batch/experiment, and task; no iid effect inference."
  echo "PASS 5: prior proxy mismatch is disclosed and cannot alter the exact path identity rule."
  echo "PASS 6: only run/task/role and tar header paths are used; no code, grade, gap, stdout, or runtime."
  echo "PASS 7: original test is structure-count only and never enters role allocation or model fitting."
  echo "PASS 8: tar members are never extracted/opened; env/member payload reads are zero."
  echo "PASS 9: S0 reports exact identity/support counts only; no predictor effect or significance."
  echo "PASS 10: deterministic serialization, producer x2, independent verifier x2, and SHA manifest."
  echo "PASS 11: CPU-only with two workers; GPU=0, API=0, model fit=0; expected 20-60 minutes."
  echo "PASS 12: SHA/schema/archive/path/join/pair/support mismatches fail closed."
  echo "PASS 13: one-shot S0; no source/rule/threshold edits after result."
} > "$output/preflight_matrix.txt"

printf '%s\n' "$commit" > "$output/source_commit.txt"
printf '%s\n' "$expected_global_inventory" > "$output/expected_global_source_inventory.txt"

actual_inventory=$(find "$source_root" -mindepth 2 -maxdepth 2 -type f -printf '%P|%s|%T@\n' | sort | sha256sum | awk '{print $1}')
printf 'expected=%s\nactual=%s\n' "$expected_global_inventory" "$actual_inventory" > "$output/source_inventory_precheck.txt"
[[ "$actual_inventory" == "$expected_global_inventory" ]] || { echo "source inventory drift" >&2; exit 3; }

cd "$repo"
"$python_bin" -m pytest -q phase1/tests/test_senior_augmented_batch_identity_support.py \
  > "$output/focused_tests.stdout.txt" 2> "$output/focused_tests.stderr.txt"
"$python_bin" -m pytest -q phase1/tests \
  > "$output/full_phase_tests.stdout.txt" 2> "$output/full_phase_tests.stderr.txt"

producer=(
  "$python_bin" -m phase1.audit_senior_augmented_batch_identity_support
  --run-manifest "$run_manifest"
  --pair-structure "$pair_structure"
  --support-summary "$support_summary"
  --source-root "$source_root"
  --source-commit "$commit"
  --workers 2
)
printf '%q ' "${producer[@]}" > "$output/producer_command.txt"
printf '\n' >> "$output/producer_command.txt"

/usr/bin/time -v -o "$output/producer_1.time.txt" \
  "${producer[@]}" --output "$output/producer_1" \
  > "$output/producer_1.stdout.txt" 2> "$output/producer_1.stderr.txt"
/usr/bin/time -v -o "$output/producer_2.time.txt" \
  "${producer[@]}" --output "$output/producer_2" \
  > "$output/producer_2.stdout.txt" 2> "$output/producer_2.stderr.txt"
diff -qr "$output/producer_1" "$output/producer_2" > "$output/producer_reproducibility.diff"

result_manifest_sha=$(sha256sum "$output/producer_1/sha256_manifest.json" | awk '{print $1}')
verifier=(
  "$python_bin" -m phase1.verify_senior_augmented_batch_identity_support
  --run-manifest "$run_manifest"
  --pair-structure "$pair_structure"
  --support-summary "$support_summary"
  --source-root "$source_root"
  --result-dir "$output/producer_1"
  --expect-result-manifest-sha256 "$result_manifest_sha"
  --expect-source-commit "$commit"
  --workers 2
)
printf '%q ' "${verifier[@]}" > "$output/verifier_command.txt"
printf '\n' >> "$output/verifier_command.txt"

/usr/bin/time -v -o "$output/verifier_1.time.txt" \
  "${verifier[@]}" --output "$output/verification_1.json" \
  > "$output/verifier_1.stdout.txt" 2> "$output/verifier_1.stderr.txt"
/usr/bin/time -v -o "$output/verifier_2.time.txt" \
  "${verifier[@]}" --output "$output/verification_2.json" \
  > "$output/verifier_2.stdout.txt" 2> "$output/verifier_2.stderr.txt"
diff -u "$output/verification_1.json" "$output/verification_2.json" > "$output/verifier_reproducibility.diff"

filename_hits=$(find "$output" -type f -printf '%f\n' | grep -icE '(^|[._-])(env|key|token|secret)([._-]|$)' || true)
credential_hits=$( { grep -rIEl '(sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "$output" || true; } | wc -l)
printf 'filename_hits=%s\ncredential_shape_files=%s\n' "$filename_hits" "$credential_hits" > "$output/security_postcheck.txt"
[[ "$filename_hits" == 0 && "$credential_hits" == 0 ]]

printf 'SENIOR_TRUE_BATCH_IDENTITY_SUPPORT_COMPLETE\n' > "$output/COMPLETE"
find "$output" -type f ! -name output_manifest.sha256 -print0 | sort -z | xargs -0 sha256sum > "$output/output_manifest.sha256"
chmod -R a-w "$output"
echo "COMPLETE output=$output commit=$commit"
