"""Independent stdlib CSV comparison of all eight closed diagnostic outputs."""
import csv,hashlib,json,math
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/forets-fresh-integration-20260914-ih6u0mpw')
raw=(ROOT/'result.json').read_bytes()
if hashlib.sha256(raw).hexdigest()!='4b7e059c43cd266778e80ff22a776ba4de5cc2e74e8007ae94f68f28a7ff789b':raise ValueError('closed result drift')
r=json.loads(raw);rows=r['rows'];out=[]
if len(rows)!=8 or len(r['parallel'])!=24:raise ValueError('fixed complete integration matrix')
for offset in range(0,8,2):
    pair=rows[offset:offset+2]
    if {x['backend'] for x in pair}!={'fresh','jupyter'} or pair[0]['task']!=pair[1]['task']:raise ValueError('pair identity')
    tables=[];hashes=[]
    for item in pair:
        p=ROOT/f'work-{item["index"]}'/'submission.csv';b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
        if h!=item['submission_sha256']:raise ValueError('actual submission hash differs')
        hashes.append(h);tables.append(list(csv.reader(b.decode().splitlines())))
    a,b=tables
    if a[0]!=b[0] or len(a)!=len(b):raise ValueError('rows or columns differ')
    maximum=0.;numeric=0;strings=0
    for x,y in zip(a[1:],b[1:]):
        if len(x)!=len(y) or len(x)!=len(a[0]):raise ValueError('row width differs')
        for u,v in zip(x,y):
            try:f,g=float(u),float(v)
            except ValueError:
                if u!=v:raise ValueError('categorical value differs')
                strings+=1;continue
            if not math.isfinite(f) or not math.isfinite(g):raise ValueError('nonfinite numeric value')
            maximum=max(maximum,abs(f-g));numeric+=1
            if not math.isclose(f,g,rel_tol=0,abs_tol=1e-12):raise ValueError('numeric parity violated')
    out.append(dict(task=pair[0]['task'],pair_index=offset//2,rows=len(a)-1,columns=len(a[0]),numeric_cells=numeric,
        identical_string_cells=strings,max_absolute_difference=maximum,byte_identical=hashes[0]==hashes[1],within_fixed_tolerance=True))
result=dict(all_fixed_checks_pass=True,pairs=out,source_result_sha256=hashlib.sha256(raw).hexdigest(),
    verifier='stdlib csv and math; independent of original pandas/numpy check',api_calls=0,gpu_jobs=0,
    note='Byte equality is not assumed for threaded floating-point reductions; tolerance was fixed before execution.')
out_raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode()
with (ROOT/'independent-parity.json').open('xb') as f:f.write(out_raw)
print(json.dumps(result|dict(sha256=hashlib.sha256(out_raw).hexdigest())))
