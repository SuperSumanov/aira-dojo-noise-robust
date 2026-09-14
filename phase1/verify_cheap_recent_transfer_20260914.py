"""Independent raw-pool, source-label, fixed-model and paired arithmetic check."""
import os
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]='1'
from contextlib import closing
from collections import defaultdict
import hashlib,importlib.util,json,sqlite3,sys
from pathlib import Path
import numpy as np,joblib
BASE=Path('/research/d7/spc/yzyang4');ROOT=BASE/'forets-wallclock-20260912-88v5m9dr'
SUMMARY='ec995b738f2c49fb57b6e0e8cb3f7c26833f20a5ecf8db93a226963e60483cfb'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(p,expected=None):
    from verify_legacy_validity_transfer_20260914 import SECRET
    raw=p.read_bytes()
    if (expected and sha(raw)!=expected) or SECRET.search(raw):raise ValueError('source identity/security')
    return json.loads(raw)
def main(cohort):
    global ROOT,SUMMARY
    suffix,SUMMARY=SOURCES[cohort]
    ROOT=BASE/('forets-wallclock-20260912-'+suffix)
    result=read(ROOT/'cheap-selector-transfer.json',SUMMARY)
    live=BASE/'forets-wallclock-20260912-km65uuej'
    source=live/'source/src/dojo/solvers/fore_ts/cheap_ranker.py'
    inventory=read(live/'source-files.json')
    if sha(source.read_bytes())!=inventory['src/dojo/solvers/fore_ts/cheap_ranker.py']:raise ValueError('fixed feature implementation')
    spec=importlib.util.spec_from_file_location('fixed_features',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    if sha(Path(mod.MODEL_PATH).read_bytes())!=result['model_sha256']:raise ValueError('fixed model')
    model=joblib.load(mod.MODEL_PATH)['model'];verified=[];cache={};seen=defaultdict(set)
    sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    for row in result['rows']:
        run=row['run'];cp=ROOT/'runs'/run/'checkpoint'
        if run not in cache:
            proof=next(x for x in result['source_proofs'] if x['run']==run);raw=(cp/'journal.jsonl').read_bytes()
            if sha(raw)!=proof['journal_sha256']:raise ValueError('journal drift')
            cache[run]={x['id']:x for x in (json.loads(s) for s in raw.splitlines())}
        p=cp/'forets-candidates-private'/row['pool']
        if sha(p.read_bytes())!=row['pool_sha256']:raise ValueError('pool drift')
        with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
        if sha(raw.encode())!=h:raise ValueError('payload')
        v=json.loads(raw);codes=[];labels=[]
        if v['phase']!='complete' or sorted(v['selected'])!=[0,1] or len(v['candidates'])!=2:raise ValueError('pool eligibility')
        for slot in (0,1):
            g=v['candidates'][slot]['node'];n=cache[run][g['id']];code=g['code'];codes.append(code)
            call=next(c for c in v['task_calls'] if c['intent']['role']=='candidate' and c['slot']==slot)
            if call['state']!='returned' or code!=n['code'] or sha(extract_code(code).encode())!=call['intent']['code_sha256']:raise ValueError('actual original execution')
            if n.get('exit_code') is None:raise ValueError('unknown initial execution')
            flag=(n.get('metric_info') or {}).get('valid_submission',n.get('metric_info/valid_submission'))
            if n['exit_code']==0 and flag is None:raise ValueError('unknown validity')
            labels.append(0 if n['exit_code']!=0 else int(flag is True or flag==1))
        predictions=model.predict_proba(np.asarray([mod.features(c) for c in codes]))[:,1].tolist()
        lengths=[-float(len(c[:30000])) for c in codes]
        if predictions!=row['scores'] or lengths!=row['short_scores'] or labels!=row['labels']:raise ValueError('independent prediction/label mismatch')
        key=tuple(sorted(sha(c.encode()) for c in codes));duplicate=key in seen[run];seen[run].add(key)
        if duplicate!=row['duplicate_within_run']:raise ValueError('duplicate flag')
        values=[]
        for scores in (predictions,lengths):
            top=np.asarray(scores)==max(scores);values.append(float(np.asarray(labels)[top].mean()))
        if (values[0],values[1],values[0]-values[1])!=(row['hgb_validity'],row['short_validity'],row['hgb_minus_short']):raise ValueError('pair arithmetic')
        verified.append(row)
    groups=[]
    for group in result['groups']:
        rr=[r for r in verified if r['task']==group['task'] and r['technical_eligible'] and not r['duplicate_within_run']]
        run_values=defaultdict(list)
        for r in rr:run_values[r['run']].append(r['hgb_minus_short'])
        mean=float(np.mean([np.mean(v) for v in run_values.values()])) if run_values else None
        if (mean is None)!=(group['hgb_minus_short_run_mean'] is None) or (mean is not None and abs(mean-group['hgb_minus_short_run_mean'])>1e-12):raise ValueError('run-equal mean')
        if (len(rr),sum(r['discordant'] for r in rr),len(run_values))!=(group['pairs'],group['discordant'],group['runs']):raise ValueError('denominator')
        groups.append(dict(task=group['task'],run_equal_gain=mean,**{k:group[k] for k in ('runs','pairs','discordant')}))
    primary=[r for r in verified if r['technical_eligible'] and not r['duplicate_within_run']];discordant=[r for r in primary if r['discordant']]
    out=dict(status='independent_raw_execution_model_prediction_and_paired_arithmetic_verified',summary_sha256=SUMMARY,
        all_observed_pairs=len(verified),primary_pairs=len(primary),primary_discordant=len(discordant),
        hgb_valid_on_discordant=sum(r['hgb_validity'] for r in discordant),short_valid_on_discordant=sum(r['short_validity'] for r in discordant),
        hgb_better_than_short=sum(r['hgb_minus_short']>0 for r in primary),hgb_worse_than_short=sum(r['hgb_minus_short']<0 for r in primary),
        groups=groups,script_sha256=sha(Path(__file__).read_bytes()),no_refit=True,
        limitations='Independent raw included-pool/model/statistical checks, not independent completeness or bootstrap reconstruction. Exploratory transfer, not final search utility.')
    raw=(json.dumps(out,sort_keys=True)+'\n').encode()
    with (ROOT/'cheap-selector-transfer-independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**out)))
SOURCES={
 'action':('7wzrny21','56b9ae5c0aed055008b44bc294f73cb9f0ef82263b097ce403a8f81dbf9099e3'),
 'width':('2z2s7sc3','fb3ea5381223d792d642464861f555a0a301a610ff77dd24d78c4af92cce5072'),
 'memory':('103zf3nb','e7ecb9b4b250845511c35efff77379ad6016b84b562e4e6d0032faac9bb0aa98')}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('cohort',choices=tuple(SOURCES));main(p.parse_args().cohort)
