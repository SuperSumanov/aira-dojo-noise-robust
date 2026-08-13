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
prior=/research/d7/spc/yzyang4/experiments/heterogeneous_oof_v11_20260814_385a5e59e401/result
oof="$prior/oof_predictions.csv"
pairs=phase1/v11_decision/decision_train_v11_b0.jsonl
cards=/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl
orientation=phase1/task_orientation.json
oof_sha=fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45
pairs_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
orientation_sha=e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/pairgraph_v11_20260814_${commit:0:12}
if [[ -e "$root" ]]; then
  echo "ABORT_EXISTING_APPEND_ONLY_ROOT $root" >&2
  exit 2
fi
mkdir -p "$root/prereg" "$root/audits" "$root/result"
exec > >(tee "$root/preflight.log") 2>&1

echo "PREFLIGHT_BEGIN $(date -Is)"
echo "PREFLIGHT_01_ARTIFACT_KNOBS"
test -z "$(git status --short)"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
cp phase1/pairgraph_intervention.py "$root/prereg/"
cp phase1/verify_pairgraph_intervention.py "$root/prereg/"
cp phase1/tests/test_pairgraph_intervention.py "$root/prereg/"
cp phase1/实验记录/2026-08-14/PairGraphIntervention_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/PairGraphIntervention_长实验预检.md "$root/prereg/"
cp phase1/scripts/run_pairgraph_intervention_20260814.sh "$root/prereg/"
sha256sum "$root"/prereg/* > "$root/prereg/source_files.sha256"

echo "PREFLIGHT_02_CHEAP_TESTS"
"$python" -m py_compile phase1/pairgraph_intervention.py phase1/verify_pairgraph_intervention.py
"$test_python" -m pytest -q phase1/tests/test_pairgraph_intervention.py phase1/tests/test_heterogeneous_oof.py
"$python" -m phase1.pairgraph_intervention --help > "$root/prereg/producer_help.txt"
"$python" -m phase1.verify_pairgraph_intervention --help > "$root/prereg/verifier_help.txt"

echo "PREFLIGHT_03_INPUT_AND_FORBIDDEN_PATH"
if grep -Eiq -- '--[^ ]*(frozen|test|held)' "$root/prereg/producer_help.txt" "$root/prereg/verifier_help.txt"; then
  echo "ABORT_FORBIDDEN_PAIR_ARGUMENT" >&2
  exit 3
fi

echo "PREFLIGHT_04_DISTRIBUTION"
"$python" - "$oof" "$pairs" "$root/audits/metadata.json" <<'PY'
import collections, csv, json, sys
oof_path, pair_path, output = sys.argv[1:]
with open(oof_path, encoding='utf-8', newline='') as handle:
    rows=list(csv.DictReader(handle))
pairs=[json.loads(line) for line in open(pair_path, encoding='utf-8') if line.strip()]
assert len(rows)==len(pairs)==4263
endpoints={}
for index,(row,pair) in enumerate(zip(rows,pairs)):
    assert int(row['row_index'])==index and pair['intask_split']=='train' and int(pair['budget'])==0
    assert row['task']==pair['task'] and row['run']==pair['run_id'] and row['parent']==pair['parent']
    assert row['better']==pair['better'] and row['worse']==pair['worse']
    for side in ('better','worse'):
        value=(row['task'],int(row['fold']),row['run'],row['parent'])
        assert endpoints.setdefault(row[side],value)==value
groups=collections.defaultdict(lambda: collections.Counter())
for task,fold,run,_ in endpoints.values(): groups[(task,fold)][run]+=1
upper=0
for runs in groups.values():
    n=sum(runs.values())
    upper += n*(n-1)//2 - sum(value*(value-1)//2 for value in runs.values())
payload={'pairs':len(rows),'runs':len({r['run'] for r in rows}),'tasks':len({r['task'] for r in rows}),
         'parents':len({r['parent'] for r in rows}),'endpoints':len(endpoints),'task_fold_cells':len(groups),
         'crossrun_pair_upper_bound':upper}
assert payload=={'pairs':4263,'runs':333,'tasks':23,'parents':2293,'endpoints':5499,
                 'task_fold_cells':96,'crossrun_pair_upper_bound':196980}
open(output,'w',encoding='utf-8').write(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print('METADATA_EXACT',payload)
PY

echo "PREFLIGHT_05_BALANCE_AND_SUPPORT"
"$python" - "$root/audits/metadata.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p['tasks']==23 and p['task_fold_cells']==96 and p['crossrun_pair_upper_bound']<250000
print('STRUCTURAL_SUPPORT_BOUND_PASS',p['crossrun_pair_upper_bound'])
PY

echo "PREFLIGHT_06_ATOMIC_SHORT_CPU"
grep -q 'os.replace(temporary, path)' phase1/pairgraph_intervention.py
grep -q 'append-only output already exists' phase1/pairgraph_intervention.py
printf '%s\n' 'short CPU census: no checkpoint; atomic outputs and append-only root' > "$root/prereg/checkpoint_contract.txt"

echo "PREFLIGHT_07_LEAKAGE"
grep -q 'non_allowlisted_cards_retained' phase1/pairgraph_intervention.py
grep -q 'frozen_read.*False' phase1/pairgraph_intervention.py
grep -q 'code_fields_retained.*0' phase1/pairgraph_intervention.py
grep -q 'observation_fields_retained.*0' phase1/pairgraph_intervention.py

echo "PREFLIGHT_08_RNG_NUMERICS"
grep -q '^BOOTSTRAP_SEED = 9_887$' phase1/pairgraph_intervention.py
grep -q '^BOOTSTRAP_REPS = 10_000$' phase1/pairgraph_intervention.py
grep -q '^EPSILON = 1e-12$' phase1/pairgraph_intervention.py

echo "PREFLIGHT_09_SECRETS"
filename_count=$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)
echo "STAGED_FILENAME_SECRET_COUNT $filename_count"
test "$filename_count" -eq 0
if grep -REIq 'sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' \
  phase1/pairgraph_intervention.py phase1/verify_pairgraph_intervention.py \
  phase1/tests/test_pairgraph_intervention.py \
  phase1/实验记录/2026-08-14/PairGraphIntervention_预注册.md \
  phase1/实验记录/2026-08-14/PairGraphIntervention_长实验预检.md; then
  echo "ABORT_SECRET_PATTERN" >&2
  exit 9
fi
echo "HIGH_CONFIDENCE_SECRET_COUNT 0"

echo "PREFLIGHT_10_WALL_CLOCK_SMOKE"
smoke_start=$(date +%s%N)
"$test_python" -m pytest -q phase1/tests/test_pairgraph_intervention.py::test_finite_population_is_crossrun_and_transport_exact
smoke_end=$(date +%s%N)
smoke_ms=$(( (smoke_end-smoke_start)/1000000 ))
echo "SYNTHETIC_TRANSPORT_SMOKE_MS $smoke_ms"
test "$smoke_ms" -lt 30000

echo "PREFLIGHT_11_STATISTICAL_SUPPORT"
echo "FINITE_POPULATION_CENSUS_TASK_BOOTSTRAP_23_TASKS_DESCRIPTIVE_ONLY"

echo "PREFLIGHT_12_TRUE_RC"
printf '%s\n' 'producer_rc and verifier_rc captured immediately before any later command' > "$root/prereg/rc_contract.txt"

echo "PREFLIGHT_13_APPEND_ONLY_HASHES"
test "$(sha256sum "$oof" | awk '{print $1}')" = "$oof_sha"
test "$(sha256sum "$pairs" | awk '{print $1}')" = "$pairs_sha"
test "$(sha256sum "$cards" | awk '{print $1}')" = "$cards_sha"
test "$(sha256sum "$orientation" | awk '{print $1}')" = "$orientation_sha"
printf '%s  %s\n' "$oof_sha" "$oof" > "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$pairs_sha" "$pairs" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$cards_sha" "$cards" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$orientation_sha" "$orientation" >> "$root/prereg/input_files.sha256"
echo "PREFLIGHT_ALL_13_PASS $(date -Is)"

set +e
timeout --signal=TERM 600 "$python" -m phase1.pairgraph_intervention \
  --repo-root "$repo" --oof "$oof" --pairs "$pairs" --cards "$cards" \
  --orientation "$orientation" --output-dir "$root/result" \
  --expect-oof-sha256 "$oof_sha" --expect-pairs-sha256 "$pairs_sha" \
  --expect-cards-sha256 "$cards_sha" --expect-orientation-sha256 "$orientation_sha" \
  --wall-cap-s 600
producer_rc=$?
set -e
echo "PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then exit "$producer_rc"; fi

set +e
timeout --signal=TERM 600 "$python" -m phase1.verify_pairgraph_intervention \
  --oof "$oof" --pairs "$pairs" --cards "$cards" --orientation "$orientation" \
  --result-dir "$root/result" --output "$root/result/independent_verify.json" \
  --expect-oof-sha256 "$oof_sha" --expect-pairs-sha256 "$pairs_sha" \
  --expect-cards-sha256 "$cards_sha" --expect-orientation-sha256 "$orientation_sha"
verifier_rc=$?
set -e
echo "VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then exit "$verifier_rc"; fi

find "$root" -type f ! -name 'artifact_manifest.sha256*' ! -name 'preflight.log' -print0 \
  | sort -z | xargs -0 sha256sum > "$root/artifact_manifest.sha256.tmp"
mv "$root/artifact_manifest.sha256.tmp" "$root/artifact_manifest.sha256"
echo "PAIRGRAPH_CHAIN_COMPLETE $root $(date -Is)"
