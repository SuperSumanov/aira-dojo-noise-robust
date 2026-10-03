"""Frozen transformations of tested CPU/readout/verifier code; no hidden outcomes.

prepare writes only NEW experiment-owned templates. No old experiment is run.
"""
import argparse, ast, hashlib, importlib.util, json, os, subprocess, sys
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');P=B/'opportunity-information-20261003-v2';R=B/'executable-evidence-20261004-v1'
PY=B/'venvs/aira/bin/python'
TEMPLATES={
 'cpu':('opportunity_information_cpu_20261003.py','4e270eee98dad9cd339f4e396aefdab2bc17dfa37006123f829e6b9a8304f89b'),
 'readout':('opportunity_information_readout_20261003.py','73959a378739d913bf80b32c401b52b133555cee5c43a22f94df72605595c75e'),
 'verifier':('opportunity_information_verify_20261003.py','6c110ac0fbcaadc130a6d96e13a526cbfad3bfd14dcfb100823918381fa49f77')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,o):
    with p.open('x') as f:json.dump(o,f,sort_keys=True,indent=2,allow_nan=False)
def replace(text,a,b,count=1):
    assert text.count(a)==count,(a,text.count(a),count);return text.replace(a,b)
def module(role):
    p=R/'analysis_templates'/f'{role}.py';s=importlib.util.spec_from_file_location('evidence_'+role,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

GATE='''def gate_from_rows(pairs,runs):
    tasks=sorted({r['task'] for r in runs})
    if len(tasks)!=2:return False
    for task in tasks:
        p=[p for p in pairs if p['task']==task]
        if len(p)!=3 or not all(x['comparable'] for x in p):return False
        if statistics.median(x['B_minus_A'] for x in p)<.002:return False
        if statistics.median(-x['C_minus_B'] for x in p)<.002:return False
        if any(x['B_minus_A']< -1e-12 or x['C_minus_B']>1e-12 for x in p):return False
        if not any(r['arm']=='B' and r['task']==task and (r['improved_candidates'] or 0)>0 for r in runs):return False
    return True
'''

def prepare():
    assert not (R/'launch.json').exists();plan=sha(R/'plan.json');target=R/'analysis_templates';target.mkdir()
    records={}
    for role,(name,h) in TEMPLATES.items():
        p=P/name;assert sha(p)==h;text=p.read_text()
        text=replace(text,str(P),str(R))
        if role=='cpu':
            text=replace(text,'c.solver.time_limit_secs==600 and c.solver.step_limit==5','c.solver.time_limit_secs==720 and c.solver.step_limit==7')
            text=replace(text,'==19453','==19461')
            text=replace(text,'len(prompts)==4','len(prompts)==6')
            text=replace(text,"assert all((x.FACTS[task_index] in p)==(arm=='B') and (x.SPECS[task_index] in p)==(arm=='C') for p in prompts)","assert all(x.note(s,i+1) in p and f'CURRENT MODEL CALL: {i+1} of 6.' in p for i,p in enumerate(prompts))")
        else:
            text=replace(text,"6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f",plan)
            text=replace(text,'range(5)','range(7)')
            text=replace(text,"r['elapsed_seconds']<=600","r['elapsed_seconds']<=720")
        if role=='readout':
            text=replace(text,'run_seconds=600,max_calls=4','run_seconds=720,max_calls=6')
            text=replace(text,"account['gpu_hours']<=6","account['gpu_hours']<=10")
            text=replace(text,"i in (0,1) for a,g", "i in (0,1,2) for a,g")
            text=replace(text,"('C',.2)","('C',.05)")
            old="gate=len(bs)==2 and all(x['paired']==2 and x['median']>0 and x['negative']==0 and any(r['arm']=='B' and r['task']==x['task'] and (r['improved_candidates'] or 0)>0 for r in runs) for x in bs)"
            text=replace(text,old,'gate=gate_from_rows(pairs,runs)')
            text=replace(text,'def compare(runs):',GATE+'\ndef compare(runs):')
            # Avoid fixtures that only test the already failed missingness branch.
            marker="    rr[1]['initial']=None;assert not compare(rr)[2]"
            extra="""    import copy
    for change in ('tie_reference','too_small','one_negative','different_initial'):
        bad=copy.deepcopy(rr)
        if change=='tie_reference':
            for r in bad:
                if r['arm']=='C':r['gain']=.1
        elif change=='too_small':
            for r in bad:
                if r['arm']=='B':r['gain']=.001
        elif change=='one_negative':bad[1]['gain']=-.01
        else:bad[1]['initial_sha256']='different'
        assert not compare(bad)[2],change
    rr[1]['initial']=None;assert not compare(rr)[2]"""
            text=replace(text,marker,extra).replace('fixtures=2','fixtures=6')
        if role=='verifier':
            text=replace(text,"assert (x.FACTS[s['start']] in q['prompt'])==(s['arm']=='B') and (x.SPECS[s['start']] in q['prompt'])==(s['arm']=='C')","assert x.COMMON in q['prompt'] and x.note(s,step) in q['prompt'] and f'CURRENT MODEL CALL: {step} of 6.' in q['prompt']")
            text=replace(text,"calls<=4","calls<=6")
            text=replace(text,"mode==r['kind']","mode==r['kind']\n                if step==1 and s['arm'] in 'BC':assert mode=='CHECK'")
            old="gate=(R/'all-closed.json').exists() and all(t['paired']==2 and t['median']>0 and t['negative']==0 and any(r['arm']=='B' and r['task']==t['task'] and (r['improved'] or 0)>0 for r in actual) for t in stats if t['contrast']=='B_minus_A')"
            new="""gate=(R/'all-closed.json').exists()
    for task_name in sorted({a['task'] for a in actual}):
        ps=[p for p in pairs if p['task']==task_name]
        if len(ps)!=3 or not all(p['comparable'] for p in ps):gate=False;continue
        a_deltas=[p['B_minus_A'] for p in ps];c_deltas=[-p['C_minus_B'] for p in ps]
        gate=gate and sorted(a_deltas)[1]>=.002 and sorted(c_deltas)[1]>=.002 and min(a_deltas)>=-1e-12 and min(c_deltas)>=-1e-12
        gate=gate and any(a['task']==task_name and a['arm']=='B' and (a['improved'] or 0)>0 for a in actual)"""
            text=replace(text,old,new)
        ast.parse(text);dest=target/f'{role}.py'
        with dest.open('x') as f:f.write(text)
        records[role]=sha(dest)
    module('readout').freeze()
    rubric=dict(scope='All18 assigned trajectories, all actions; no outcome selection.',criteria=[
        'B names a consequential premise AND specifies what contrasting observations would imply.',
        'CHECK actually executes a test of that premise; generic summaries/planned changes alone do not pass.',
        'Returned evidence distinguishes premise supported/contradicted/unresolved; thrown exception is not contradiction.',
        'Later actual code implements an evidence-linked modification, not only self-report; unrelated changes separately coded.',
        'Quality must exceed A and C under frozen full-cost gate; standard checklist repairs remain standard repairs.',
        'Do not condition denominator on first check adherence, valid new candidate or model-generated positive wording.'
        ],review_boundary='Analyst sees arms and qualitative terminals; no claim of independent blinded semantic coding. Numerical values withheld until closure. No novelty claim from success alone.')
    write(R/'mechanism-freeze.json',rubric)
    write(R/'analysis-freeze.json',dict(plan_sha256=plan,files=records,templates=TEMPLATES,script_sha256=sha(Path(__file__)),mechanism_sha256=sha(R/'mechanism-freeze.json')))
    print(json.dumps(dict(status='ANALYSIS_FROZEN',plan_sha256=plan,templates=records)))

def check():
    f=read(R/'analysis-freeze.json');assert f['plan_sha256']==sha(R/'plan.json') and f['script_sha256']==sha(Path(__file__))
    for role,h in f['files'].items():assert sha(R/'analysis_templates'/f'{role}.py')==h
    return f

def main():
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','cpu','launch','status','analyze','verify']);q=a.parse_args()
    if q.mode=='prepare':return prepare()
    check()
    if q.mode=='cpu':
        subprocess.run([str(PY),'-B',str(R/'analysis_templates/cpu.py')],check=True)
    elif q.mode=='launch':
        c=read(R/'transport-loop-cpu.json');assert c['status']=='PASS' and c['plan_sha256']==sha(R/'plan.json') and c['script_sha256']==sha(R/'analysis_templates/cpu.py')
        assert not (R/'launch.json').exists() and not (R/'submit-intent.json').exists()
        write(R/'budget-approval.json',dict(approved=True,plan_sha256=sha(R/'plan.json'),gpu_hours_cap=10,basis='User 2026-10-04 HKT renewed broad scoped approval to continue experiments for a complete four-hour window. Before implementation assistant previewed18 trajectories, six calls/720sec each, four3090 up to150min, no paid API/base training. One batch only.'))
        subprocess.run([str(PY),'-B',str(R/'task_feedback_real_20261001.py'),'submit'],check=True)
    elif q.mode=='verify':module('verifier').main()
    else:getattr(module('readout'),q.mode)()
if __name__=='__main__':main()
