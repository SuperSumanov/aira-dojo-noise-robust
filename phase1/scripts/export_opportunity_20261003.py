"""Export explicit closed aggregate artifacts, never raw task/agent data."""
import hashlib,json,re,shutil
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');OUT=B/'opportunity-export-20261003-v1'
SECRET=re.compile(rb'(?<![A-Za-z0-9_])(?:sk-[A-Za-z0-9_.-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9_.-]{16,})',re.I)
FORBIDDEN=re.compile(rb'first[-_]?960|target[-_]?(?:300|522)|D_val|official.?test',re.I)
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not OUT.exists();checked=[];account=[]
    specs=[
      ('calibration_opportunity_20261003','calibration-opportunity-20261003-v1','bb2652e5957b6e043138c1c50de95874c487a8ea4fd5e72bb164fe6e03fd8a94',
       ['plan.json','cpu.json','launch.json','closed.json','readout-v1/runs.csv','readout-v1/summary.json','readout-v1/sensitivity.json']),
      ('nb_ratio_opportunity_20261003','nb-ratio-opportunity-20261003-v1','b810f31f70ea89e81bf1a1557544c0e9fe072ce6534fdb1449665be7f12e53fc',
       ['plan.json','cpu.json','launch.json','closed.json','readout-v1/runs.csv','readout-v1/summary.json']),
      ('style_opportunity_20261003','style-opportunity-20261003-v1','dfa60c1c84544d02e8effd5a3d5e18ce38839d502c8e6d615700856164032371',
       ['plan.json','cpu.json','launch.json','closed.json','readout-v1/runs.csv','readout-v1/summary.json']),
      ('convex_opportunity_20261003','convex-opportunity-20261003-v1','614b1a10de6b86e2c9849c72fd8ec096a287ffc19417572f073d8f69f7ff829d',
       ['plan.json','runs.csv','summary.json','verification.json']),
      ('pairmix_opportunity_20261003','pairmix-opportunity-20261003-v1','e72d40e131eaa2a05d8588b96c23f468ae7a5a626436918faa9dfa05bf0f2e43',
       ['plan.json','runs.csv','summary.json','numerics.json']),
      ('pairmix_sensitivity_20261003','pairmix-sensitivity-20261003-v1','2cd9b9032292b3fa082210b38f1f1435daa03787af0d214243c49a4587d5f0e5',
       ['plan.json','runs.csv','folds.csv','summary.json'])]
    for folder,root,ph,files in specs:
        r=B/root;assert sha(r/'plan.json')==ph
        summary_path=r/('readout-v1/summary.json' if (r/'closed.json').exists() else 'summary.json')
        s=read(summary_path);assert s['plan_sha256']==ph
        if (r/'closed.json').exists():
            assert s['verification']=='PASS' and s['valid_pairs']==3
            parts=s['accounting'].split('|');assert parts[1]=='COMPLETED' and 'gres/gpu=2' in parts[3]
            account.append(dict(job=parts[0],seconds=int(parts[2]),gpus=2,gpu_hours=int(parts[2])*2/3600))
            for name,h in s['files'].items():assert sha(r/'readout-v1'/name)==h
        elif folder.startswith('convex'):
            v=read(r/'verification.json');assert v['status']=='PASS' and v['summary_sha256']==sha(summary_path)
        elif folder.startswith('pairmix_opportunity'):
            v=read(r/'numerics.json');assert v['cv_aggregation']=='PASS' and v['summary_sha256']==sha(summary_path)
            assert v['mismatches']==2  # Preserved, not silently promoted to all-equal.
        else:
            v=read(B/'pairmix-opportunity-20261003-v1/numerics.json');assert v['cv_summary_sha256']==sha(summary_path)
        for rel in files:
            p=r/rel;assert p.is_file() and not p.is_symlink()
            raw=p.read_bytes();assert not SECRET.search(raw),(folder,rel,'credential-shape')
            assert not FORBIDDEN.search(raw),(folder,rel,'protected marker review needed')
            dest=folder+'/'+Path(rel).name
            checked.append(dict(source=str(p),relative=dest,sha256=sha(p),bytes=len(raw)))
    assert len({x['relative'] for x in checked})==len(checked)
    OUT.mkdir(mode=0o700)
    for x in checked:
        p=OUT/x['relative'];p.parent.mkdir(exist_ok=True);shutil.copyfile(x['source'],p);assert sha(p)==x['sha256']
    receipt=dict(scope='Closed exact allowlist of plans, aggregate rows and verifiers. No labels/prediction rows/model replies/candidate code/private weights/raw logs.',
        files=checked,accounting=account,total_gpu_hours=sum(x['seconds']*x['gpus'] for x in account)/3600,
        paid_api_calls=0,generator_calls=0,base_model_updates=0,
        limitations='Nine real task-program runs on one task; repeated prediction and shared-data dependence reported. Oracle and CV analyses are not a new agent method or fresh generalization.')
    with (OUT/'export-receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(dict(status='PASS',files=len(checked),export_root=str(OUT),receipt_sha256=sha(OUT/'export-receipt.json'),
        accounting=account,total_gpu_hours=receipt['total_gpu_hours'])))
if __name__=='__main__':main()
