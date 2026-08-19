#!/usr/bin/env bash
set -euo pipefail

repo=${1:?repo worktree required}
source_commit=${2:?source commit required}
result_root=${3:?result root required}
cd "$repo"
test "$(git rev-parse HEAD)" = "$source_commit"

input=phase1/results/senior_augmented_train_dev_support_20260819
run_sha=bd707dd992a131d03dc20bdc981626826325f461e086a945b2f85fc41c2c171b
pair_sha=52ffcdc0b7cc4486b61de0c664c7c057c26171a520372ca2071d55f2fb7a127b
support_sha=7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8
test ! -e "$result_root"
tmp=$(mktemp -d /research/d7/spc/yzyang4/tmp/pair_mismatch.XXXXXX)
trap 'rm -rf -- "$tmp"' EXIT

source ~/env_setup.sh
pytest -q
for pass in one two; do
  python phase1/audit_senior_augmented_pair_mismatch.py \
    --run-manifest "$input/run_manifest.jsonl" --expect-run-manifest-sha256 "$run_sha" \
    --pair-structure "$input/pair_structure.jsonl" --expect-pair-structure-sha256 "$pair_sha" \
    --support-summary "$input/summary.json" --expect-support-summary-sha256 "$support_sha" \
    --source-commit "$source_commit" --output "$tmp/$pass" > "$tmp/$pass.stdout"
done
diff -ru "$tmp/one" "$tmp/two"
for pass in one two; do
  python phase1/verify_senior_augmented_pair_mismatch.py \
    --artifact "$tmp/one" --run-manifest "$input/run_manifest.jsonl" \
    --pair-structure "$input/pair_structure.jsonl" --support-summary "$input/summary.json" \
    --output "$tmp/verify_$pass.json"
done
cmp "$tmp/verify_one.json" "$tmp/verify_two.json"
mkdir -p "$result_root"
cp "$tmp/one/summary.json" "$tmp/one/sha256_manifest.json" "$result_root/"
cp "$tmp/verify_one.json" "$result_root/independent_verification.json"
sha256sum "$result_root"/*
echo PAIR_MISMATCH_FORMAL_RUN_COMPLETE
