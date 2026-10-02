"""Descriptive all-assigned accounting; no new scoring or changed decision gate."""
import argparse,csv,hashlib,json,re,statistics
from pathlib import Path
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def main(root):
    s=read(root/'summary.json');v=read(root/'verification.json')
    assert v['status']=='PASS' and v['summary_sha256']==sha(root/'summary.json')
    for n,h in s['files'].items():assert sha(root/n)==h
    runs=rows(root/'runs.csv');a=rows(root/'actions.csv')
    initial={r['index']:float(r['initial']) for r in runs}
    new=[r for r in a if r['step']!='0'];valid=[r for r in new if r['valid']=='True']
    check=[r for r in new if r['kind']=='CHECK' and r['execution_success']=='True']
    groups={}
    for arm in 'ABCD':
        rr=[r for r in runs if r['arm']==arm];aa=[r for r in new if r['arm']==arm]
        gains=[float(r['gain']) for r in rr]
        groups[arm]=dict(runs=len(rr),gain_median=statistics.median(gains),gain_sample_variance=statistics.variance(gains),
            generated=sum(r['generated']=='True' for r in aa),format_rejects=sum(r['format_status']=='REJECT' for r in aa),
            valid_new=sum(r['valid']=='True' for r in aa),successful_checks=sum(r['execution_success']=='True' and r['kind']=='CHECK' for r in aa),
            unreturned_executions=sum(r['started']=='True' and r['returned']!='True' for r in aa),
            replay_failed=sum(r['replay_attempted']=='True' and r['replay_success']=='False' for r in aa))
    diffs=[dict(index=int(r['index']),arm=r['arm'],seed=int(r['seed']),step=int(r['step']),metric=float(r['metric']),
        delta=float(r['metric'])-initial[r['index']]) for r in valid]
    acct=s['accounting'].split('|');assert acct[1]=='COMPLETED'
    gpu_hours=int(acct[2])*int(re.search(r'gres/gpu=(\d+)',acct[3]).group(1))/3600
    counts=dict(trajectories=len(runs),new_valid=len(valid),new_improved=sum(r['delta']>1e-12 for r in diffs),
        new_tied=sum(abs(r['delta'])<=1e-12 for r in diffs),new_worse=sum(r['delta']< -1e-12 for r in diffs),
        generated=sum(r['generated']=='True' for r in new),format_rejects=sum(r['format_status']=='REJECT' for r in new),
        budget_exhausted=sum(r['budget_exhausted']=='True' for r in runs),successful_checks=len(check))
    out=dict(status='PASS',summary_sha256=sha(root/'summary.json'),producer_sha256=sha(Path(__file__)),
        counts=counts,arms=groups,candidate_deltas=diffs,gpu_hours=gpu_hours,
        successful_check_wall_seconds=[float(r['execution_wall_seconds']) for r in check],
        decision='Do not expand this recipe; retain ordinary persistence as infrastructure, not a method claim.',
        limitations='Two combined run seeds, one historical start/task, reused development set, unequal successful action exposure; all assigned retained. Counts and code alignment do not establish feedback causality. No statistical equivalence claim.')
    with (root/'census.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root',type=Path);main(a.parse_args().root)
