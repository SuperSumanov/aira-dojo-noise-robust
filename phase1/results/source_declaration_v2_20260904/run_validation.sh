#!/usr/bin/env bash
set -euo pipefail
umask 077
readonly root=/tmp/source-declaration-v2-20260904-CYEGWQ
readonly py=/research/d7/spc/yzyang4/venvs/exp/bin/python
cd "$root"
test ! -e results
mkdir -m 0700 results
trap 'rc=$?; printf "validation_exit=%s\n" "$rc" >results/exit_status.txt' EXIT
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$root" CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONHASHSEED=0
printf 'source_commit=7083668352f924860da4613c4dd2724cd3570c37\nmodel_fits=0\nnew_gpu_jobs=0\narchive_payloads=synthetic_test_fixtures_only\n' >results/execution_context.txt
sha256sum code.tar phase1/validate_senior_source_provenance_manifest.py phase1/validate_senior_source_provenance_v2.py \
 phase1/scripts/audit_historical_source_dates_20260904.py phase1/scripts/verify_historical_source_dates_20260904.py >results/source.sha256
"$py" -B -m pytest -p no:cacheprovider -q phase1/tests/test_senior_source_provenance_v2.py phase1/tests/test_senior_source_provenance_manifest.py >results/linux_tests.txt 2>&1
"$py" -B -m phase1.scripts.audit_historical_source_dates_20260904 >results/date_a.json
"$py" -B -m phase1.scripts.audit_historical_source_dates_20260904 >results/date_b.json
cmp results/date_a.json results/date_b.json
digest=$(sha256sum results/date_a.json | cut -d' ' -f1)
"$py" -B -m phase1.scripts.verify_historical_source_dates_20260904 --receipt "$root/results/date_a.json" --sha256 "$digest" >results/independent.json
"$py" -B - results/independent.json <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
assert r['status']=='INDEPENDENT_HISTORICAL_DATE_DIAGNOSTIC_MATCH'
print(json.dumps({'status':'SOURCE_DECLARATION_V2_VALIDATED','metrics':r['metrics'],'date_receipt_sha256':r['receipt_sha256']},sort_keys=True))
PY
printf 'VALIDATION_COMPLETE_NO_EFFECT_FIT\n' >results/COMPLETE
