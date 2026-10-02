"""Independent receipt and complete-cost verification for public-state qualification."""
import csv, hashlib, json, statistics, subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/state-reuse-qualification-20261002-v1')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if not (R/'closed.json').exists():
        print(json.dumps(dict(status='RUNNING',completed_pairs=len(list(R.glob('episode-*/pair-*.json'))))))
        return
    if any(read(R/'closed.json')['returncodes']):
        print(json.dumps(dict(status='WORKER_FAILED',closed=read(R/'closed.json'))));return
    p=read(R/'plan.json')
    for f,h in p['files'].items():assert sha(R/f)==h
    assert sha(R/'plan.json')=='e9926dcf48ea6385f542142e070faa811ab528a644bfa29970aa4bf750740af3'
    rows=[];tasks=[];files={}
    for i in range(2):
        ep=R/f'episode-{i}';assert (ep/'completed.json').exists()
        task_rows=[]
        for trial in range(2):
            pair=read(ep/f'pair-{trial}.json');warm=ep/f'action-{trial*2}';cold=ep/f'action-{trial*2+1}'
            x=read(warm/'public-diagnostic.json');y=read(cold/'public-diagnostic.json')
            a=read(warm/'result.json');b=read(cold/'result.json')
            exact=x==y
            assert pair['exact_equal']==exact and a['seed']==b['seed']==p['seeds'][trial]
            assert a['task']==b['task']==pair['task']
            for path,r,payload in ((warm,a,x),(cold,b,y)):
                assert r['plan_sha256']==sha(R/'plan.json')
                assert r['query_sha256']==hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                assert r['total_seconds']>=r['initial_seconds']+r['query_seconds']+r['close_seconds']
                bind=read(path/'binding.json');assert bind['namespace']['exact_device_namespace']
                for f in ('result.json','public-diagnostic.json','binding.json'):files[str((path/f).relative_to(R))]=sha(path/f)
            row=dict(task=a['task'],seed=a['seed'],exact_equal=exact,
                warm_query_seconds=a['query_seconds'],cold_query_with_rebuild_seconds=b['total_seconds'],
                marginal_speed_ratio=b['total_seconds']/a['query_seconds'],
                full_reuse_seconds=a['total_seconds'],
                full_discard_then_query_seconds=a['initial_seconds']+a['close_seconds']+b['total_seconds'],
                source_initial_seconds=a['initial_seconds'],commit=p['commit'],plan_sha256=sha(R/'plan.json'))
            row['full_workflow_speed_ratio']=row['full_discard_then_query_seconds']/row['full_reuse_seconds']
            rows.append(row);task_rows.append(row)
        tasks.append(dict(task=task_rows[0]['task'],pairs=2,exact_equal=sum(r['exact_equal'] for r in task_rows),
            marginal_ratio_median=statistics.median(r['marginal_speed_ratio'] for r in task_rows),
            marginal_ratio_sample_variance=statistics.variance(r['marginal_speed_ratio'] for r in task_rows),
            full_ratio_median=statistics.median(r['full_workflow_speed_ratio'] for r in task_rows),
            full_ratio_sample_variance=statistics.variance(r['full_workflow_speed_ratio'] for r in task_rows)))
    gate=all(r['exact_equal'] for r in rows) and all(t['marginal_ratio_median']>2 for t in tasks)
    result=dict(status='VERIFIED',gate=gate,plan_sha256=sha(R/'plan.json'),source_sha256=sha(Path(__file__)),
        rows=rows,tasks=tasks,files=files,hidden_scores_read=False,
        limitations='cold follows warm; no feedback-caused improvement claim; full discard workflow is sum of measured phases, not separately executed third trajectory')
    with (R/'verification.json').open('x') as f:json.dump(result,f,indent=2)
    with (R/'pairs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','rows')},sort_keys=True))
if __name__=='__main__':main()
