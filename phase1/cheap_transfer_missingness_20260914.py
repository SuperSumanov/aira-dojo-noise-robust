"""Sharp paired validity bounds for fixed policies with unobserved outcomes."""
import os
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[n]='1'
from collections import Counter
from contextlib import closing
import itertools,json,math,sqlite3,statistics,sys
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import SOURCES,checked,read,sha,identity,MODEL_ROOT,MODEL_SHA,BASE,vector,label,SECRET

SOURCES=dict(SOURCES,scope=('88v5m9dr','edit-scope-summary.json','8fd3598f99041d7878daec43ef107da68f2e91a340203a726f3c9e8aff1911cd','selection_replays'))
POINT_SHA=dict(scope='ec995b738f2c49fb57b6e0e8cb3f7c26833f20a5ecf8db93a226963e60483cfb',
 action='56b9ae5c0aed055008b44bc294f73cb9f0ef82263b097ce403a8f81dbf9099e3',
 width='fb3ea5381223d792d642464861f555a0a301a610ff77dd24d78c4af92cce5072',
 memory='e7ecb9b4b250845511c35efff77379ad6016b84b562e4e6d0032faac9bb0aa98')
def probs(scores):
    if len(scores)!=2 or any(not math.isfinite(x) for x in scores):raise ValueError('two finite scores')
    if scores[0]==scores[1]:return [.5,.5]
    return [1.,0.] if scores[0]>scores[1] else [0.,1.]
def bounds(hgb,short,labels):
    if len(labels)!=2 or any(v is not None and (type(v) is not int or v not in (0,1)) for v in labels):raise ValueError('known binary or unknown labels')
    delta=[a-b for a,b in zip(probs(hgb),probs(short))]
    lower=sum(min(0,d) if y is None else d*y for d,y in zip(delta,labels))
    upper=sum(max(0,d) if y is None else d*y for d,y in zip(delta,labels))
    # Independent exhaustive truth-table check, at most four assignments.
    possibilities=[sum(d*y for d,y in zip(delta,ys)) for ys in itertools.product(*[((0,1) if y is None else (y,)) for y in labels])]
    if (lower,upper)!=(min(possibilities),max(possibilities)):raise ValueError('sharp-bound enumeration')
    return lower,upper
def main(cohort):
    import io,joblib,numpy as np
    os.umask(0o077);suffix,sname,summary_sha,replaykey=SOURCES[cohort];root=BASE/('forets-wallclock-20260912-'+suffix)
    summary=read(root/sname,summary_sha);finished=read(root/'readout-finished.json')
    if finished['status']!='verified' or finished['files'][sname]!=summary_sha:raise ValueError('closed source')
    original=read(root/'cheap-selector-transfer.json',POINT_SHA[cohort]);oldpoints={(r['run'],r['pool']):r for r in original['rows']}
    ms=read(MODEL_ROOT/'summary.json','66be27cbde084c433df25e95cd803bc7f42df3c71ad7d72af23528205d928a33')
    train=[set(),set(),set()]
    for source in ms['sources']:
        p=Path(source['inventory_path']);inv=read(p,source['sha256'])
        for raw in checked(p.parent/'nodes.private.jsonl',inv['private_nodes_sha256']).splitlines():
            for s,h in zip(train,identity(json.loads(raw)['code'])):s.add(h)
    model=joblib.load(io.BytesIO(checked(MODEL_ROOT/'code_only.private.joblib',MODEL_SHA,False)))['model']
    sys.path.insert(0,str(root/'source/src'))
    from dojo.core.solvers.utils.response import extract_code
    expected={(r['run_id'],r['pool']):r['sha256'] for r in summary[replaykey]}
    sources=[r for r in summary['rows'] if cohort!='scope' or r['arm']=='whole_program']
    if len(sources)!=8:raise ValueError('full planned source')
    rows=[];runs=[];point_checked=set()
    for r in sources:
        cfg=read(root/'configs'/(r['run_id']+'.json'));cp=Path(cfg['solver']['checkpoint_path']);nodes={};reasons=Counter();seen=set();local=[]
        if not cp.resolve().is_relative_to(root/'runs'):raise ValueError('root boundary')
        if (cp/'journal.jsonl').exists():
            for raw in checked(cp/'journal.jsonl').splitlines():
                n=json.loads(raw)
                if n['id'] in nodes:raise ValueError('duplicate journal')
                nodes[n['id']]=n
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            h=sha(p.read_bytes())
            if h!=expected.get((r['run_id'],p.name)):raise ValueError('frozen pool')
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:raw,digest=db.execute('select payload,sha256 from snapshot where id=1').fetchone()
            if sha(raw.encode())!=digest or SECRET.search(raw.encode()) or sha(p.read_bytes())!=h:raise ValueError('payload drift/security')
            v=json.loads(raw)
            if v['binding'].get('common_start'):reasons['bootstrap']+=1;continue
            if len(v['candidates'])!=2:reasons['not_width_two']+=1;continue
            if not all(isinstance(c.get('node'),dict) and isinstance(c['node'].get('code'),str) and c['node']['code'].strip() for c in v['candidates']):reasons['not_two_generated_programs']+=1;continue
            codes=[c['node']['code'] for c in v['candidates']]
            if any(any(hh in s for s,hh in zip(train,identity(c))) for c in codes):reasons['training_overlap']+=1;continue
            ys=[];missing=[]
            for slot,c in enumerate(v['candidates']):
                calls=[x for x in v['task_calls'] if x['intent']['role']=='candidate' and x['slot']==slot]
                if len(calls)>1:raise ValueError('multiple original attempts')
                n=nodes.get(c['node']['id'])
                if not calls or calls[0]['state']!='returned' or n is None:
                    ys.append(None);missing.append('unexecuted_or_unreturned_or_no_journal');continue
                call=calls[0]
                if n['code']!=codes[slot] or sha(extract_code(codes[slot]).encode())!=call['intent']['code_sha256']:raise ValueError('code binding')
                if call['execution_metadata']['exit_code_reported']!=n.get('exit_code'):raise ValueError('exit binding')
                y=label(n);ys.append(y);missing.append('unknown_validity' if y is None else None)
            hs=model.predict_proba(np.asarray([vector(c) for c in codes]))[:,1].tolist();ss=[-float(len(c[:30000])) for c in codes]
            lower,upper=bounds(hs,ss,ys);key=tuple(sorted(sha(c.encode()) for c in codes));duplicate=key in seen;seen.add(key)
            old=oldpoints.get((r['run_id'],p.name))
            if old is not None:
                if old['labels']!=ys or old['scores']!=hs or lower!=upper or lower!=old['hgb_minus_short']:raise ValueError('known-point reproduction')
                point_checked.add((r['run_id'],p.name))
            row=dict(run=r['run_id'],task=r['task'],seed=r['seed'],technical_eligible=r['technical_eligible'],pool=p.name,pool_sha256=h,
                labels=ys,missing_reasons=missing,duplicate_within_run=duplicate,fully_known=all(y is not None for y in ys),
                hgb_scores=hs,short_scores=ss,gain_lower=lower,gain_upper=upper,from_original_complete_case=old is not None)
            rows.append(row);local.append(row);reasons['duplicate' if duplicate else 'applicable_pair']+=1
        unique=[x for x in local if not x['duplicate_within_run']]
        runs.append(dict(run=r['run_id'],task=r['task'],seed=r['seed'],technical_eligible=r['technical_eligible'],reasons=dict(reasons),pairs=len(unique),
            unknown_pairs=sum(not x['fully_known'] for x in unique),gain_lower=statistics.mean(x['gain_lower'] for x in unique) if unique else None,
            gain_upper=statistics.mean(x['gain_upper'] for x in unique) if unique else None))
    if point_checked!=set(oldpoints):raise ValueError('old complete-case coverage lost')
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        rr=[r for r in runs if r['task']==task and r['technical_eligible'] and r['pairs']]
        groups.append(dict(task=task,runs=len(rr),pairs=sum(r['pairs'] for r in rr),unknown_pairs=sum(r['unknown_pairs'] for r in rr),
            run_equal_gain_lower=statistics.mean(r['gain_lower'] for r in rr) if rr else None,
            run_equal_gain_upper=statistics.mean(r['gain_upper'] for r in rr) if rr else None))
    result=dict(role='posthoc_sharp_bounds_initial_validity_not_counterfactual_search',cohort=cohort,source_summary_sha256=summary_sha,point_summary_sha256=POINT_SHA[cohort],
        model_sha256=MODEL_SHA,script_sha256=sha(Path(__file__).read_bytes()),plan_sha256=sha(Path(__file__).with_name('CHEAP_TRANSFER_MISSINGNESS_PLAN_20260914.md').read_bytes()),
        rows=rows,runs=runs,groups=groups,original_points_reproduced=len(point_checked),all_bounds_enumeration_verified=True,api_calls=0,gpu_jobs=0,models_refit=0,
        limits='Identification bounds, not confidence intervals; selected source distribution and workspace interference remain. Does not quantify later search quality or time saved.')
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
    with (root/'cheap-transfer-missingness.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),cohort=cohort,groups=groups,original_points_reproduced=len(point_checked))))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('cohort',choices=tuple(SOURCES));main(p.parse_args().cohort)
