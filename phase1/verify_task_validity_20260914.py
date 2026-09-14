"""Verify fitted-model delivery, raw target labels and pair-count statistics."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import ast,csv,hashlib,json,math,warnings
from collections import Counter
from pathlib import Path
from verify_legacy_validity_transfer_20260914 import checked,label,auc

ROOT=Path('/research/d7/spc/yzyang4/forets-task-validity-20260914-n8q3h72y')
SHA='66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33'
TYPES=('Import','ImportFrom','Call','FunctionDef','ClassDef','For','While','If','Try','With','Assign','Subscript','Attribute','ListComp','DictComp','Lambda','Return','Raise','ExceptHandler','Constant','Name','Compare','BinOp','BoolOp')

def vector(code):
    code=code[:30000]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',SyntaxWarning); tree=ast.parse(code)
        counts=Counter(type(node).__name__ for node in ast.walk(tree))
        def depth(node):return max((1+depth(child) for child in ast.iter_child_nodes(node)),default=0)
        return [math.log1p(len(code)),math.log1p(code.count('\n')+1),0,depth(tree)]+[math.log1p(counts[t]) for t in TYPES]
    except SyntaxError:return [math.log1p(len(code)),math.log1p(code.count('\n')+1),1,0]+[0]*len(TYPES)

def main():
    import joblib,numpy as np
    s=json.loads(checked(ROOT/'summary.json',SHA));raw=checked(ROOT/'predictions.csv',s['predictions_sha256'])
    predictions=list(csv.DictReader(raw.decode().splitlines()));source_count=0
    for item in s['sources']:
        p=Path(item['inventory_path']);inventory=json.loads(checked(p,item['sha256']))
        rows=[json.loads(b) for b in checked(p.parent/'nodes.private.jsonl',inventory['private_nodes_sha256']).splitlines()]
        for proof in inventory['source_proofs']:
            jp=Path(proof['path']);nodes={n['step']:n for n in (json.loads(b) for b in checked(jp,proof['sha256']).splitlines())}
            run=str(jp.parent.parent.relative_to(ROOT.parent/'aira-dojo-runs/aira-dojo'))
            for r in (r for r in rows if r['run']==run):
                n=nodes[r['step']]
                if label(n)!=r['label'] or hashlib.sha256(n['code'].encode()).hexdigest()!=r['code_sha256']:raise ValueError('raw source label/code')
                source_count+=1
    if source_count!=s['train_nodes']:raise ValueError('source coverage; expected no purge')
    targets={}
    for p in s['target_source_proofs']:
        jp=ROOT.parent/p['root']/'runs'/p['run_id']/'checkpoint/journal.jsonl'
        for n in (json.loads(b) for b in checked(jp,p['journal_sha256']).splitlines()):
            if label(n) is None or not isinstance(n.get('code'),str) or not n['code'].strip():continue
            targets[p['root']+'/'+p['run_id'],n['step']]=n
    if len(targets)!=157 or len(predictions)!=314:raise ValueError('target count')
    verified=[]
    for result in s['results']:
        rows=[r for r in predictions if r['condition']==result['condition']]
        if len(rows)!=157 or len({(r['run'],r['step']) for r in rows})!=157:raise ValueError('condition coverage')
        model_path=ROOT/(result['condition']+'.private.joblib');checked(model_path,result['model_sha256'])
        model=joblib.load(model_path);xs=[]
        for r in rows:
            n=targets[r['run'],int(r['step'])]
            if label(n)!=int(r['label']) or hashlib.sha256(n['code'].encode()).hexdigest()!=r['code_sha256']:raise ValueError('target identity')
            v=vector(n['code'])
            if result['condition']=='code_plus_task':v += [int(r['task']==t) for t in model['categories']]
            xs.append(v)
        values=model['model'].predict_proba(np.asarray(xs))[:,1]
        difference=max(abs(float(v)-float(r['predicted_validity'])) for v,r in zip(values,rows))
        if difference>1e-12:raise ValueError('model delivery differs')
        for m in result['tasks']:
            rr=[r for r in rows if r['task']==m['task']]
            if abs(auc(rr,'predicted_validity')-m['auc'])>1e-12:raise ValueError('AUC differs')
        verified.append(dict(condition=result['condition'],prediction_max_abs_difference=difference,model_sha256=result['model_sha256']))
    out=dict(status='verified_raw_labels_independent_features_model_prediction_and_auc',source_summary_sha256=SHA,training_nodes=source_count,
        targets=len(targets),prediction_rows=len(predictions),models=verified,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limits='No independent refit or bootstrap recomputation; reused development targets are not confirmation.')
    raw=(json.dumps(out,sort_keys=True)+'\n').encode()
    with (ROOT/'independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=hashlib.sha256(raw).hexdigest(),**out)))
if __name__=='__main__':main()
