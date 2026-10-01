"""Read-only independent re-scoring of this development pilot's returned actions."""
from __future__ import annotations
import argparse,hashlib,json,math,sys
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/task-feedback-upper-20261002-v1')
PLAN_SHA='9fe231e1b9e2da8cb51fadb7ff9844b074c10e8e3dc64d1d1f3be170fb0703a0'
METRICS={'spooky-author-identification':'log_loss','random-acts-of-pizza':'auc','tweet-sentiment-extraction':'mean_word_jaccard'}

def read(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def equal(a,b):return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-11)

def verify(root=ROOT):
    if root!=ROOT or digest(root/'plan.json')!=PLAN_SHA:raise ValueError('pilot/plan scope')
    sys.path.insert(0,str(root))
    from task_feedback_real_20261001 import m as engine
    plan=engine.check();engine.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from task_feedback_facts_20261001 import diagnostics,compare_to_parent
    legacy_path=engine.B/'task-feedback-real-20261001-v6/task_feedback_facts_20261001.py'
    assert digest(legacy_path)=='b44bc3badff713fe8e595fea6b8d2d6fc9e7c453e1e412ece7b833f4af0c908b'
    legacy=engine.load('upper_independent_metrics',legacy_path)
    job=read(root/'launch.json')['job'];service=read(root/'service-native.json')
    assert service['job']==job
    checked=[];pending=[]
    for s in plan['schedule']:
        ep=root/f'episode-{s["index"]}'
        if not (ep/'native.json').exists():pending.append(s['index']);continue
        if not (ep/'closed.json').exists():pending.append(s['index'])
        native=read(ep/'native.json')
        assert native['job']==job and len(native['gpu_uuids'])==1
        assert not set(native['gpu_uuids'])&set(service['gpu_uuids'])
        assert native['config_sha256']==digest(root/'configs'/f'{s["index"]}.json')
        cfg=RunConfig.load_from_json(root/'configs'/f'{s["index"]}.json')
        task=MLEBenchTask(cfg.task);values=[];parents={}
        for step in range(5):
            d=ep/f'action-{step}';result=d/'result.json'
            if not result.exists():continue
            # result precedes node receipt by one atomic write; skip active boundary.
            if not (d/'node.private.json').exists():pending.append(s['index']);continue
            before=digest(result);r=read(result);node=read(d/'node.private.json');start=read(d/'started.json')
            code_sha=hashlib.sha256(node['code'].encode()).hexdigest()
            assert code_sha==r['code_sha256']==start['code_sha256']
            assert r['step']==step and 0<=r['elapsed_seconds']<=plan['run_seconds']
            if step==0:assert code_sha==plan['starts'][s['start']]['code_sha256']
            binding=d/'binding.json'
            if r['execution_started']:
                b=read(binding)
                assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace']
            if r['valid']:
                assert r['execution_started'] and r['exit_code']==0 and not r['timed_out']
                sub=d/'submission.private.csv';sub_sha=digest(sub)
                receipt=task._search_only_score(s['task'],sub)
                assert receipt['split']=='D_search_development_only'
                assert equal(receipt[METRICS[s['task']]],r['metric'])
                spec=task._search_only_module.SPEC[s['task']]
                labels=engine.B/spec.get('source',spec.get('view'))/'private/dsearch.csv'
                legacy.diagnostics(s['task'],task.public_dir,labels,sub,receipt)  # independent metric implementation, never fed to agents
                independent=diagnostics(s['task'],task.public_dir,labels,sub,receipt)
                if s['arm']!='A':
                    assert independent==r['facts']
                else:assert r['facts'] is None
                assert digest(sub)==sub_sha
                values.append(r['metric'])
            parents[code_sha]=r['facts']
            best=(min if s['task']=='spooky-author-identification' else max)(values) if values else None
            assert best==r['selected_metric']
            assert digest(result)==before
            checked.append({'index':s['index'],'task':s['task'],'arm':s['arm'],'step':step,
                            'valid':r['valid'],'result_sha256':before,'code_sha256':code_sha,
                            'submission_sha256':digest(d/'submission.private.csv') if r['valid'] else None,
                            'native_score_recomputed':bool(r['valid']),
                            'independent_aggregate_recomputed':bool(r['valid'])})
        if (ep/'completed.json').exists():
            assert read(ep/'completed.json')['selected_metric']==((min if s['task']=='spooky-author-identification' else max)(values) if values else None)
    return {'status':'PASS_OBSERVED_ACTIONS','plan_sha256':PLAN_SHA,'job':job,
            'observed_actions':len(checked),'valid_actions_recomputed':sum(x['valid'] for x in checked),
            'pending_episode_indices':sorted(set(pending)),'records':checked,
            'scope':'D_search development only; no D_val/test or protected cohorts; no rerun or selection changes'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=verify()
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},sort_keys=True))
