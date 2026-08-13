#!/usr/bin/env bash
set -eo pipefail

source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
repo=$(cd "$script_dir/../.." && pwd -P)
python=/research/d7/spc/yzyang4/venvs/critic/bin/python
test_python=/research/d7/spc/yzyang4/venvs/exp/bin/python
feature_run=/research/d7/spc/yzyang4/experiments/frozen_embed_v11_20260814_f339eb971c6d
train_pairs=phase1/v11_decision/decision_train_v11_b0.jsonl
run_map=phase1/card_run_map.json
manifest="$feature_run/manifest/train_endpoints.jsonl"
manifest_summary="$feature_run/manifest/train_endpoints_summary.json"
feature_root="$feature_run/features"
baseline_oof="$feature_run/rank/oof_predictions.csv"
pair_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
run_map_sha=3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30
manifest_sha=8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19
baseline_sha=083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96
model_sha=fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe
extraction_commit=f339eb971c6d04fd149c608cc570b4bcdcdd1aac

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/task_topcenter_v11_20260814_${commit:0:12}
if [[ -e "$root" ]]; then
  echo "ABORT_EXISTING_APPEND_ONLY_ROOT $root" >&2
  exit 2
fi
mkdir -p "$root/prereg" "$root/support" "$root/smoke"
exec > >(tee "$root/preflight.log") 2>&1

echo "PREFLIGHT_BEGIN $(date -Is)"
echo "PREFLIGHT_01_ARTIFACT_KNOBS"
git status --short
test -z "$(git status --short)"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
cp phase1/task_topcenter_rank.py "$root/prereg/"
cp phase1/verify_task_topcenter_discovery.py "$root/prereg/"
cp phase1/task_topcenter_engineering_smoke.py "$root/prereg/"
cp phase1/task_parent_support_audit.py "$root/prereg/"
cp phase1/frozen_embed_rank.py "$root/prereg/"
cp phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_长实验预检.md "$root/prereg/"
cp phase1/scripts/run_task_topcenter_discovery_20260814.sh "$root/prereg/"
sha256sum "$root"/prereg/* > "$root/prereg/source_files.sha256"

echo "PREFLIGHT_02_CHEAP_TESTS"
"$python" -m py_compile \
  phase1/task_topcenter_rank.py \
  phase1/verify_task_topcenter_discovery.py \
  phase1/task_topcenter_engineering_smoke.py \
  phase1/task_parent_support_audit.py
"$test_python" -m pytest -q \
  phase1/tests/test_task_parent_support_audit.py \
  phase1/tests/test_task_topcenter_rank.py

echo "PREFLIGHT_03_PAIR_AND_FORBIDDEN_PATH"
if "$python" phase1/task_topcenter_rank.py --help | grep -Eiq -- '--[^ ]*(frozen|test|held)'; then
  echo "ABORT_FORBIDDEN_PAIR_ARGUMENT" >&2
  exit 3
fi
if "$python" phase1/verify_task_topcenter_discovery.py --help | grep -Eiq -- '--[^ ]*(frozen|test|held)'; then
  echo "ABORT_FORBIDDEN_VERIFIER_ARGUMENT" >&2
  exit 3
fi

echo "PREFLIGHT_04_DISTRIBUTION"
"$python" phase1/task_parent_support_audit.py \
  --train-pairs "$train_pairs" \
  --baseline-oof "$baseline_oof" \
  --output-json "$root/support/audit.json" \
  --output-csv "$root/support/per_task.csv"
"$python" - "$root/support/audit.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
g=p["global"]
expected={"pairs":4263,"runs":333,"tasks":23,"parents":2293,"endpoints":5499,"complete_parents":2259,"multiway_parents":773,"multiway_pairs":2743,"physical_run_fold_overlap":0}
for key,value in expected.items():
    if g[key] != value:
        raise SystemExit(f"support mismatch {key}: {g[key]} != {value}")
print("SUPPORT_EXACT", expected)
PY

echo "PREFLIGHT_05_BALANCE"
"$python" - "$root/support/audit.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
folds=p["per_fold"]
assert len(folds)==5 and all(x["runs"]>=66 for x in folds)
assert p["global"]["multiway_pair_share"] > 0.64
assert any(not x["inner_3fold_run_feasible_in_every_active_outer_fold"] for x in p["per_task"])
print("BALANCE_REQUIRES_SHARED_SHRUNK_RESIDUAL")
PY

echo "PREFLIGHT_06_CHECKPOINT_DESIGN"
grep -q 'FOLD_COMPLETE' phase1/task_topcenter_rank.py
grep -q 'os.replace(temporary, final_dir)' phase1/task_topcenter_rank.py
grep -q 'inner_oof_scores' phase1/verify_task_topcenter_discovery.py
grep -q 'checkpoint_key' phase1/verify_task_topcenter_discovery.py

echo "PREFLIGHT_07_LEAKAGE"
"$python" - "$feature_run/manifest/train_held_isolation.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding="utf-8"))
for key in ("run_overlap", "node_overlap", "raw_code_hash_overlap"):
    if p[key] != 0:
        raise SystemExit(f"leakage {key}={p[key]}")
print("TRAIN_HELD_THREE_LAYER_OVERLAP_ZERO")
PY

echo "PREFLIGHT_08_RNG_NUMERICS"
grep -q '^SEED = 887$' phase1/task_topcenter_rank.py
grep -q '^MAXITER = 300$' phase1/task_topcenter_rank.py
grep -q '"initialization": "all_zero"' phase1/task_topcenter_rank.py

echo "PREFLIGHT_09_SECRETS"
filename_count=$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)
echo "STAGED_FILENAME_SECRET_COUNT $filename_count"
test "$filename_count" -eq 0
if grep -REIq 'sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' \
  phase1/task_topcenter_rank.py \
  phase1/verify_task_topcenter_discovery.py \
  phase1/task_topcenter_engineering_smoke.py \
  phase1/task_parent_support_audit.py \
  phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_预注册.md \
  phase1/实验记录/2026-08-14/TaskTopCentered_RunOOF_长实验预检.md; then
  echo "ABORT_SECRET_PATTERN" >&2
  exit 9
fi
echo "HIGH_CONFIDENCE_SECRET_COUNT 0"

echo "PREFLIGHT_10_WALL_CLOCK_SMOKE"
set +e
timeout --signal=TERM 600 "$python" phase1/task_topcenter_engineering_smoke.py \
  --repo-root "$repo" \
  --pairs "$train_pairs" \
  --run-map "$run_map" \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --feature-root "$feature_root" \
  --output "$root/smoke/engineering_smoke.json" \
  --extraction-commit "$extraction_commit" \
  --model-sha256 "$model_sha" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --formal-runtime-budget-s 2400
smoke_rc=$?
set -e
echo "SMOKE_RC $smoke_rc"
test "$smoke_rc" -eq 0

echo "PREFLIGHT_11_TRAINING_POWER"
"$python" - "$root/support/audit.json" "$root/smoke/engineering_smoke.json" <<'PY'
import json, sys
support=json.load(open(sys.argv[1], encoding="utf-8"))["global"]
smoke=json.load(open(sys.argv[2], encoding="utf-8"))
assert support["runs"]==333 and support["complete_parents"]==2259
assert support["multiway_pairs"]==2743
assert smoke["status"]=="ENGINEERING_SMOKE_PASS" and smoke["accuracy_computed"] is False
print("POWER_AND_ENGINEERING_SMOKE_PASS", smoke["conservative_full_fit_extrapolation_s"])
PY

echo "PREFLIGHT_12_TRUE_RC"
printf '%s\n' 'producer_rc and verifier_rc are captured before any subsequent command' > "$root/prereg/rc_contract.txt"

echo "PREFLIGHT_13_APPEND_ONLY_HASHES"
test "$(sha256sum "$train_pairs" | awk '{print $1}')" = "$pair_sha"
test "$(sha256sum "$run_map" | awk '{print $1}')" = "$run_map_sha"
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$manifest_sha"
test "$(sha256sum "$baseline_oof" | awk '{print $1}')" = "$baseline_sha"
printf '%s  %s\n' "$pair_sha" "$train_pairs" > "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$run_map_sha" "$run_map" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$manifest_sha" "$manifest" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$baseline_sha" "$baseline_oof" >> "$root/prereg/input_files.sha256"
echo "PREFLIGHT_ALL_13_PASS $(date -Is)"

set +e
timeout --signal=TERM 2700 "$python" phase1/task_topcenter_rank.py \
  --repo-root "$repo" \
  --pairs "$train_pairs" \
  --run-map "$run_map" \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --feature-root "$feature_root" \
  --baseline-oof "$baseline_oof" \
  --out-dir "$root/rank" \
  --extraction-commit "$extraction_commit" \
  --model-sha256 "$model_sha" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha" \
  --wall-cap-s 2700
producer_rc=$?
set -e
echo "PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then
  exit "$producer_rc"
fi

set +e
"$python" phase1/verify_task_topcenter_discovery.py \
  --pairs "$train_pairs" \
  --manifest "$manifest" \
  --feature-root "$feature_root" \
  --baseline-oof "$baseline_oof" \
  --result-dir "$root/rank" \
  --output "$root/rank/independent_verify.json" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha" \
  --extraction-commit "$extraction_commit" \
  --model-sha256 "$model_sha"
verifier_rc=$?
set -e
echo "VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then
  exit "$verifier_rc"
fi

find "$root" -type f ! -name 'artifact_manifest.sha256*' -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$root/artifact_manifest.sha256.tmp"
mv "$root/artifact_manifest.sha256.tmp" "$root/artifact_manifest.sha256"
echo "TASK_TOPCENTER_CHAIN_COMPLETE $root $(date -Is)"
