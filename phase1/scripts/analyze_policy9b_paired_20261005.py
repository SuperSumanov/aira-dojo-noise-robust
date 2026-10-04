"""Frozen before result inspection: complete-denominator native base/LoRA readout.
Read only the closed development batch; predictions/labels/code never exported.
"""
import argparse,csv,hashlib,importlib.util,json,math,os,statistics,subprocess,sys
from collections import Counter
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False)
def load(name,p):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def summary(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        sample_variance=statistics.variance(values) if len(values)>1 else None)
def oriented(sft,base,lower):return (base-sft) if lower else (sft-base)
def select_node(rows,lower):
    good=[r for r in rows if r.get('is_buggy') is False and type(r.get('metric')) in (float,int) and math.isfinite(r['metric'])]
    return (min if lower else max)(good,key=lambda r:r['metric']) if good else None
def independent(task,pred_path,spec):
    # Separate library implementation: original scorer uses scalar log sums / pair enumeration.
    import numpy as np
    from sklearn.metrics import roc_auc_score
    with pred_path.open(newline='',encoding='utf-8-sig') as f:preds=list(csv.DictReader(f))
    labels_path=Path('/research/d7/spc/yzyang4')/spec['source']/'private/dsearch.csv'
    manifest_path=Path('/research/d7/spc/yzyang4')/spec['view']/'manifest.json'
    assert sha(manifest_path)==spec['view_sha']
    assert sha(labels_path)==read(manifest_path)['source_dsearch_sha256']
    with labels_path.open(newline='',encoding='utf-8-sig') as f:labels=list(csv.DictReader(f))
    keyed={r[spec['id']]:r for r in preds}
    assert len(keyed)==len(preds)==len(labels) and set(keyed)=={r[spec['id']] for r in labels}
    if task=='random-acts-of-pizza':
        y=np.array([int(r[spec['label']]) for r in labels]);p=np.array([float(keyed[r[spec['id']]][spec['label']]) for r in labels])
        return float(roc_auc_score(y,p))
    p=np.array([[float(keyed[r['id']][c]) for c in ('EAP','HPL','MWS')] for r in labels])
    y=np.array([('EAP','HPL','MWS').index(r['author']) for r in labels]);assert np.isfinite(p).all()
    # Match the frozen scorer's clipping, not sklearn's dtype-dependent epsilon.
    return float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean())
def test():
    assert oriented(.8,.7,False)>0 and oriented(.4,.5,True)>0
    assert select_node([dict(is_buggy=True,metric=1),dict(is_buggy=False,metric=.7)],False)['metric']==.7
    assert select_node([dict(is_buggy=False,metric=.2),dict(is_buggy=False,metric=.6)],True)['metric']==.2
    assert select_node([dict(is_buggy=True,metric=1)],False) is None
    assert summary([])==dict(n=0,median=None,sample_variance=None)
    assert summary([1,3])==dict(n=2,median=2,sample_variance=2)
    print(json.dumps(dict(status='ANALYSIS_CPU_PASS',checks=6,real_results_read=0)))
def main():
    plan=read(R/'plan.json');job=read(R/'launch.json')['job'];assert job.isdigit()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=25).strip().splitlines()
    assert len(accounting)==1
    jid,state,elapsed,tres,exitcode,*_=accounting[0].split('|')
    assert jid==job and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=25).strip()
    assert 'gres/gpu=4' in tres
    for name,digest in plan['files'].items():assert sha(R/name)==digest,name
    assert read(R/'analysis-freeze.json')['analysis_sha256']==sha(Path(__file__))
    output=R/'readout-v1';output.mkdir()
    runs=[];checks=[];task_specs={};node_comparisons=[]
    for s in plan['schedule']:
        ep=R/f"episode-{s['index']}";cfg=read(R/'configs'/f"{s['index']}.json")
        task=s['task'];lower=task=='spooky-author-identification';metric='log_loss' if lower else 'auc'
        scorer_path=Path(cfg['task']['search_only_dev_scorer_path']);assert sha(scorer_path)==cfg['task']['search_only_dev_scorer_sha256']
        spec=load('policy9b_frozen_scorer',scorer_path).SPEC[task];task_specs[task]=spec
        journal=ep/'checkpoint/journal.jsonl'
        nodes=[json.loads(line) for line in journal.read_bytes().splitlines() if line.strip()] if journal.exists() else []
        best=select_node(nodes,lower)
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        if finished:
            assert finished['native_selected_valid']==(best is not None)
            assert finished['native_selected_score']==(None if best is None else best['metric'])
        verified={};external=[]
        for f in sorted(ep.glob('scored-*.json')):
            raw=read(f);receipt=raw['receipt'];pred=f.with_name(f.stem+'.private.csv')
            assert sha(pred)==receipt['submission_sha256']
            value=independent(task,pred,spec);difference=abs(value-receipt[metric])
            assert difference<=1e-12,'independent score mismatch'
            # Outcomes returned after the budget are not valid endpoints.
            assert raw['elapsed_seconds']<=plan['run_seconds']
            verified[receipt['submission_sha256']]=value;external.append(value)
            checks.append(dict(index=s['index'],absolute_error=difference,n=receipt['n'],metric=metric))
        for n in nodes:
            if n.get('is_buggy') is False:
                info=n.get('metric_info') or {};h=info.get('submission_sha256')
                assert h in verified and abs(n['metric']-verified[h])<=1e-12
        role_counts=Counter(r for n in nodes for r in n.get('operators_used',[]))
        failure=read(ep/'failure.json').get('error_type') if (ep/'failure.json').exists() else None
        closed=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        row=dict(**s,metric=metric,lower_is_better=lower,budget_seconds=600,source_commit=plan['source_commit'],
            attempted=(ep/'launch.json').exists(),worker_status=finished.get('status','missing_finished_receipt'),
            failure_type=failure,native_valid=best is not None,native_final=None if best is None else best['metric'],
            external_valid_count=len(external),external_best=(min if lower else max)(external) if external else None,
            candidate_attempts=len(list(ep.glob('candidate-*.private.json'))),journal_nodes=max(0,len(nodes)-1),
            draft_calls=role_counts['draft'],debug_calls=role_counts['debug'],improve_calls=role_counts['improve'],analysis_calls=role_counts['analysis'],
            srun_returncode=closed.get('srun_returncode'),deadline_reached=closed.get('worker_deadline_reached'),
            image_cleanup_certified=closed.get('image_cleanup_certified',False))
        runs.append(row)
    contrasts=[]
    for task in sorted(task_specs):
        group=[r for r in runs if r['task']==task];pairs=[]
        for seed in sorted({r['seed'] for r in group}):
            pair={r['arm']:r for r in group if r['seed']==seed};assert set(pair)=={'base','sft'}
            b,z=pair['base'],pair['sft'];available=b['native_valid'] and z['native_valid']
            pairs.append(dict(seed=seed,base=b['native_final'],sft=z['native_final'],both_valid=available,
                oriented_sft_minus_base=oriented(z['native_final'],b['native_final'],b['lower_is_better']) if available else None))
        differences=[p['oriented_sft_minus_base'] for p in pairs if p['both_valid']]
        contrasts.append(dict(task=task,pairs=pairs,paired_summary=summary(differences),
            all_pairs_positive=len(differences)==2 and all(d>0 for d in differences),
            arms={arm:dict(assigned=2,valid=sum(r['native_valid'] for r in group if r['arm']==arm),
                scores=summary([r['native_final'] for r in group if r['arm']==arm and r['native_valid']])) for arm in ('base','sft')}))
    report=dict(status='CLOSED_DEVELOPMENT_QUALIFICATION',job=job,state=state,exitcode=exitcode,elapsed_seconds=int(elapsed),
        allocated_gpu_hours=4*int(elapsed)/3600,plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(Path(__file__)),
        assigned=8,attempted=sum(r['attempted'] for r in runs),native_valid=sum(r['native_valid'] for r in runs),
        all_closed_receipts=(R/'all-closed.json').exists(),service_ready=(R/'service-ready.json').exists(),
        independent_scores=len(checks),max_independent_abs_error=max((r['absolute_error'] for r in checks),default=None),
        contrasts=contrasts,advance_qualification=all(c['all_pairs_positive'] for c in contrasts),
        limitation='Two reused development tasks and two generation seeds; no official test, unknown training roster/base revision. Qualification not confirmation, power or novelty. Failures remain in denominator.')
    write(output/'summary.json',report);write(output/'independent-checks.json',checks)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(runs[0]));w.writeheader();w.writerows(runs)
    write(output/'export-receipt.json',{p.name:sha(p) for p in output.iterdir() if p.is_file()})
    print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');a=p.parse_args()
    test() if a.test else main()
