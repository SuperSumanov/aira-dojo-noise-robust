"""Read-only initial-state comparability, scoped to the new development pilot."""
import hashlib,json
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/task-feedback-real-20261001-v6')
def read(p):return json.loads(p.read_bytes())
assert hashlib.sha256((R/'plan.json').read_bytes()).hexdigest()=='15751d3b52bdc42617df02006ce724635f4bf49df6e477686769fd1979d53403'
plan=read(R/'plan.json');rows=[]
for start in range(6):
    group={}
    for s in plan['schedule']:
        if s['start']!=start:continue
        p=R/f'episode-{s["index"]}/action-0/result.json'
        if not p.exists():continue
        r=read(p);f=p.parent.parent/'action-1/feedback.json'
        group[s['arm']]={'index':s['index'],'valid':r['valid'],'metric':r['metric'] if r['valid'] else None,'raw_code_sha':r['code_sha256'],'executed_sha':r.get('executed_code_sha256'),'facts_sha':read(f)['facts_sha256'] if f.exists() else None}
    for high,low in [('C','B'),('B','A'),('C','A')]:
        if high not in group or low not in group:continue
        h,l=group[high],group[low]
        rows.append({'start':start,'contrast':high+'-'+low,'both_initial_valid':h['valid'] and l['valid'],'initial_validity_equal':h['valid']==l['valid'],'initial_score_equal':h['metric']==l['metric'] if h['valid'] and l['valid'] else None,'raw_code_equal':h['raw_code_sha']==l['raw_code_sha'],'executed_code_equal':h['executed_sha']==l['executed_sha'] if h['executed_sha'] and l['executed_sha'] else None,'first_feedback_facts_equal':h['facts_sha']==l['facts_sha'] if high=='C' and low=='B' and h['facts_sha'] and l['facts_sha'] else None})
print(json.dumps({'comparisons':rows,'scope':'Only first-action state; never implies identical subsequent trajectories or final gains.'},sort_keys=True))
