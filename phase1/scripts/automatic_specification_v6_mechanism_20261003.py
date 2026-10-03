"""Closed-all mechanism inspection without exposing numerical outcomes.

Rubric is frozen after launch but before inspecting model responses or effects.
It does not alter the numerical gate or automate semantic judgments.
"""
import argparse, ast, datetime, hashlib, json, re, subprocess, os
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6')
PLAN='71340fc4a5fb97f09fa1dc31b5189500bffef3e73b68382a6bff9b628b61e154'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=p.read_bytes();assert not SECRET.search(raw),'credential shape: no content printed'
    return json.loads(raw)

def freeze():
    assert sha(R/'plan.json')==PLAN and not (R/'readout-v1').exists()
    x=dict(plan_sha256=PLAN,script_sha256=sha(Path(__file__)),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        timing='Post-launch, before inspection of model responses or numerical effects. Does not change original numerical gate.',
        units='All assigned roots and comparisons, including failures and unstarted positions.',
        rubric={
            'grounding':'Does the initial plan correctly reference actual existing components/variables and observations? Do not equate asserted causality with evidence.',
            'implementation':'Compare stated change with executed code; label implemented/partial/not implemented/unknown. Execution success alone is not implementation proof.',
            'preservation':'Explicitly list non-target alterations, unnecessary retraining, or incompatible interfaces; missing evidence is unknown.',
            'known_rules':'Check objective/metric alignment, supported early stopping, public CV member/blend selection, train-fitted preprocessing, standard text views/regularized models. Beyond this checklist is not proof of novelty.',
            'attribution':'A multi-change patch does not identify a single causal mechanism. Distinct generation seeds producing identical predictions are not independent training replication.',
            'benefit':'Only the frozen numerical readout can establish retained-score differences; code inspection never substitutes for it.'},
        procedure='Inspect all completed traces before reading aggregate effect numbers where possible. Analyst sees arm and execution events; no claim of independent blinded reviewer.')
    with (R/'mechanism-freeze.json').open('x') as f:json.dump(x,f,sort_keys=True,indent=2)
    print(json.dumps(dict(status='MECHANISM_RUBRIC_FROZEN',sha256=sha(R/'mechanism-freeze.json'))))

def inspect(index,step,brief):
    assert sha(R/'plan.json')==PLAN and read(R/'mechanism-freeze.json')['script_sha256']==sha(Path(__file__))
    assert read(R/'closed.json')['service_closed']
    job=read(R/'launch.json')['job']
    state=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    fields=next(r.split('|') for r in state.splitlines() if r.split('|')[0]==job)
    assert fields[1] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT')
    for s in read(R/'plan.json')['schedule']:
        if index is not None and s['index']!=index:continue
        ep=R/f'episode-{s["index"]}'
        print(json.dumps(dict(index=s['index'],role=s['role'],task=s['task'],arm=s['arm'],seed=s['seed'],launched=(ep/'native.json').exists(),closed=(ep/'closed.json').exists())))
        for k in range(5):
            if step is not None and k!=step:continue
            a=ep/f'action-{k}';gf=a/'generation.private.json';nf=a/'node.private.json'
            if not gf.exists() and not nf.exists():continue
            g=read(gf) if gf.exists() else {};node=read(nf) if nf.exists() else {}
            raw=g.get('response','');codes=re.findall(r'```python\s*\n(.*?)```',raw,re.S)
            if k==0 and 'code' in node:codes=[node['code']]
            result=read(a/'result.json') if (a/'result.json').exists() else {}
            fmt=read(a/'format.json') if (a/'format.json').exists() else {}
            item=dict(index=s['index'],step=k,format_status=fmt.get('status'),mode=fmt.get('mode'),returned=bool(result),execution_success=result.get('execution_success'),
                rationale=raw.split('```',1)[0][:1800] if brief else raw.split('```',1)[0],response_sha256=hashlib.sha256(raw.encode()).hexdigest(),code_blocks=len(codes))
            if step is not None:item['codes']=codes
            elif not brief:
                item['signatures']=[]
                for code in codes:
                    try:t=ast.parse(code)
                    except SyntaxError:item['signatures'].append(dict(parse='FAIL'));continue
                    item['signatures'].append(dict(lines=len(code.splitlines()),calls=sorted({ast.unparse(n.func) for n in ast.walk(t) if isinstance(n,ast.Call)}),assignments=[ast.unparse(n)[:700] for n in ast.walk(t) if isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign))]))
            print(json.dumps(item))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','inspect']);a.add_argument('--index',type=int);a.add_argument('--step',type=int);a.add_argument('--brief',action='store_true');q=a.parse_args()
    if q.mode=='freeze':freeze()
    else:inspect(q.index,q.step,q.brief)
