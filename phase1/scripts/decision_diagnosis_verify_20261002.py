"""Independent score algebra, retained incumbent, request chronology, GPU scope."""
import csv, hashlib, json, math, sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
PLAN='939f9470529ad6c14f5b6670bb1bec4cd99398026f6fbdbea662c8d29e32c48e'
def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def main():
    assert sha(R/'plan.json')==PLAN
    assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    sys.path.insert(0,str(R)); from task_feedback_real_20261001 import m
    p=m.check(); m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    summary=read(R/'readout-v1/summary.json'); assert summary['plan_sha256']==PLAN
    for name,h in summary['files'].items(): assert sha(R/'readout-v1'/name)==h
    sr={r['index']:r for r in summary['rows']}; checked=[]; request_checks=[]
    job=read(R/'launch.json')['job']; service=read(R/'service-native.json')
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}'; assert (ep/'closed.json').exists()
        native=read(ep/'native.json'); assert native['job']==job==service['job']
        assert len(native['gpu_uuids'])==1 and not set(native['gpu_uuids'])&set(service['gpu_uuids'])
        cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json')
        assert native['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
        task=MLEBenchTask(cfg.task); spec=task._search_only_module.SPEC[s['task']]
        labels=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
        key='request_id' if s['task']=='random-acts-of-pizza' else 'id'
        truth={r[key]:r for r in labels}; assert len(truth)==len(labels)
        values=[]; initial=None
        for step in range(3):
            a=ep/f'action-{step}'; path=a/'result.json'
            if not path.exists(): continue
            r=read(path); node=read(a/'node.private.json'); start=read(a/'started.json')
            assert sha(path) and hashlib.sha256(node['code'].encode()).hexdigest()==r['code_sha256']==start['code_sha256']
            assert r['step']==step and r['elapsed_seconds']<=900
            if step==0: assert r['code_sha256']==p['starts'][s['start']]['code_sha256']
            binding=read(a/'binding.json')
            assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
            if r['kind']=='CHECK': assert r['metric'] is None and not r['valid']
            if r['valid']:
                assert r['exit_code']==0 and not r['timed_out']
                predrows=rows(a/'submission.private.csv'); pred={row[key]:row for row in predrows}
                assert len(pred)==len(predrows)==len(truth) and set(pred)==set(truth)
                if key=='request_id':
                    pos=[float(pred[k]['requester_received_pizza']) for k,v in truth.items() if int(v['requester_received_pizza'])==1]
                    neg=[float(pred[k]['requester_received_pizza']) for k,v in truth.items() if int(v['requester_received_pizza'])==0]
                    metric=math.fsum(1 if a>b else .5 if a==b else 0 for a in pos for b in neg)/(len(pos)*len(neg))
                else:
                    metric=-math.fsum(math.log(max(float(pred[k][v['author']]),1e-15)) for k,v in truth.items())/len(truth)
                assert math.isclose(metric,r['metric'],rel_tol=1e-11,abs_tol=1e-11)
                values.append(metric)
                if step==0: initial=metric
            best=(min if key=='id' else max)(values) if values else None
            assert best is None and r['selected_metric'] is None or best is not None and math.isclose(best,r['selected_metric'],abs_tol=1e-11)
            checked.append(dict(index=s['index'],step=step,kind=r['kind'],valid=r['valid'],result_sha256=sha(path)))
        best=(min if key=='id' else max)(values) if values else None
        assert best is None and sr[s['index']]['selected'] is None or best is not None and math.isclose(best,sr[s['index']]['selected'],abs_tol=1e-11)
        if (ep/'action-1/result.json').exists() and (ep/'action-2/request.private.json').exists():
            first=read(ep/'action-1/node.private.json'); r1=read(ep/'action-1/result.json')
            req=read(ep/'action-2/request.private.json')['prompt']
            assert first['terminal'][-12000:] in req and first['plan'] in req
            assert f"Exit={r1['exit_code']}; timed_out={r1['timed_out']}" in req
            request_checks.append(dict(index=s['index'],actual_output_in_next_prompt=True,
                previous_result_sha256=sha(ep/'action-1/result.json'),request_sha256=sha(ep/'action-2/request.private.json')))
    out=dict(status='PASS',plan_sha256=PLAN,summary_sha256=sha(R/'readout-v1/summary.json'),
        source_sha256=sha(Path(__file__)),verified_actions=checked,request_chronology=request_checks,
        valid_scored=sum(r['valid'] for r in checked),
        scope='Independent per-positive-negative AUC / per-row log loss; same approved D_search labels. GPU namespace and source/result hashes, saved-incumbent replay. Mechanism/novelty NOT certified.')
    with (R/'readout-v1/verification.json').open('x') as f: json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k not in ('verified_actions','request_chronology')},sort_keys=True))
if __name__=='__main__':main()
