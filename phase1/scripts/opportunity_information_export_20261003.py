"""Export only the closed experiment's safe aggregate evidence; no raw messages."""
import hashlib,json,re,shutil
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2')
D=Path('/research/d7/spc/yzyang4/opportunity-information-export-20261003-v1')
PLAN='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def main():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    assert read(R/'readout-v1/verification.json')['status']=='PASS'
    assert (R/'readout-v1/mechanism-audit.json').exists()
    files=[('readout-v1/'+x,x) for x in ('runs.csv','actions.csv','pairs.csv','verification.json','mechanism-audit.json','conditional-sensitivity.json')]
    files += [(x,x) for x in ('readout-freeze.json','cpu.json','transport-loop-cpu.json','service-ready.json','sensitivity-freeze.json')]
    # Inspect every byte before producing the export directory.
    blobs={dest:(R/src).read_bytes() for src,dest in files}
    summary=read(R/'readout-v1/summary.json'); summary.pop('input_hashes')
    summary['full_summary_sha256']=sha(R/'readout-v1/summary.json')
    plan=read(R/'plan.json'); plan.pop('files'); plan['exact_full_plan_sha256']=PLAN
    for name,obj in [('summary-public.json',summary),('plan-public.json',plan)]:
        blobs[name]=json.dumps(obj,sort_keys=True,indent=2,allow_nan=False).encode()
    for raw in blobs.values():assert not SECRET.search(raw),'credential shape'
    assert not D.exists(); D.mkdir(mode=0o700); receipt=[]
    for name,raw in blobs.items():
        with (D/name).open('xb') as f:f.write(raw)
        receipt.append(dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    obj=dict(status='SAFE_AGGREGATE_EXPORT',files=receipt,raw_labels=False,raw_predictions=False,raw_candidate_programs=False,model_messages=False,credentials=False,
        source_plan_sha256=PLAN,scope='Only fully closed approved developer experiment; protected cohorts remain closed.')
    with (D/'export-receipt.json').open('x') as f:json.dump(obj,f,sort_keys=True,indent=2)
    print(json.dumps(dict(status=obj['status'],files=len(receipt),receipt_sha256=sha(D/'export-receipt.json'),path=str(D))))
if __name__=='__main__':main()
