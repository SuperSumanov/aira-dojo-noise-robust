"""One fixed cheap screen of rank locality; no candidate generation or fitting."""
import csv
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

from rank_locality_guard_20261002 import project, blocks, certificate

B=Path('/research/d7/spc/yzyang4')
SOURCE=B/'repair-opportunity-20261002-v1'
OLD=B/'task-feedback-real-20261001-v6'
OUT=B/'rank-locality-screen-20261002-v1'
TASK='random-acts-of-pizza'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def save(p,value):
    with p.open('x') as f:json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def summary(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None,
                maximum=max(values) if values else None)


def main():
    os.umask(0o077);OUT.mkdir();began=time.monotonic()
    assert sha(SOURCE/'summary.json')=='c714d7daf46ed431f87a7d0428a60a188613b7452541b932b9e7ad20dfb37139'
    save(OUT/'plan.json',dict(role='RETROSPECTIVE_MECHANISM_SCREEN_NOT_NEW_E2E_OR_RULE_DISCOVERY',
        source_sha256=sha(Path(__file__)),operator_sha256=sha(Path(__file__).with_name('rank_locality_guard_20261002.py')),
        source_commit='df7dc14eb2103558708574ae3373b9123cd8b3c4',cohort='all45 Pizza proposals,27 valid parent-child pairs; automatic28/15 separately',
        operator='preserve every cross-group comparison/tie and entire parent score multiset; reorder maximal homogeneous score-level runs by child score',
        groups='original public-training word-count tertiles; all3 applied jointly, NO best-group selection',
        tie_rule='mixed-group parent ties locked; child ties retain parent order',
        primary='guard versus actual parent; all valid and failure denominators, median/variance/win-loss, no selection',
        secondary='raw child; fixed historical strong reference; label-aware within-block oracle as diagnostic headroom only',
        no_expansion_gate='no guarded automatic candidate beats historical strong reference => no GPU expansion of this operator',
        boundary='not universal AUC improvement; labels may make remaining within-group changes beneficial or harmful',
        gpu=0,api_calls=0,fits=0,hard_cpu_seconds=180,invocation=sys.argv))
    sys.path.insert(0,str(OLD));import task_feedback_real_20261001 as runtime
    runtime.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    index=next(r['index'] for r in read(OLD/'plan.json')['schedule'] if r['task']==TASK)
    task=MLEBenchTask(RunConfig.load_from_json(OLD/'configs'/f'{index}.json').task)
    binding=read(SOURCE/'bindings.private.json')
    for name in ('train.json','test.json'):assert sha(task.public_dir/name)==binding[str(task.public_dir/name)]
    train=read(task.public_dir/'train.json');test=read(task.public_dir/'test.json')
    lengths=sorted(len((r.get('request_text_edit_aware') or '').split()) for r in train)
    cuts=[lengths[(len(lengths)-1)//3],lengths[2*(len(lengths)-1)//3]]
    ids=[r['request_id'] for r in test]
    group=[sum(len((r.get('request_text_edit_aware') or '').split())>c for c in cuts) for r in test]
    pairs=[r for r in rows(SOURCE/'pairs.csv') if r['task']==TASK];assert len(pairs)==45
    def loadp(path):
        assert sha(path)==binding[str(path)]
        rr=rows(path);lookup={r['request_id']:float(r['requester_received_pizza']) for r in rr}
        assert len(lookup)==len(rr)==len(ids) and set(lookup)==set(ids)
        return [lookup[i] for i in ids]
    frozen=[]; private=[]
    for r in pairs:
        if r['child_valid']!='True':continue
        ep=B/r['batch']/f'episode-{r["episode"]}'
        p=loadp(ep/f'action-{r["parent_step"]}/submission.private.csv')
        c=loadp(ep/f'action-{r["step"]}/submission.private.csv');out=project(p,c,group)
        assert certificate(p,out,group)
        cell=dict(index=int(r['index']),parent=p,child=c,guard=out)
        path=OUT/f'{r["index"]}.private.json';save(path,cell)
        frozen.append(dict(index=int(r['index']),path=str(path),sha256=sha(path),
            changed_samples=sum(a!=b for a,b in zip(p,out)),movable_blocks=sum(len(b)>1 for b in blocks(p,group))))
        private.append(cell)
    assert len(frozen)==27
    save(OUT/'predictions-frozen.json',dict(plan_sha256=sha(OUT/'plan.json'),rows=frozen,construction_seconds=time.monotonic()-began))
    # Labels are used only after every deterministic candidate is frozen.
    import numpy as np
    spec=task._search_only_module.SPEC[TASK];labelpath=B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
    assert sha(labelpath)==binding[str(labelpath)]
    truth={r['request_id']:int(r['requester_received_pizza']) for r in rows(labelpath)}
    assert set(truth)==set(ids);y=np.array([truth[i] for i in ids]);pos=np.flatnonzero(y==1);neg=np.flatnonzero(y==0)
    def auc(value):
        v=np.array(value);a=v[pos,None];b=v[None,neg]
        return float(((a>b)+.5*(a==b)).mean())
    reference=read(SOURCE/'summary.json')['references'][TASK]['utility'];output=[]
    for r,cell,f in zip([r for r in pairs if r['child_valid']=='True'],private,frozen):
        assert sha(Path(f['path']))==f['sha256']
        p,c,g=cell['parent'],cell['child'],cell['guard'];u0,u1,ug=auc(p),auc(c),auc(g)
        assert abs(u0-float(r['parent_utility']))<1e-11 and abs(u1-float(r['child_utility']))<1e-11
        # Exact best assignment of each block's FIXED score multiset to labels.
        # This deliberately cheats and is saved only as a headroom bound.
        oracle=list(p)
        for block in blocks(p,group):
            for i,value in zip(sorted(block,key=lambda i:(y[i],i)),sorted(p[i] for i in block)):oracle[i]=value
        assert certificate(p,oracle,group)
        uo=auc(oracle);assert uo+1e-11>=max(ug,u0)
        output.append(dict(index=int(r['index']),batch=r['batch'],episode=int(r['episode']),step=int(r['step']),
            parent_step=int(r['parent_step']),generation_seed=r['generation_seed'],automatic_guidance=r['automatic_guidance']=='True',
            parent=u0,child=u1,guard=ug,guard_gain=ug-u0,child_gain=u1-u0,guard_vs_strong=ug-reference,
            within_block_oracle_gain=uo-u0,changed_samples=f['changed_samples'],movable_blocks=f['movable_blocks'],
            plan_sha256=sha(OUT/'plan.json')))
    with (OUT/'rows.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    summaries={}
    for scope in ('all','automatic'):
        subset=[r for r in output if scope=='all' or r['automatic_guidance']]
        summaries[scope]=dict(proposals=sum(scope=='all' or r['automatic_guidance']=='True' for r in pairs),valid=len(subset),
            wins=sum(r['guard_gain']>1e-12 for r in subset),ties=sum(abs(r['guard_gain'])<=1e-12 for r in subset),losses=sum(r['guard_gain'] < -1e-12 for r in subset),
            rescue_worse_child=sum(r['child_gain'] < -1e-12 and r['guard_gain']>1e-12 for r in subset),
            beats_strong=sum(r['guard_vs_strong']>1e-12 for r in subset),guard_gain=summary([r['guard_gain'] for r in subset]),
            oracle_gain=summary([r['within_block_oracle_gain'] for r in subset]),changed_samples=summary([r['changed_samples'] for r in subset]))
    result=dict(status='DESCRIPTIVE_SCREEN_ONLY',plan_sha256=sha(OUT/'plan.json'),rows_sha256=sha(OUT/'rows.csv'),summaries=summaries,
        preserved_cross_group_comparisons=True,gpu=0,api_calls=0,fits=0,elapsed_seconds=time.monotonic()-began)
    save(OUT/'summary.json',result);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
