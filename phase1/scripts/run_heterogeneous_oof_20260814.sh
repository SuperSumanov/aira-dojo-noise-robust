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
cards=/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl
pairs=phase1/v11_decision/decision_train_v11_b0.jsonl
run_map=phase1/card_run_map.json
manifest="$feature_run/manifest/train_endpoints.jsonl"
manifest_summary="$feature_run/manifest/train_endpoints_summary.json"
baseline_oof="$feature_run/rank/oof_predictions.csv"
pair_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
run_map_sha=3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30
cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
manifest_sha=8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19
baseline_sha=083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/heterogeneous_oof_v11_20260814_${commit:0:12}
if [[ -e "$root" ]]; then
  echo "ABORT_EXISTING_APPEND_ONLY_ROOT $root" >&2
  exit 2
fi
mkdir -p "$root/prereg" "$root/audits" "$root/smoke"
exec > >(tee "$root/preflight.log") 2>&1

echo "PREFLIGHT_BEGIN $(date -Is)"
echo "PREFLIGHT_01_ARTIFACT_KNOBS"
test -z "$(git status --short)"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
cp phase1/heterogeneous_oof.py "$root/prereg/"
cp phase1/verify_heterogeneous_oof.py "$root/prereg/"
cp phase1/heterogeneous_engineering_smoke.py "$root/prereg/"
cp phase1/tests/test_heterogeneous_oof.py "$root/prereg/"
cp phase1/实验记录/2026-08-14/HeterogeneousRunOOF_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/HeterogeneousRunOOF_长实验预检.md "$root/prereg/"
cp phase1/scripts/run_heterogeneous_oof_20260814.sh "$root/prereg/"
sha256sum "$root"/prereg/* > "$root/prereg/source_files.sha256"

echo "PREFLIGHT_02_CHEAP_TESTS"
"$python" -m py_compile phase1/heterogeneous_oof.py phase1/verify_heterogeneous_oof.py phase1/heterogeneous_engineering_smoke.py
"$test_python" -m pytest -q phase1/tests/test_heterogeneous_oof.py
"$python" -m phase1.heterogeneous_oof --help > "$root/prereg/producer_help.txt"
"$python" -m phase1.verify_heterogeneous_oof --help > "$root/prereg/verifier_help.txt"

echo "PREFLIGHT_03_PAIR_AND_FORBIDDEN_PATH"
if grep -Eiq -- '--[^ ]*(frozen|test|held)' "$root/prereg/producer_help.txt" "$root/prereg/verifier_help.txt"; then
  echo "ABORT_FORBIDDEN_PAIR_ARGUMENT" >&2
  exit 3
fi

echo "PREFLIGHT_04_DISTRIBUTION"
"$python" phase1/task_parent_support_audit.py --train-pairs "$pairs" --baseline-oof "$baseline_oof" --output-json "$root/audits/support.json" --output-csv "$root/audits/per_task.csv"
"$python" - "$root/audits/support.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))['global']
expected={'pairs':4263,'runs':333,'tasks':23,'parents':2293,'endpoints':5499,'complete_parents':2259,'physical_run_fold_overlap':0}
for key,value in expected.items():
    if p[key] != value: raise SystemExit(f'support mismatch {key}: {p[key]} != {value}')
print('SUPPORT_EXACT', expected)
PY

echo "PREFLIGHT_05_BALANCE"
"$python" - "$root/audits/support.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert len(p['per_fold'])==5 and all(x['runs']>=66 for x in p['per_fold'])
print('BALANCE_PASS', [(x['fold'],x['runs'],x['pairs']) for x in p['per_fold']])
PY

echo "PREFLIGHT_06_CHECKPOINT_RESUME"
grep -q 'checkpoint_key' phase1/heterogeneous_oof.py
grep -q 'valid_scores_sha256' phase1/heterogeneous_oof.py
grep -q 'os.replace(temporary, final_dir)' phase1/heterogeneous_oof.py
grep -q 'refit score mismatch' phase1/verify_heterogeneous_oof.py

echo "PREFLIGHT_07_LEAKAGE"
"$python" - "$feature_run/manifest/train_held_isolation.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
for key in ('run_overlap','node_overlap','raw_code_hash_overlap'):
    if p[key] != 0: raise SystemExit(f'leakage {key}={p[key]}')
print('TRAIN_HELD_THREE_LAYER_OVERLAP_ZERO')
PY
grep -q 'label_fields_retained' phase1/heterogeneous_oof.py
grep -q 'post_execution_fields_retained' phase1/heterogeneous_oof.py

echo "PREFLIGHT_08_RNG_NUMERICS"
grep -q '^SEED = 887$' phase1/heterogeneous_oof.py
grep -q 'fit_intercept=False' phase1/heterogeneous_oof.py
grep -q 'symmetric_design' phase1/heterogeneous_oof.py

echo "PREFLIGHT_09_SECRETS"
filename_count=$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)
echo "STAGED_FILENAME_SECRET_COUNT $filename_count"
test "$filename_count" -eq 0
if grep -REIq 'sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' \
  phase1/heterogeneous_oof.py phase1/verify_heterogeneous_oof.py phase1/heterogeneous_engineering_smoke.py \
  phase1/tests/test_heterogeneous_oof.py phase1/实验记录/2026-08-14/HeterogeneousRunOOF_预注册.md \
  phase1/实验记录/2026-08-14/HeterogeneousRunOOF_长实验预检.md; then
  echo "ABORT_SECRET_PATTERN" >&2
  exit 9
fi
echo "HIGH_CONFIDENCE_SECRET_COUNT 0"

echo "PREFLIGHT_10_WALL_CLOCK_SMOKE"
set +e
timeout --signal=TERM 900 "$python" -m phase1.heterogeneous_engineering_smoke \
  --pairs "$pairs" --run-map "$run_map" --cards "$cards" --manifest "$manifest" \
  --manifest-summary "$manifest_summary" --baseline-oof "$baseline_oof" \
  --output "$root/smoke/engineering_smoke.json" \
  --expect-pairs-sha256 "$pair_sha" --expect-run-map-sha256 "$run_map_sha" \
  --expect-cards-sha256 "$cards_sha" --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha" --formal-chain-budget-s 3600
smoke_rc=$?
set -e
echo "SMOKE_RC $smoke_rc"
test "$smoke_rc" -eq 0

echo "PREFLIGHT_11_TRAINING_POWER"
"$python" - "$root/smoke/engineering_smoke.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert p['status']=='ENGINEERING_SMOKE_PASS' and p['accuracy_computed'] is False and p['metrics_computed']==[]
assert p['pairs']==4263 and p['runs']==333 and p['parents']==2293 and p['endpoints']==5499
print('POWER_AND_ENGINEERING_SMOKE_PASS', p['conservative_chain_extrapolation_s'], p['max_rss_kib'])
PY

echo "PREFLIGHT_12_TRUE_RC"
printf '%s\n' 'producer_rc and verifier_rc captured immediately before any later command' > "$root/prereg/rc_contract.txt"

echo "PREFLIGHT_13_APPEND_ONLY_HASHES"
test "$(sha256sum "$pairs" | awk '{print $1}')" = "$pair_sha"
test "$(sha256sum "$run_map" | awk '{print $1}')" = "$run_map_sha"
test "$(sha256sum "$cards" | awk '{print $1}')" = "$cards_sha"
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$manifest_sha"
test "$(sha256sum "$baseline_oof" | awk '{print $1}')" = "$baseline_sha"
printf '%s  %s\n' "$pair_sha" "$pairs" > "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$run_map_sha" "$run_map" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$cards_sha" "$cards" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$manifest_sha" "$manifest" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$baseline_sha" "$baseline_oof" >> "$root/prereg/input_files.sha256"
echo "PREFLIGHT_ALL_13_PASS $(date -Is)"

set +e
timeout --signal=TERM 3600 "$python" -m phase1.heterogeneous_oof \
  --repo-root "$repo" --pairs "$pairs" --run-map "$run_map" --cards "$cards" \
  --manifest "$manifest" --manifest-summary "$manifest_summary" --baseline-oof "$baseline_oof" \
  --out-dir "$root/result" --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-manifest-sha256 "$manifest_sha" --expect-baseline-sha256 "$baseline_sha" --wall-cap-s 3600
producer_rc=$?
set -e
echo "PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then exit "$producer_rc"; fi

set +e
timeout --signal=TERM 3600 "$python" -m phase1.verify_heterogeneous_oof \
  --pairs "$pairs" --run-map "$run_map" --cards "$cards" --manifest "$manifest" \
  --manifest-summary "$manifest_summary" --baseline-oof "$baseline_oof" \
  --result-dir "$root/result" --output "$root/result/independent_verify.json" \
  --expect-pairs-sha256 "$pair_sha" --expect-run-map-sha256 "$run_map_sha" \
  --expect-cards-sha256 "$cards_sha" --expect-manifest-sha256 "$manifest_sha" \
  --expect-baseline-sha256 "$baseline_sha"
verifier_rc=$?
set -e
echo "VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then exit "$verifier_rc"; fi

find "$root" -type f ! -name 'artifact_manifest.sha256*' ! -name 'preflight.log' -print0 \
  | sort -z | xargs -0 sha256sum > "$root/artifact_manifest.sha256.tmp"
mv "$root/artifact_manifest.sha256.tmp" "$root/artifact_manifest.sha256"
echo "HETEROGENEOUS_OOF_CHAIN_COMPLETE $root $(date -Is)"
