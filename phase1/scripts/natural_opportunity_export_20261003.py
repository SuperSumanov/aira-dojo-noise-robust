import hashlib,json,re,shutil
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');DEST=B/'natural-opportunity-export-20261003-v1'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
ITEMS={
 'qualification':('natural-opportunity-20261003-v1',['readout.json','readout-runs.csv','readout-pairs.csv','verification.json','conditional-sensitivity.json','decoder-contract-pre-score.json','readout-freeze.json','cpu.json']),
 'decoder_supplement':('natural-decoder-factorial-20261003-v1',['readout.json','readout-runs.csv','readout-pairs.csv','verification.json','readout-freeze.json','cpu.json'])}
assert not DEST.exists();DEST.mkdir(mode=0o700);receipt=[]
for label,(name,files) in ITEMS.items():
    source=B/name;dest=DEST/label;dest.mkdir()
    for file in files:
        assert 'private' not in file and file in ITEMS[label][1]
        raw=(source/file).read_bytes();assert not SECRET.search(raw)
        shutil.copyfile(source/file,dest/file);receipt.append(dict(path=f'{label}/{file}',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    plan=json.loads((source/'plan.json').read_bytes())
    safe={k:v for k,v in plan.items() if k not in ('files',)}
    safe['exact_full_plan_sha256']=hashlib.sha256((source/'plan.json').read_bytes()).hexdigest()
    raw=json.dumps(safe,sort_keys=True,indent=2,allow_nan=False).encode();assert not SECRET.search(raw)
    with (dest/'plan-public.json').open('xb') as f:f.write(raw)
    receipt.append(dict(path=f'{label}/plan-public.json',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
out=dict(status='SAFE_AGGREGATE_EXPORT',files=receipt,raw_predictions=False,raw_labels=False,raw_candidate_programs=False,model_messages=False,credentials=False,
    scope='Only current approved developer results; no protected cohorts. Frozen supplement summary is preserved alongside explicit verifier correction.')
with (DEST/'export-receipt.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(dict(status='SAFE_AGGREGATE_EXPORT',files=len(receipt),receipt_sha256=hashlib.sha256((DEST/'export-receipt.json').read_bytes()).hexdigest(),path=str(DEST))))
