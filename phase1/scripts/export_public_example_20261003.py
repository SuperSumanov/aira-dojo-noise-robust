"""Copy only enumerated, closed, aggregate experiment artifacts for publication."""
import hashlib,json,re,shutil
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
OUT=B/'public-example-export-20261003-v1'
# Boundary avoids the verified false hit inside task-feedback-* directory names.
SECRET=re.compile(rb'(?<![A-Za-z0-9_])(?:sk-[A-Za-z0-9_.-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9_.-]{16,})',re.I)
FORBIDDEN=re.compile(rb'first[-_]?960|target[-_]?(?:300|522)|D_val|official.?test',re.I)
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not OUT.exists()
    specs=[('public_examples_20261003','public-example-feedback-20261003-v1',
       '40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376',
       ['plan.json','cpu.json','transport-cpu.json','launch.json','all-closed.json','closed.json',
        'readout-v1/runs.csv','readout-v1/actions.csv','readout-v1/pairs.csv','readout-v1/summary.json','readout-v1/verification.json']),
      ('char_branch_control_20261003','char-branch-control-20261003-v1',
       'e989f2f0d3d585812fda44bca0b2b6de5124b2222d9c1b2554800f0a4d997269',
       ['plan.json','cpu.json','launch.json','closed.json','readout-v1/runs.csv','readout-v1/pairs.csv','readout-v1/summary.json'])]
    checked=[]
    for folder,root,ph,files in specs:
        r=B/root;assert sha(r/'plan.json')==ph and (r/'closed.json').exists()
        summary=read(r/'readout-v1/summary.json');assert summary['plan_sha256']==ph
        if folder=='public_examples_20261003':
            v=read(r/'readout-v1/verification.json')
            assert v['status']=='PASS' and v['summary_sha256']==sha(r/'readout-v1/summary.json')
            assert read(r/'closed.json')['service_closed']
        else:assert summary['verification_status']=='PASS'
        for rel in files:
            p=r/rel;assert p.is_file() and not p.is_symlink()
            raw=p.read_bytes();assert not SECRET.search(raw),(folder,rel,'credential shape')
            assert not FORBIDDEN.search(raw),(folder,rel,'protected marker review needed')
            dest=folder+'/'+Path(rel).name
            checked.append(dict(source=str(p),relative=dest,sha256=sha(p),bytes=len(raw)))
    assert len({c['relative'] for c in checked})==len(checked)
    OUT.mkdir(mode=0o700)
    for c in checked:
        dest=OUT/c['relative'];dest.parent.mkdir(exist_ok=True);shutil.copyfile(c['source'],dest)
        assert sha(dest)==c['sha256']
    receipt=dict(scope='Explicit closed aggregate allowlist. No credentials, raw examples, model replies, terminal logs, code candidates, labels or prediction rows copied.',files=checked)
    with (OUT/'export-receipt.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(dict(status='PASS',files=len(checked),export_root=str(OUT),receipt_sha256=sha(OUT/'export-receipt.json'))))
if __name__=='__main__':main()
