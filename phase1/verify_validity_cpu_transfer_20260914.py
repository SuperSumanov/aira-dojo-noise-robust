"""Independent target and pair-count AUC check; no sklearn or refitting."""
from collections import Counter,defaultdict
import csv,hashlib,json,math
from pathlib import Path
import re

ROOT=Path('/research/d7/spc/yzyang4/forets-validity-cpu-20260914-ieceg8zb')
SUMMARY_SHA='7c862828b7a629f6a57623921ccb8444b58322672c59602fa4fd96c635905728'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(b):return hashlib.sha256(b).hexdigest()
def auc(rows,column):
    positive=[float(r[column]) for r in rows if int(r['label'])==1]
    negative=[float(r[column]) for r in rows if int(r['label'])==0]
    if not positive or not negative:return None
    return sum(1 if p>n else .5 if p==n else 0 for p in positive for n in negative)/(len(positive)*len(negative))
def main():
    raw=(ROOT/'summary.json').read_bytes()
    if sha(raw)!=SUMMARY_SHA:raise ValueError('closed summary drift')
    s=json.loads(raw);predraw=(ROOT/'oof-predictions.csv').read_bytes()
    if sha(predraw)!=s['prediction_sha256']:raise ValueError('predictions drift')
    predictions=list(csv.DictReader(predraw.decode().splitlines()));original={}
    for proof in s['source_proofs']:
        p=ROOT.parent/proof['root']/'runs'/proof['run_id']/'checkpoint/journal.jsonl';raw=p.read_bytes()
        if sha(raw)!=proof['journal_sha256'] or SECRET.search(raw):raise ValueError('source security/identity')
        for line in raw.splitlines():
            node=json.loads(line)
            if node['step']==0 or node.get('exec_time') is None or node.get('exit_code') is None:continue
            values=[]
            if 'valid_submission' in (node.get('metric_info') or {}):values.append(node['metric_info']['valid_submission'])
            if 'metric_info/valid_submission' in node:values.append(node['metric_info/valid_submission'])
            if values and any(v!=values[0] for v in values):raise ValueError('conflicting validity')
            valid=values[0] if values else None
            if node['exit_code']==0 and valid is None:continue
            label=1 if node['exit_code']==0 and valid==1 else 0
            if not isinstance(node.get('code'),str) or not node['code'].strip():continue
            original[(proof['root'],proof['run_id'],node['step'])]=(label,sha(node['code'].encode()),-math.log1p(len(node['code'])))
    verified=[]
    for result in s['results']:
        rows=[r for r in predictions if r['mode']==result['mode']]
        keys=[(r['root'],r['run_id'],int(r['step'])) for r in rows]
        if len(keys)!=len(set(keys)) or set(keys)!=set(original):raise ValueError('exact OOF coverage')
        byrun=defaultdict(set)
        for r,key in zip(rows,keys):
            label,h,length=original[key]
            if int(r['label'])!=label or r['code_sha256']!=h or abs(float(r['short_code_score'])-length)>1e-12:raise ValueError('target/hash/length mismatch')
            for field in ('predicted_validity','prior_validity'):
                if not math.isfinite(float(r[field])) or not 0<=float(r[field])<=1:raise ValueError('invalid probability')
            byrun[r['run']].add(int(r['fold']))
        if any(len(v)!=1 for v in byrun.values()):raise ValueError('run split leakage')
        for fold in result['folds']:
            test=[r for r in rows if int(r['fold'])==fold['fold']];test_ast={r['ast_key'] for r in test}
            before=[r for r in rows if int(r['fold'])!=fold['fold']];train=[r for r in before if r['ast_key'] not in test_ast]
            if len(train)!=fold['train'] or len(test)!=fold['test'] or len(before)-len(train)!=fold['purged_exact_ast_training_rows']:raise ValueError('purged fold sizes')
            count=Counter(r['run'] for r in train)
            prior=sum(int(r['label'])/count[r['run']] for r in train)/len(count)
            if any(abs(float(r['prior_validity'])-prior)>1e-12 for r in test):raise ValueError('train-only prior')
            if result['mode']=='protocol' and len({r['root'] for r in test})!=1:raise ValueError('protocol holdout')
        computed=[]
        for expected in result['tasks']:
            taskrows=[r for r in rows if r['task']==expected['task']];a=auc(taskrows,'predicted_validity')
            b=sum((float(r['predicted_validity'])-int(r['label']))**2 for r in taskrows)/len(taskrows)
            if abs(a-expected['auc'])>1e-12 or abs(b-expected['brier'])>1e-12:raise ValueError('independent metric mismatch')
            short=auc(taskrows,'short_code_score');prior=auc(taskrows,'prior_validity')
            e_short=next(x['auc'] for x in result['short_code_tasks'] if x['task']==expected['task'])
            e_prior=next(x['auc'] for x in result['constant_baseline_tasks'] if x['task']==expected['task'])
            if abs(short-e_short)>1e-12 or abs(prior-e_prior)>1e-12:raise ValueError('baseline mismatch')
            computed.append(dict(task=expected['task'],auc=a,short_code_auc=short,prior_auc=prior,n=len(taskrows)))
        if abs(sum(r['auc'] for r in computed)/len(computed)-result['macro_auc'])>1e-12:raise ValueError('macro mismatch')
        verified.append(dict(mode=result['mode'],tasks=computed,all_checks=True))
    output=dict(summary_sha256=SUMMARY_SHA,verified=verified,source_nodes=len(original),oof_rows=len(predictions),
        method='independent raw targets, run/AST-purged fold sizes, training-only priors, direct positive-negative pair AUC',
        no_refit=True,no_external_grade=True,bootstrap_note='bootstrap interval not independently rerun',all_checks_pass=True)
    raw=(json.dumps(output,sort_keys=True)+'\n').encode()
    with (ROOT/'independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(output|dict(independent_sha256=sha(raw))))
if __name__=='__main__':main()
