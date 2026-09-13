"""No refitting: independent raw-label, fixed-matrix and pairwise-AUC checks."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re

SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
BASE=Path('/research/d7/spc/yzyang4')

def sha(raw):return hashlib.sha256(raw).hexdigest()
def label(node):
    if node.get('step')==0 or node.get('exec_time') is None or node.get('exit_code') is None:return None
    flag=(node.get('metric_info') or {}).get('valid_submission',node.get('metric_info/valid_submission'))
    if node['exit_code']!=0:return 0
    if flag is None:return None
    return int(flag is True or flag==1)
def auc(rows,column):
    positives=[float(r[column]) for r in rows if int(r['label'])==1]
    negatives=[float(r[column]) for r in rows if int(r['label'])==0]
    if not positives or not negatives:return None
    return sum(float(a>b)+.5*float(a==b) for a in positives for b in negatives)/(len(positives)*len(negatives))
def checked(path,expected):
    raw=path.read_bytes()
    if sha(raw)!=expected or SECRET.search(raw):raise ValueError('source identity/security')
    return raw

def main(root):
    if root.parent!=BASE or not root.name.startswith('forets-legacy-transfer-20260914-'):raise ValueError('scope')
    summary_raw=(root/'summary.json').read_bytes();summary=json.loads(summary_raw)
    predictions=list(csv.DictReader(checked(root/'predictions.csv',summary['predictions_sha256']).decode().splitlines()))
    inventory_path=Path(summary['inventory_path']);inventory=json.loads(checked(inventory_path,summary['inventory_sha256']))
    legacy=[json.loads(line) for line in checked(inventory_path.parent/'nodes.private.jsonl',inventory['private_nodes_sha256']).splitlines()]
    originals={};legacy_count=0
    for proof in inventory['source_proofs']:
        path=Path(proof['path']);raw=checked(path,proof['sha256'])
        table={n['step']:n for n in (json.loads(line) for line in raw.splitlines() if line.strip())}
        run=str(path.parent.parent.relative_to(BASE/'aira-dojo-runs/aira-dojo'))
        for record in (r for r in legacy if r['run']==run):
            n=table[record['step']]
            if label(n)!=record['label'] or sha(n['code'].encode())!=record['code_sha256']:raise ValueError('legacy label/code mismatch')
            legacy_count+=1
    if legacy_count!=len(legacy):raise ValueError('unverified legacy node')
    for proof in summary['target_source_proofs']:
        path=BASE/proof['root']/'runs'/proof['run_id']/'checkpoint/journal.jsonl'
        for n in (json.loads(line) for line in checked(path,proof['journal_sha256']).splitlines() if line.strip()):
            if label(n) is None or not isinstance(n.get('code'),str) or not n['code'].strip():continue
            key=(proof['root']+'/'+proof['run_id'],n['step'])
            if key in originals:raise ValueError('target duplicate')
            originals[key]=(label(n),sha(n['code'].encode()),len(n['code']))
    completed=[r for r in summary['results'] if r['status']=='completed']
    expected={(r['scope'],r['model'],run,step) for r in completed for run,step in originals}
    keys={(r['scope'],r['model'],r['run'],int(r['step'])) for r in predictions}
    if keys!=expected or len(keys)!=len(predictions):raise ValueError('matrix/target coverage')
    for r in predictions:
        y,h,length=originals[r['run'],int(r['step'])]
        if (int(r['label']),r['code_sha256'])!=(y,h) or float(r['short_code_score'])!=-math.log1p(length):raise ValueError('target label/hash/baseline')
        if not 0<=float(r['predicted_validity'])<=1:raise ValueError('prediction bounds')
    measurements=[]
    for report in completed:
        rr=[r for r in predictions if (r['scope'],r['model'])==(report['scope'],report['model'])]
        for m in report['tasks']:
            selected=[r for r in rr if r['task']==m['task']]
            value=auc(selected,'predicted_validity')
            if abs(value-m['auc'])>1e-12:raise ValueError('independent AUC differs')
            brier=sum((float(r['predicted_validity'])-int(r['label']))**2 for r in selected)/len(selected)
            if abs(brier-m['brier'])>1e-12:raise ValueError('independent Brier differs')
            measurements.append(dict(scope=report['scope'],model=report['model'],task=m['task'],auc=value))
    result=dict(status='verified_independent_labels_coverage_auc_brier',summary_sha256=sha(summary_raw),
        legacy_nodes=legacy_count,target_nodes=len(originals),prediction_rows=len(predictions),measurements=measurements,
        script_sha256=sha(Path(__file__).read_bytes()),limits='Does not independently refit models or reproduce bootstrap intervals.')
    raw=(json.dumps(result,sort_keys=True)+'\n').encode()
    with (root/'independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**result)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);main(parser.parse_args().root.resolve())
