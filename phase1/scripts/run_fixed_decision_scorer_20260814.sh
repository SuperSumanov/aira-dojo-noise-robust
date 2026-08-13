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
pair_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
run_map_sha=3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30
cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
manifest_sha=8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19
manifest_summary_sha=cc2a0ecc2b96ce66c4e01d7f734cb73d3363a88ce6ad5f1567937761a72272dc

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/fixed_decision_scorer_v11_20260814_${commit:0:12}
if [[ -e "$root" ]]; then
  echo "ABORT_EXISTING_APPEND_ONLY_ROOT $root" >&2
  exit 2
fi
mkdir -p "$root/prereg" "$root/audits"
exec > >(tee "$root/preflight.log") 2>&1

echo "PREFLIGHT_BEGIN $(date -Is)"
echo "PREFLIGHT_01_ARTIFACT_KNOBS"
test -z "$(git status --short)"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
cp phase1/fixed_decision_scorer.py "$root/prereg/"
cp phase1/verify_fixed_decision_scorer.py "$root/prereg/"
cp phase1/tests/test_fixed_decision_scorer.py "$root/prereg/"
cp phase1/实验记录/2026-08-14/ProspectiveDecisionConfirmation_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/ProspectiveDecisionScorer_长实验预检.md "$root/prereg/"
cp phase1/scripts/run_fixed_decision_scorer_20260814.sh "$root/prereg/"
sha256sum "$root"/prereg/* > "$root/prereg/source_files.sha256"

echo "PREFLIGHT_02_CHEAP_TESTS"
"$python" -m py_compile phase1/fixed_decision_scorer.py phase1/verify_fixed_decision_scorer.py
"$test_python" -m pytest -q \
  phase1/tests/test_fixed_decision_scorer.py \
  phase1/tests/test_heterogeneous_oof.py \
  phase1/tests/test_pairgraph_intervention.py

echo "PREFLIGHT_03_ENTRYPOINT_CONTRACT"
"$python" -m phase1.fixed_decision_scorer build --help > "$root/prereg/build_help.txt"
"$python" -m phase1.fixed_decision_scorer activate --help > "$root/prereg/activate_help.txt"
"$python" -m phase1.fixed_decision_scorer score --help > "$root/prereg/score_help.txt"
"$python" -m phase1.verify_fixed_decision_scorer --help > "$root/prereg/verifier_help.txt"
if grep -Eiq -- '--[^ ]*(frozen|test|held)' "$root/prereg/build_help.txt" "$root/prereg/verifier_help.txt"; then
  echo "ABORT_FORBIDDEN_TRAIN_ARGUMENT" >&2
  exit 3
fi
grep -q -- '--blind-manifest' "$root/prereg/score_help.txt"

echo "PREFLIGHT_04_DISTRIBUTION"
"$python" phase1/task_parent_support_audit.py \
  --train-pairs "$pairs" \
  --baseline-oof "$feature_run/rank/oof_predictions.csv" \
  --output-json "$root/audits/support.json" \
  --output-csv "$root/audits/per_task.csv"
"$python" - "$root/audits/support.json" "$run_map" <<'PY'
import json, sys
support=json.load(open(sys.argv[1], encoding='utf-8'))['global']
run_map=json.load(open(sys.argv[2], encoding='utf-8'))
expected={'pairs':4263,'runs':333,'tasks':23,'parents':2293,'endpoints':5499,'complete_parents':2259,'physical_run_fold_overlap':0}
for key,value in expected.items():
    if support[key] != value: raise SystemExit(f'support mismatch {key}: {support[key]} != {value}')
precutoff=len(set(map(str, run_map.values())))
if precutoff != 667: raise SystemExit(f'precutoff runs {precutoff} != 667')
print('SUPPORT_EXACT', expected, 'precutoff_runs', precutoff)
PY

echo "PREFLIGHT_05_BALANCE_AND_FIXED_STOP"
"$python" - "$root/audits/support.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
assert len(p['per_fold']) == 5 and all(x['runs'] >= 66 for x in p['per_fold'])
g=p['global']
print('TRAIN_BALANCE_PASS', [(x['fold'],x['runs'],x['pairs']) for x in p['per_fold']])
print('PLANNING_PAIR_PER_RUN', g['pairs']/g['runs'], 'FUTURE_FIXED_RUNS', 240, 'NO_OUTCOME_STOPPING')
PY

echo "PREFLIGHT_06_ATOMIC_ACTIVATION"
grep -q 'os.replace(temporary, path)' phase1/fixed_decision_scorer.py
grep -q 'VERIFIED_SCORER_FREEZE_COMPLETE' phase1/fixed_decision_scorer.py
grep -q 'refusing to overwrite freeze receipt' phase1/fixed_decision_scorer.py

echo "PREFLIGHT_07_LEAKAGE"
"$python" - "$feature_run/manifest/train_held_isolation.json" <<'PY'
import json, sys
p=json.load(open(sys.argv[1], encoding='utf-8'))
for key in ('run_overlap','node_overlap','raw_code_hash_overlap'):
    if p[key] != 0: raise SystemExit(f'leakage {key}={p[key]}')
print('TRAIN_HELD_THREE_LAYER_OVERLAP_ZERO')
PY
grep -q 'label_fields_retained' phase1/fixed_decision_scorer.py
grep -q 'BLIND_TOP_LEVEL_KEYS' phase1/fixed_decision_scorer.py
grep -q 'frozen_read.*False' phase1/fixed_decision_scorer.py

echo "PREFLIGHT_08_RNG_NUMERICS"
grep -q '^SEED = 887$' phase1/fixed_decision_scorer.py
grep -q 'fit_intercept=False' phase1/fixed_decision_scorer.py
grep -q 'symmetric_design' phase1/fixed_decision_scorer.py
grep -q 'allow_pickle=False' phase1/fixed_decision_scorer.py phase1/verify_fixed_decision_scorer.py

echo "PREFLIGHT_09_SECRETS"
filename_count=$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)
echo "STAGED_FILENAME_SECRET_COUNT $filename_count"
test "$filename_count" -eq 0
if grep -REIq 'sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' \
  phase1/fixed_decision_scorer.py phase1/verify_fixed_decision_scorer.py \
  phase1/tests/test_fixed_decision_scorer.py \
  phase1/实验记录/2026-08-14/ProspectiveDecisionConfirmation_预注册.md \
  phase1/实验记录/2026-08-14/ProspectiveDecisionScorer_长实验预检.md; then
  echo "ABORT_SECRET_PATTERN" >&2
  exit 9
fi
echo "HIGH_CONFIDENCE_SECRET_COUNT 0"

echo "PREFLIGHT_10_WALL_CLOCK_SMOKE"
"$test_python" -m pytest -q \
  phase1/tests/test_fixed_decision_scorer.py::test_bundle_roundtrip_matches_fitted_endpoint_scores \
  phase1/tests/test_fixed_decision_scorer.py::test_blind_manifest_accepts_only_strict_future_code_schema

echo "PREFLIGHT_11_POWER_AND_SCOPE"
printf '%s\n' \
  'SCORER_FREEZE_HAS_NO_SCIENTIFIC_OUTCOME' \
  'PROSPECTIVE_CONFIRMATION_FIRST_240_RUNS' \
  'MINIMUM_15_TASKS_150_FINITE_RUNS_1500_PAIRS_DOMINANT_TASK_LE_025' \
  'ZERO_GPU_ZERO_API_ZERO_LLM_UPDATE'

echo "PREFLIGHT_12_TRUE_RC"
printf '%s\n' 'producer_rc verifier_rc activate_rc captured immediately after each command' > "$root/prereg/rc_contract.txt"

echo "PREFLIGHT_13_APPEND_ONLY_HASHES"
test "$(sha256sum "$pairs" | awk '{print $1}')" = "$pair_sha"
test "$(sha256sum "$run_map" | awk '{print $1}')" = "$run_map_sha"
test "$(sha256sum "$cards" | awk '{print $1}')" = "$cards_sha"
test "$(sha256sum "$manifest" | awk '{print $1}')" = "$manifest_sha"
test "$(sha256sum "$manifest_summary" | awk '{print $1}')" = "$manifest_summary_sha"
printf '%s  %s\n' "$pair_sha" "$pairs" > "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$run_map_sha" "$run_map" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$cards_sha" "$cards" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$manifest_sha" "$manifest" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$manifest_summary_sha" "$manifest_summary" >> "$root/prereg/input_files.sha256"
echo "PREFLIGHT_ALL_13_PASS $(date -Is)"

set +e
timeout --signal=TERM 3600 "$python" -m phase1.fixed_decision_scorer build \
  --repo-root "$repo" \
  --pairs "$pairs" \
  --run-map "$run_map" \
  --cards "$cards" \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --out-dir "$root/result" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-cards-sha256 "$cards_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-manifest-summary-sha256 "$manifest_summary_sha" \
  --wall-cap-s 3600
producer_rc=$?
set -e
echo "PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then exit "$producer_rc"; fi

set +e
timeout --signal=TERM 3600 "$python" -m phase1.verify_fixed_decision_scorer \
  --pairs "$pairs" \
  --run-map "$run_map" \
  --cards "$cards" \
  --manifest "$manifest" \
  --manifest-summary "$manifest_summary" \
  --result-dir "$root/result" \
  --output "$root/result/independent_verify.json" \
  --expect-pairs-sha256 "$pair_sha" \
  --expect-run-map-sha256 "$run_map_sha" \
  --expect-cards-sha256 "$cards_sha" \
  --expect-manifest-sha256 "$manifest_sha" \
  --expect-manifest-summary-sha256 "$manifest_summary_sha"
verifier_rc=$?
set -e
echo "VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then exit "$verifier_rc"; fi

set +e
"$python" -m phase1.fixed_decision_scorer activate \
  --repo-root "$repo" \
  --result-dir "$root/result"
activate_rc=$?
set -e
echo "ACTIVATE_RC $activate_rc"
if [[ "$activate_rc" -ne 0 ]]; then exit "$activate_rc"; fi

find "$root" -type f ! -name 'artifact_manifest.sha256*' ! -name 'preflight.log' -print0 \
  | sort -z | xargs -0 sha256sum > "$root/artifact_manifest.sha256.tmp"
mv "$root/artifact_manifest.sha256.tmp" "$root/artifact_manifest.sha256"
echo "FIXED_DECISION_SCORER_CHAIN_COMPLETE $root $(date -Is)"
