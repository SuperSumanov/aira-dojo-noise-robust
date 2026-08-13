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
pairs=phase1/v11_decision/decision_train_v11_b0.jsonl
cards=/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl
fold_oof=phase1/results/heterogeneous_oof_v11_20260814/oof_predictions.csv
orientation=phase1/task_orientation.json
protocol_json=phase1/tgca_protocol_v1.json
pairs_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
fold_oof_sha=fc57c03a1c96ce7be19a4db764a539082258fe4c69a2ec8653b41ff85626cb45
orientation_sha=e11111a3538c54eb91048b54380466b4dc0f041c2f511a78a85573cbc92b121a
protocol_sha=52a6046798ca5a03438b5973145f20f4261702ff874f3a98738981fe782e487b

cd "$repo"
test "$(pwd -P)" = "$repo"
commit=$(git rev-parse HEAD)
root=/research/d7/spc/yzyang4/experiments/tgca_v11_20260814_${commit:0:12}
if [[ -e "$root" ]]; then
  echo "ABORT_EXISTING_APPEND_ONLY_ROOT $root" >&2
  exit 2
fi
mkdir -p "$root/prereg" "$root/audits" "$root/smoke" "$root/result"
exec > >(tee "$root/preflight.log") 2>&1

echo "PREFLIGHT_BEGIN $(date -Is)"
echo "PREFLIGHT_01_ARTIFACT_KNOBS"
test -z "$(git status --short)"
printf '%s\n' "$commit" > "$root/prereg/expected_commit.txt"
cp phase1/tgca_discovery.py "$root/prereg/"
cp phase1/verify_tgca_discovery.py "$root/prereg/"
cp phase1/tgca_engineering_smoke.py "$root/prereg/"
cp phase1/tgca_protocol_v1.json "$root/prereg/"
cp phase1/tests/test_tgca_discovery.py "$root/prereg/"
cp phase1/实验记录/2026-08-14/TGCA_预注册.md "$root/prereg/"
cp phase1/实验记录/2026-08-14/TGCA_长实验预检.md "$root/prereg/"
cp phase1/scripts/run_tgca_discovery_20260814.sh "$root/prereg/"
sha256sum "$root"/prereg/* > "$root/prereg/source_files.sha256"
"$python" -m pip freeze > "$root/prereg/python_environment.txt"
uname -a > "$root/prereg/system.txt"
lscpu >> "$root/prereg/system.txt"

echo "PREFLIGHT_02_CHEAP_TESTS"
"$python" -m py_compile phase1/tgca_discovery.py phase1/verify_tgca_discovery.py phase1/tgca_engineering_smoke.py
"$test_python" -m pytest -q phase1/tests/test_tgca_discovery.py
"$python" -m phase1.tgca_discovery --help > "$root/prereg/producer_help.txt"
"$python" -m phase1.verify_tgca_discovery --help > "$root/prereg/verifier_help.txt"

echo "PREFLIGHT_03_INPUT_AND_FORBIDDEN_PATH"
if grep -Eiq -- '--[^ ]*(frozen|test|held)' "$root/prereg/producer_help.txt" "$root/prereg/verifier_help.txt"; then
  echo "ABORT_FORBIDDEN_PAIR_ARGUMENT" >&2
  exit 3
fi
if grep -Eq 'temporal_blind_0812|label_vault.jsonl' phase1/tgca_discovery.py phase1/verify_tgca_discovery.py; then
  echo "ABORT_TEMPORAL_VAULT_REFERENCE" >&2
  exit 3
fi
grep -q 'does not import.*tgca_discovery' phase1/verify_tgca_discovery.py

echo "PREFLIGHT_04_DISTRIBUTION"
"$python" - "$pairs" "$fold_oof" "$root/audits/support.json" <<'PY'
import collections,csv,json,sys
pairs=[json.loads(line) for line in open(sys.argv[1],encoding='utf-8') if line.strip()]
folds=list(csv.DictReader(open(sys.argv[2],encoding='utf-8',newline='')))
assert len(pairs)==len(folds)==4263
runs={}; endpoints={}; parents=set(); tasks=set()
for i,(pair,fold) in enumerate(zip(pairs,folds)):
    assert pair['intask_split']=='train' and int(pair['budget'])==0 and int(fold['row_index'])==i
    for key,pkey in [('task','task'),('run','run_id'),('parent','parent'),('better','better'),('worse','worse')]:
        assert fold[key]==str(pair[pkey])
    f=int(fold['fold']); run=str(pair['run_id'])
    assert 0<=f<5 and runs.setdefault(run,f)==f
    tasks.add(str(pair['task'])); parents.add(str(pair['parent']))
    for side in ('better','worse'):
        value=(str(pair['task']),run,str(pair['parent']),f)
        assert endpoints.setdefault(str(pair[side]),value)==value
payload={'pairs':len(pairs),'runs':len(runs),'tasks':len(tasks),'parents':len(parents),'endpoints':len(endpoints),
         'fold_pairs':dict(sorted(collections.Counter(int(x['fold']) for x in folds).items())),
         'fold_runs':dict(sorted(collections.Counter(runs.values()).items()))}
assert {k:payload[k] for k in ('pairs','runs','tasks','parents','endpoints')}=={
    'pairs':4263,'runs':333,'tasks':23,'parents':2293,'endpoints':5499}
open(sys.argv[3],'w',encoding='utf-8').write(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print('SUPPORT_EXACT',payload)
PY

echo "PREFLIGHT_05_BALANCE_AND_SUPPORT"
"$python" - "$pairs" "$root/audits/balance.json" <<'PY'
import collections,json,sys
rows=[json.loads(line) for line in open(sys.argv[1],encoding='utf-8') if line.strip()]
counts=collections.Counter(str(row['task']) for row in rows)
supported={task:n for task,n in sorted(counts.items()) if n>=20}
payload={'supported_tasks_min20':len(supported),'dominant_task':counts.most_common(1)[0][0],
         'dominant_task_share':counts.most_common(1)[0][1]/len(rows),'per_task_pairs':dict(sorted(counts.items()))}
assert payload['supported_tasks_min20']>=15 and payload['dominant_task_share']<=0.25
open(sys.argv[2],'w',encoding='utf-8').write(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print('BALANCE_PASS',payload['supported_tasks_min20'],payload['dominant_task_share'])
PY

echo "PREFLIGHT_06_CHECKPOINT_RESUME"
grep -q 'checkpoint_key' phase1/tgca_discovery.py
grep -q 'valid_scores.npz' phase1/tgca_discovery.py
grep -q 'os.replace(temporary, final)' phase1/tgca_discovery.py
grep -q 'refit score mismatch' phase1/verify_tgca_discovery.py
printf '%s\n' 'atomic fold checkpoints; exact key and artifact SHA on resume' > "$root/prereg/checkpoint_contract.txt"

echo "PREFLIGHT_07_LEAKAGE"
"$python" - "$pairs" "$fold_oof" "$cards" "$root/audits/isolation.json" \
  "$pairs_sha" "$fold_oof_sha" "$cards_sha" <<'PY'
import json,sys
from pathlib import Path
from phase1 import tgca_discovery as t
pairs,folds,cards,out,pair_sha,fold_sha,card_sha=sys.argv[1:]
rows,meta,_=t.load_rows_and_folds(Path(pairs),Path(folds),pair_sha,fold_sha)
selected,_=t.load_cards(Path(cards),meta,card_sha)
audits=[t.fold_isolation(fold,rows,selected) for fold in range(5)]
assert all(a['run_overlap']==a['endpoint_overlap']==a['raw_code_sha_overlap']==0 for a in audits)
Path(out).write_text(json.dumps(audits,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print('THREE_LAYER_FOLD_ISOLATION_ZERO',[(x['fit_runs'],x['valid_runs']) for x in audits])
PY
grep -q 'post_execution_fields_retained.*0' phase1/tgca_discovery.py
grep -q 'non_allowlisted_cards_retained.*0' phase1/tgca_discovery.py

echo "PREFLIGHT_08_RNG_NUMERICS"
grep -q '^MODEL_SEED = 887$' phase1/tgca_discovery.py
grep -q '^EDGE_SEED = 20_260_814$' phase1/tgca_discovery.py
grep -q '^BOOTSTRAP_SEED = 20_260_815$' phase1/tgca_discovery.py
grep -q '^BOOTSTRAP_REPS = 10_000$' phase1/tgca_discovery.py
grep -q 'fit_intercept=False' phase1/tgca_discovery.py
grep -q 'dtype=np.float64' phase1/tgca_discovery.py

echo "PREFLIGHT_09_SECRETS"
filename_count=$(git diff --cached --name-only | grep -icE 'env|key|token|secret' || true)
echo "STAGED_FILENAME_SECRET_COUNT $filename_count"
test "$filename_count" -eq 0
if grep -REIq 'sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}' \
  phase1/tgca_discovery.py phase1/verify_tgca_discovery.py phase1/tgca_engineering_smoke.py \
  phase1/tests/test_tgca_discovery.py phase1/tgca_protocol_v1.json \
  phase1/实验记录/2026-08-14/TGCA_预注册.md phase1/实验记录/2026-08-14/TGCA_长实验预检.md; then
  echo "ABORT_SECRET_PATTERN" >&2
  exit 9
fi
echo "HIGH_CONFIDENCE_SECRET_COUNT 0"

echo "PREFLIGHT_10_WALL_CLOCK_SMOKE"
set +e
timeout --signal=TERM 1800 "$python" -m phase1.tgca_engineering_smoke \
  --repo-root "$repo" --pairs "$pairs" --cards "$cards" --fold-oof "$fold_oof" \
  --orientation "$orientation" --output-dir "$root/smoke/work" --output "$root/smoke/summary.json" \
  --expect-pairs-sha256 "$pairs_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-fold-oof-sha256 "$fold_oof_sha" --expect-orientation-sha256 "$orientation_sha" \
  --formal-chain-budget-s 14400
smoke_rc=$?
set -e
echo "SMOKE_RC $smoke_rc"
test "$smoke_rc" -eq 0

echo "PREFLIGHT_11_TRAINING_POWER"
"$python" - "$root/smoke/summary.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
assert p['status']=='TGCA_ENGINEERING_SMOKE_PASS' and p['accuracy_computed'] is False and p['metrics_computed']==[]
assert p['pairs']==4263 and p['runs']==333 and p['tasks']==23 and p['parents']==2293 and p['endpoints']==5499
assert p['all_models_accepted'] and p['within_formal_chain_budget']
print('ENGINEERING_AND_BUDGET_PASS',p['elapsed_s'],p['conservative_formal_chain_extrapolation_s'],p['max_rss_kib'])
PY

echo "PREFLIGHT_12_TRUE_RC"
printf '%s\n' 'producer_rc and verifier_rc captured immediately before any later command' > "$root/prereg/rc_contract.txt"

echo "PREFLIGHT_13_APPEND_ONLY_HASHES"
test "$(sha256sum "$pairs" | awk '{print $1}')" = "$pairs_sha"
test "$(sha256sum "$cards" | awk '{print $1}')" = "$cards_sha"
test "$(sha256sum "$fold_oof" | awk '{print $1}')" = "$fold_oof_sha"
test "$(sha256sum "$orientation" | awk '{print $1}')" = "$orientation_sha"
test "$(sha256sum "$protocol_json" | awk '{print $1}')" = "$protocol_sha"
printf '%s  %s\n' "$pairs_sha" "$pairs" > "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$cards_sha" "$cards" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$fold_oof_sha" "$fold_oof" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$orientation_sha" "$orientation" >> "$root/prereg/input_files.sha256"
printf '%s  %s\n' "$protocol_sha" "$protocol_json" >> "$root/prereg/input_files.sha256"
echo "PREFLIGHT_ALL_13_PASS $(date -Is)"

printf '%q ' "$python" -m phase1.tgca_discovery \
  --repo-root "$repo" --pairs "$pairs" --cards "$cards" --fold-oof "$fold_oof" \
  --orientation "$orientation" --protocol-json "$protocol_json" --output-dir "$root/result" \
  --expect-pairs-sha256 "$pairs_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-fold-oof-sha256 "$fold_oof_sha" --expect-orientation-sha256 "$orientation_sha" \
  --expect-protocol-sha256 "$protocol_sha" --wall-cap-s 7200 > "$root/prereg/producer_command.txt"
printf '\n' >> "$root/prereg/producer_command.txt"
set +e
timeout --signal=TERM 7200 "$python" -m phase1.tgca_discovery \
  --repo-root "$repo" --pairs "$pairs" --cards "$cards" --fold-oof "$fold_oof" \
  --orientation "$orientation" --protocol-json "$protocol_json" --output-dir "$root/result" \
  --expect-pairs-sha256 "$pairs_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-fold-oof-sha256 "$fold_oof_sha" --expect-orientation-sha256 "$orientation_sha" \
  --expect-protocol-sha256 "$protocol_sha" --wall-cap-s 7200
producer_rc=$?
set -e
echo "PRODUCER_RC $producer_rc"
if [[ "$producer_rc" -ne 0 ]]; then exit "$producer_rc"; fi

printf '%q ' "$python" -m phase1.verify_tgca_discovery \
  --pairs "$pairs" --cards "$cards" --fold-oof "$fold_oof" --orientation "$orientation" \
  --protocol-json "$protocol_json" --result-dir "$root/result" --output "$root/result/independent_verify.json" \
  --expect-pairs-sha256 "$pairs_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-fold-oof-sha256 "$fold_oof_sha" --expect-orientation-sha256 "$orientation_sha" \
  --expect-protocol-sha256 "$protocol_sha" > "$root/prereg/verifier_command.txt"
printf '\n' >> "$root/prereg/verifier_command.txt"
set +e
timeout --signal=TERM 7200 "$python" -m phase1.verify_tgca_discovery \
  --pairs "$pairs" --cards "$cards" --fold-oof "$fold_oof" --orientation "$orientation" \
  --protocol-json "$protocol_json" --result-dir "$root/result" --output "$root/result/independent_verify.json" \
  --expect-pairs-sha256 "$pairs_sha" --expect-cards-sha256 "$cards_sha" \
  --expect-fold-oof-sha256 "$fold_oof_sha" --expect-orientation-sha256 "$orientation_sha" \
  --expect-protocol-sha256 "$protocol_sha"
verifier_rc=$?
set -e
echo "VERIFIER_RC $verifier_rc"
if [[ "$verifier_rc" -ne 0 ]]; then exit "$verifier_rc"; fi

find "$root" -type f ! -name 'artifact_manifest.sha256*' ! -name 'preflight.log' -print0 \
  | sort -z | xargs -0 sha256sum > "$root/artifact_manifest.sha256.tmp"
mv "$root/artifact_manifest.sha256.tmp" "$root/artifact_manifest.sha256"
echo "TGCA_CHAIN_COMPLETE $root $(date -Is)"
