"""Post-hoc robustness on three entire completed recent protocols; no fitting."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
from collections import Counter,defaultdict
from contextlib import closing
import ast,hashlib,io,json,math,sqlite3,statistics,sys,warnings
from pathlib import Path
from analyze_scope_short_control_20260914 import SECRET,label
from verify_task_validity_20260914 import vector

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'forets-wallclock-20260912-88v5m9dr'
MODEL_ROOT=BASE/'forets-task-validity-20260914-n8q3h72y'
SUMMARY_SHA='8fd3598f99041d7878daec43ef107da68f2e91a340203a726f3c9e8aff1911cd'
MODEL_SHA='05379469122879c798f1d2c571eb733956a067dac314050feeb06d3e09c641d1'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def checked(path,expected=None,secret=True):
    raw=path.read_bytes()
    if (expected is not None and sha(raw)!=expected) or (secret and SECRET.search(raw)):raise ValueError('hash/security at approved input')
    return raw
def read(path,expected=None):return json.loads(checked(path,expected))
def identity(code):
    try:
        with warnings.catch_warnings():warnings.simplefilter('ignore',SyntaxWarning);tree=ast.parse(code)
        normalized=sha(ast.dump(tree,include_attributes=False).encode())
    except SyntaxError:normalized='invalid:'+sha(code.encode())
    return sha(code.encode()),normalized,sha(code[:30000].encode())
def expected_validity(scores,labels):
    if len(scores)!=2 or len(labels)!=2 or any(type(y) is not int or y not in (0,1) for y in labels):raise ValueError('two known labels')
    if any(not math.isfinite(s) for s in scores):raise ValueError('finite scores')
    indices=[i for i,s in enumerate(scores) if s==max(scores)]
    return sum(labels[i] for i in indices)/len(indices)
def bootstrap(values):
    import numpy as np
    if not values:return None
    a=np.array(values);rng=np.random.default_rng(20260914)
    draws=a[rng.integers(len(a),size=(2000,len(a)))].mean(axis=1)
    return [float(np.quantile(draws,q)) for q in (.025,.975)]
def main(cohort):
    global ROOT,SUMMARY_SHA
    suffix,SUMMARY_NAME,SUMMARY_SHA,REPLAY_KEY=SOURCES[cohort]
    ROOT=BASE/('forets-wallclock-20260912-'+suffix)
    import joblib,numpy as np
    os.umask(0o077)
    summary=read(ROOT/SUMMARY_NAME,SUMMARY_SHA)
    finish=read(ROOT/'readout-finished.json')
    if finish['status']!='verified' or finish['files'][SUMMARY_NAME]!=SUMMARY_SHA:raise ValueError('all-closed source')
    ms=read(MODEL_ROOT/'summary.json','66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33')
    train=[set(),set(),set()]
    for src in ms['sources']:
        p=Path(src['inventory_path']);inv=read(p,src['sha256'])
        for line in checked(p.parent/'nodes.private.jsonl',inv['private_nodes_sha256']).splitlines():
            n=json.loads(line)
            for s,h in zip(train,identity(n['code'])):s.add(h)
    artifact=joblib.load(io.BytesIO(checked(MODEL_ROOT/'code_only.private.joblib',MODEL_SHA,False)))
    if artifact['condition']!='code_only':raise ValueError('fixed condition')
    model=artifact['model'];sys.path.insert(0,str(ROOT/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    expected={(r['run_id'],r['pool']):r['sha256'] for r in summary[REPLAY_KEY]}
    sources=summary['rows']
    if ROOT.name in {p['root'] for p in ms['target_source_proofs']}:raise ValueError('reused model development root')
    if len(sources)!=8:raise ValueError('all planned protocol runs')
    rows=[];runs=[];proofs=[]
    for r in sources:
        cfg=read(ROOT/'configs'/(r['run_id']+'.json'));cp=Path(cfg['solver']['checkpoint_path'])
        if not cp.resolve().is_relative_to(ROOT/'runs'):raise ValueError('source scope')
        jp=cp/'journal.jsonl';nodes={};reasons=Counter();seen=set();local=[]
        if jp.exists():
            raw=checked(jp);proofs.append(dict(run=r['run_id'],journal_sha256=sha(raw)))
            for line in raw.splitlines():
                n=json.loads(line)
                if n['id'] in nodes:raise ValueError('duplicate journal id')
                nodes[n['id']]=n
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            if before!=expected.get((r['run_id'],p.name)):raise ValueError('frozen pool drift')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,h=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=h or SECRET.search(raw.encode()) or sha(p.read_bytes())!=before:raise ValueError('pool hash/security')
            v=json.loads(raw)
            if v['binding'].get('common_start'):reasons['bootstrap']+=1;continue
            if len(v['candidates'])!=2 or v['phase']!='complete' or set(v['selected'] or [])!={0,1}:reasons['not_complete_two_executed']+=1;continue
            calls=[c for c in v['task_calls'] if c['intent']['role']=='candidate']
            if len(calls)!=2 or {c['slot'] for c in calls}!={0,1} or any(c['state']!='returned' for c in calls):reasons['original_calls_unknown']+=1;continue
            codes=[];ys=[];skip=None
            for slot in (0,1):
                c=next(c for c in calls if c['slot']==slot);g=v['candidates'][slot]['node']
                if not isinstance(g,dict) or g['id'] not in nodes:skip='original_journal_missing';break
                n=nodes[g['id']];code=g['code']
                if sha(code.encode())!=sha(n['code'].encode()) or sha(extract_code(code).encode())!=c['intent']['code_sha256']:raise ValueError('native/raw code binding')
                if c['execution_metadata']['exit_code_reported']!=n.get('exit_code'):raise ValueError('exit metadata')
                y=label(n)
                if y is None:skip='initial_label_unknown';break
                if any(h in s for s,h in zip(train,identity(code))):skip='training_overlap';break
                codes.append(code);ys.append(y)
            if skip:reasons[skip]+=1;continue
            key=tuple(sorted(sha(c.encode()) for c in codes));duplicate=key in seen;seen.add(key)
            scores=[float(x) for x in model.predict_proba(np.asarray([vector(c) for c in codes]))[:,1]]
            lengths=[float(-len(c[:30000])) for c in codes]
            hv=expected_validity(scores,ys);sv=expected_validity(lengths,ys);uv=sum(ys)/2
            row=dict(run=r['run_id'],task=r['task'],seed=r['seed'],technical_eligible=r['technical_eligible'],pool=p.name,pool_sha256=before,
                code_sha256=list(key),labels=ys,scores=scores,short_scores=lengths,duplicate_within_run=duplicate,discordant=ys[0]!=ys[1],
                hgb_validity=hv,short_validity=sv,uniform_validity=uv,hgb_minus_short=hv-sv,hgb_minus_uniform=hv-uv)
            rows.append(row);local.append(row);reasons['eligible_observed_duplicate' if duplicate else 'eligible_unique_pair']+=1
        unique=[x for x in local if not x['duplicate_within_run']]
        runs.append(dict(run=r['run_id'],task=r['task'],seed=r['seed'],technical_eligible=r['technical_eligible'],reasons=dict(reasons),all_pairs=len(local),unique_pairs=len(unique),
            discordant=sum(x['discordant'] for x in unique),hgb_minus_short=statistics.mean(x['hgb_minus_short'] for x in unique) if unique else None,
            hgb_minus_uniform=statistics.mean(x['hgb_minus_uniform'] for x in unique) if unique else None))
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        selected=[r for r in runs if r['task']==task and r['technical_eligible'] and r['unique_pairs']]
        pairs=[x for x in rows if x['task']==task and x['technical_eligible'] and not x['duplicate_within_run']]
        groups.append(dict(task=task,runs=len(selected),pairs=len(pairs),discordant=sum(x['discordant'] for x in pairs),
            hgb_strict_valid=sum(x['hgb_validity']==1 for x in pairs if x['discordant']),short_strict_valid=sum(x['short_validity']==1 for x in pairs if x['discordant']),
            hgb_minus_short_run_mean=statistics.mean(r['hgb_minus_short'] for r in selected) if selected else None,
            hgb_minus_short_run_bootstrap=bootstrap([r['hgb_minus_short'] for r in selected]),
            hgb_minus_uniform_run_mean=statistics.mean(r['hgb_minus_uniform'] for r in selected) if selected else None,
            hgb_minus_uniform_run_bootstrap=bootstrap([r['hgb_minus_uniform'] for r in selected])))
    out=dict(role='posthoc_fixed_model_recent_protocol_transfer',cohort=cohort,source_root=str(ROOT),source_summary_sha256=SUMMARY_SHA,model_sha256=MODEL_SHA,
        script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_RECENT_TRANSFER_PLAN_20260914.md').read_bytes()),
        rows=rows,runs=runs,groups=groups,source_proofs=proofs,api_calls=0,gpu_jobs=0,models_refit=0,
        limits='Selected old-search distribution; sequential workspace interference; eight planned runs, fewer technically eligible. Initial validity is not final quality or counterfactual search utility. Does not change the prospective fixed selector or any investment gate.')
    raw=(json.dumps(out,sort_keys=True,allow_nan=False)+'\n').encode()
    with (ROOT/'cheap-selector-transfer.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),groups=groups,runs=runs)))
SOURCES={
    'action':('7wzrny21','action-delivery-summary.json','182e8a424cc99e7cdd0ec9a46a219ba84f05a1c578ca6d2dc8ff9685fbb80d65','policy_replays'),
    'width':('2z2s7sc3','width-summary.json','9ceacd308c7928b243094f09ae028f34e2e0df1e5fc32b21ba04f5a26febfff8','selection_replays'),
    'memory':('103zf3nb','memory-summary.json','a7e5aaf94cf1ecf4d12f6debde0ee0342a6a972c7a19b2ea7615287e573c08c0','selection_replays')}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('cohort',choices=tuple(SOURCES));main(p.parse_args().cohort)
