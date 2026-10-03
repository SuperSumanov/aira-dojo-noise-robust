"""Reuse pinned readout implementations with a frozen V6 context.

No effect computation occurs until closure. The only verifier adaptation is
the distinct, execution-only root instruction; comparison checks are unchanged.
"""
import argparse,ast,hashlib,importlib.util,json,sys,datetime
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v6')
B=R.parent
TEMPLATES={
 'readout':('automatic_specification_gpu3_v4_readout_20261003.py','b5fab43ac9e0d34b53f874756494d4dd79ee80fcb9676ba30eeeff39394b1c26'),
 'verifier':('automatic_specification_gpu3_v4_verify_20261003.py','05dc76ddf2e694fd8cd48e51120c208467a014d2888c1835c5174136185d6449'),
 'sensitivity':('automatic_specification_gpu3_v4_sensitivity_20261003.py','72939993d0220c51220339e53eefb038bfe2511f17fde773b198161c6e083729')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,obj):
    with p.open('x') as f:json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False)
def load(name,plan):
    p=R/'analysis_templates'/f'{name}.py';spec=importlib.util.spec_from_file_location('v6_'+name,p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.R=R;module.PLAN=plan
    return module
def freeze(plan):
    assert plan and sha(R/'plan.json')==plan and not (R/'analysis-freeze.json').exists()
    assert not (R/'launch.json').exists() and not (R/'readout-v1').exists()
    target=R/'analysis_templates';target.mkdir();files={}
    for role,(name,h) in TEMPLATES.items():
        p=B/name;assert sha(p)==h;content=p.read_text()
        if role=='verifier':
            old="and x.COMMON in q['prompt']";assert content.count(old)==1
            content=content.replace(old,"and (x.ROOT_COMMON if s['role']=='root' else x.COMMON) in q['prompt']")
            for arm in 'BC':
                old=f"if s['role']=='comparison' and s['arm']=='{arm}':";assert content.count(old)==1
                content=content.replace(old,f"if s['role']=='comparison' and step==1 and s['arm']=='{arm}':")
            old="                for n,r in previous:";assert content.count(old)==1
            content=content.replace(old,"                if s['role']=='comparison':\n                    assert f'CURRENT MODEL CALL: {step} of 4.' in q['prompt']\n                    assert ('On call 1, use PLAN only.' in q['prompt'])==(s['arm'] in 'BC' and step==1)\n                for n,r in previous:")
        ast.parse(content)
        dest=target/f'{role}.py'
        with dest.open('x') as f:f.write(content)
        files[role]=sha(dest)
    for role in TEMPLATES:load(role,plan).freeze()
    receipt=dict(plan_sha256=plan,script_sha256=sha(Path(__file__)),templates=TEMPLATES,files=files,
        utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),adaptation='Context R/PLAN rebound to fixed V6 cohort; verifier checks execution-only root prompt. Also verifies current-call marker and first-call instruction removal after step1. Scientific endpoints and numerical gate unchanged.')
    write(R/'analysis-freeze.json',receipt);print(json.dumps(dict(status='ALL_ANALYSIS_FROZEN',plan_sha256=plan,receipt_sha256=sha(R/'analysis-freeze.json'))))
def main():
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','status','analyze','verify','sensitivity']);a.add_argument('--plan-sha');q=a.parse_args()
    if q.mode=='freeze':return freeze(q.plan_sha)
    f=read(R/'analysis-freeze.json');plan=f['plan_sha256'];assert sha(R/'plan.json')==plan and sha(Path(__file__))==f['script_sha256']
    for name,h in f['files'].items():assert sha(R/'analysis_templates'/f'{name}.py')==h
    role='verifier' if q.mode=='verify' else 'sensitivity' if q.mode=='sensitivity' else 'readout'
    module=load(role,plan);getattr(module,'analyze' if q.mode=='sensitivity' else q.mode)()
if __name__=='__main__':main()
