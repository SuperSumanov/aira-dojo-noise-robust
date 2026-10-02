"""Independent pair-count AUC for the manual one-keyword opportunity control."""
import argparse,csv,hashlib,json,math,os,statistics,subprocess,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/char-branch-control-20261003-v1')
PLAN='e989f2f0d3d585812fda44bca0b2b6de5124b2222d9c1b2554800f0a4d997269'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def status():
    assert sha(R/'plan.json')==PLAN
    return dict(job=read(R/'launch.json')['job'],closed=(R/'closed.json').exists(),
        workers=[dict(index=i,native=(R/f'episode-{i}/native.json').exists(),closed=(R/f'episode-{i}/closed.json').exists(),
        results=len(list((R/f'episode-{i}').glob('action-*/result.json')))) for i in range(2)])
def analyze():
    assert sha(R/'plan.json')==PLAN and (R/'closed.json').exists()
    p=read(R/'plan.json')
    for rel,h in p['files'].items():assert sha(R/rel)==h
    sys.path.insert(0,str(R));from char_branch_control_20261003 import runtime
    m=runtime();from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    cfg=RunConfig.load_from_json(R/'configs/0.json');task=MLEBenchTask(cfg.task);spec=task._search_only_module.SPEC[cfg.task.name]
    labels=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv');truth={r['request_id']:r for r in labels};assert len(truth)==len(labels)
    records=[];checks=[]
    for i,seed in enumerate(p['seeds']):
        for step,arm in enumerate(p['order'][i]):
            a=R/f'episode-{i}/action-{step}';result=read(a/'result.json') if (a/'result.json').exists() else None
            row=dict(task=cfg.task.name,index=i,seed=seed,step=step,arm=arm,valid=False,metric=None,seconds=None,blend_oof_auc=None,
                     lgb_oof_auc=None,xgb_oof_auc=None,cat_oof_auc=None,analyzer=None,commit=p['commit'],plan_sha256=PLAN)
            if result:
                assert result['code_sha256']==p['code_sha256'][arm] and result['arm']==arm and result['seed']==seed
                row.update(valid=result['valid'],metric=result['metric'],seconds=result['seconds'])
                if result['public']:
                    pub=result['public'];row.update(blend_oof_auc=pub['blend_auc'],analyzer=pub['analyzer'],**{k+'_oof_auc':v for k,v in pub['model_aucs'].items()})
                if result['valid']:
                    predrows=rows(a/'submission.private.csv');pred={r['request_id']:float(r['requester_received_pizza']) for r in predrows}
                    assert set(pred)==set(truth) and len(pred)==len(predrows) and all(math.isfinite(v) for v in pred.values())
                    pos=[v for k,v in pred.items() if int(truth[k]['requester_received_pizza'])==1];neg=[v for k,v in pred.items() if int(truth[k]['requester_received_pizza'])==0]
                    value=math.fsum(1 if a>b else .5 if a==b else 0 for a in pos for b in neg)/(len(pos)*len(neg))
                    assert math.isclose(value,result['metric'],rel_tol=1e-11,abs_tol=1e-11)
                    binding=read(a/'binding.json');assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
                    assert pub['analyzer']==('char' if arm=='char' else 'word')
                    checks.append(dict(index=i,step=step,metric=value,result_sha256=sha(a/'result.json'),submission_sha256=sha(a/'submission.private.csv')))
            records.append(row)
    pairs=[]
    for seed in p['seeds']:
        group={r['arm']:r for r in records if r['seed']==seed};a,b=group['original'],group['char']
        pairs.append(dict(seed=seed,both_valid=a['valid'] and b['valid'],original=a['metric'],char=b['metric'],
            delta=b['metric']-a['metric'] if a['valid'] and b['valid'] else None,
            public_oof_delta=b['blend_oof_auc']-a['blend_oof_auc'] if a['blend_oof_auc'] is not None and b['blend_oof_auc'] is not None else None))
    delta=[r['delta'] for r in pairs if r['both_valid']]
    account=subprocess.check_output(['sacct','-X','-j',read(R/'launch.json')['job'],'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    out=R/'readout-v1';out.mkdir()
    for name,data in [('runs.csv',records),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(plan_sha256=PLAN,verifier_sha256=sha(Path(__file__)),verification_status='PASS',independently_scored=len(checks),
                 pairs=pairs,paired=len(delta),median_delta=statistics.median(delta) if delta else None,
                 sample_variance=statistics.variance(delta) if len(delta)>1 else None,all_assigned=4,rows=records,accounting=account,
                 files={name:sha(out/name) for name in ('runs.csv','pairs.csv')},checked_predictions=checks,
                 scope='human-specified one-keyword diagnostic; not autonomous improvement, not final generalization; independently recomputed development AUC')
    with (out/'summary.json').open('x') as f:json.dump(summary,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','checked_predictions')},sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['status','analyze']);x=a.parse_args()
    if x.mode=='status':print(json.dumps(status(),sort_keys=True))
    else:analyze()
