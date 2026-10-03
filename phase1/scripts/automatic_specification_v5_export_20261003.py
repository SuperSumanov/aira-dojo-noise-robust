"""Export verified aggregate V5 artifacts; never raw workspace/model content."""
import hashlib,json,re
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu3-v5')
D=R.parent/'automatic-specification-export-20261003-v5'
PLAN='e533639434bc1c1cca57a301127a63eff56452119dfe78ccd332199e9f8fb2ce'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())

def main():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    out=R/'readout-v1';summary=read(out/'summary.json')
    assert read(out/'verification.json')['status']=='PASS'
    assert read(out/'verification.json')['summary_sha256']==sha(out/'summary.json')
    audit=read(out/'mechanism-audit.json')
    assert audit['summary_sha256']==sha(out/'summary.json')
    assert audit['plan_sha256']==PLAN
    assert sorted(x['index'] for x in audit['records'])==list(range(14))
    files=[('readout-v1/'+x,x) for x in ('runs.csv','actions.csv','pairs.csv','verification.json','mechanism-audit.json','conditional-sensitivity.json')]
    files += [(x,x) for x in ('readout-freeze.json','transport-loop-cpu.json','verifier-freeze.json','sensitivity-freeze.json','mechanism-freeze.json','analysis-freeze.json','compatibility.json','prior-accounting.json')]
    for name,h in summary['files'].items():assert sha(out/name)==h
    blobs={dst:(R/src).read_bytes() for src,dst in files}
    summary.pop('input_hashes');summary['full_summary_sha256']=sha(out/'summary.json')
    plan=read(R/'plan.json');plan.pop('files');plan['exact_full_plan_sha256']=PLAN
    for name,obj in [('summary-public.json',summary),('plan-public.json',plan)]:
        blobs[name]=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False).encode()
    for raw in blobs.values():assert not SECRET.search(raw),'credential shape: export stopped'
    assert not D.exists();D.mkdir(mode=0o700);receipt=[]
    for name,raw in blobs.items():
        with (D/name).open('xb') as f:f.write(raw)
        receipt.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    obj=dict(status='SAFE_AGGREGATE_EXPORT',files=receipt,raw_labels=False,raw_predictions=False,raw_candidate_programs=False,model_messages=False,credentials=False,source_plan_sha256=PLAN,
        scope='Closed approved developer experiment only. No protected cohort or final-test access. No candidate code or model responses exported.')
    with (D/'export-receipt.json').open('x') as f:json.dump(obj,f,sort_keys=True,indent=2)
    print(json.dumps(dict(status=obj['status'],files=len(receipt),receipt_sha256=sha(D/'export-receipt.json'),path=str(D))))

if __name__=='__main__':main()
