"""Four-row fixed implementation control; native and independent score checks.

This is not a new agent arm and the program may reset its own training seed.
Reads only this registered unprotected D_search development experiment.
"""
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/task-feedback-pizza-control-20261002-v1')
PLAN_SHA='d384e0db9e14bfe0a2b48a4d47f4b98169e86ac3d7ed00be5733ad2ef429eb37'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def collect():
    assert sha(ROOT/'plan.json')==PLAN_SHA
    assert (ROOT/'all-closed.json').is_file(), 'Wait for all four attempts; no early scores'
    assert read(ROOT/'all-closed.json')['generator_calls']==0
    sys.path.insert(0,str(ROOT))
    from task_feedback_pizza_control_20261002 import m
    plan=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    legacy_path=m.B/'task-feedback-real-20261001-v6/task_feedback_facts_20261001.py'
    assert sha(legacy_path)=='b44bc3badff713fe8e595fea6b8d2d6fc9e7c453e1e412ece7b833f4af0c908b'
    legacy=m.load('pizza_control_independent_metric',legacy_path)
    job=read(ROOT/'launch.json')['job'];rows=[]
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}';d=ep/'action-0';closed=read(ep/'closed.json')
        assert not list(ep.glob('action-*/generation.private.json'))
        assert not list(ep.glob('action-*/feedback.json'))
        returned=list(ep.glob('action-*/result.json'))
        assert all(p==d/'result.json' for p in returned)
        native=read(ep/'native.json')
        assert native['job']==job and len(native['gpu_uuids'])==1
        assert native['config_sha256']==sha(ROOT/'configs'/f'{s["index"]}.json')
        row={**s,'job':job,'commit':plan['base_commit'],'plan_sha256':PLAN_SHA,
             'budget_seconds':600,'generator_calls':0,'returned':bool(returned),
             'valid':False,'metric':None,'elapsed_seconds':None,
             'code_sha256':None,'submission_sha256':None,'independently_verified':False,
             'worker_deadline_reached':closed['worker_deadline_reached']}
        if returned:
            r=read(d/'result.json');node=read(d/'node.private.json')
            assert r['step']==0 and 0<=r['elapsed_seconds']<=600
            assert hashlib.sha256(node['code'].encode()).hexdigest()==r['code_sha256']
            assert node['code']==read(ROOT/'starts'/f'{s["start"]}.private.json')['code']
            row.update(valid=r['valid'],elapsed_seconds=r['elapsed_seconds'],code_sha256=r['code_sha256'])
            if r['execution_started']:
                binding=read(d/'binding.json')
                assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
            if r['valid']:
                assert r['execution_started'] and not r['timed_out'] and r['exit_code']==0
                assert r['metric'] is not None and math.isfinite(r['metric'])
                cfg=RunConfig.load_from_json(ROOT/'configs'/f'{s["index"]}.json');task=MLEBenchTask(cfg.task)
                sub=d/'submission.private.csv';h=sha(sub);receipt=task._search_only_score(s['task'],sub)
                assert receipt['split']=='D_search_development_only'
                assert math.isclose(receipt['auc'],r['metric'],rel_tol=1e-11,abs_tol=1e-11)
                spec=task._search_only_module.SPEC[s['task']]
                labels=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
                legacy.diagnostics(s['task'],task.public_dir,labels,sub,receipt)
                assert sha(sub)==h
                row.update(metric=r['metric'],submission_sha256=h,independently_verified=True)
        rows.append(row)
    assert len(rows)==4
    pairs=[]
    for seed in sorted({r['seed'] for r in rows}):
        q={r['variant']:r for r in rows if r['seed']==seed};o,f=q['original'],q['fixed']
        pairs.append({'seed':seed,'original':o['metric'],'fixed':f['metric'],
                      'fixed_minus_original':f['metric']-o['metric'] if f['valid'] and o['valid'] else None,
                      'validity_difference':int(f['valid'])-int(o['valid'])})
    delta=[p['fixed_minus_original'] for p in pairs if p['fixed_minus_original'] is not None]
    return {'status':'PASS_COMPLETE_FOUR_ROW_CONTROL','job':job,'plan_sha256':PLAN_SHA,
            'rows':rows,'pairs':pairs,'complete_denominator':4,'valid':sum(r['valid'] for r in rows),
            'median_paired_delta':statistics.median(delta) if delta else None,
            'sample_variance_paired_delta':statistics.variance(delta) if len(delta)>1 else None,
            'scope':'one code incumbent, two execution repeats; explicit program reseeding retained; not independent training seeds, agent treatment, E2E or final test'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=collect();a.out.mkdir(mode=0o700,exist_ok=False)
    for name,rows in [('runs.csv',result['rows']),('pairs.csv',result['pairs'])]:
        with (a.out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (a.out/'summary.json').write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','pairs')},sort_keys=True))
