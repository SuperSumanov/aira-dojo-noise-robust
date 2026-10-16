"""Closed18997 only: native CPU pipeline, mocked final transport, no HTTP/GPU.

Checks the actual constructor/adapter chain forwards the configured search seed.
This cannot establish what a live server received or why completions diverged.
"""
import hashlib
import json
from pathlib import Path
import sys
import subprocess

ROOT=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
PIN='1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main(index,out):
    index=int(index);out=Path(out)
    assert index in (0,1,8,9)
    assert sha(ROOT/'plan.json')==PIN and (ROOT/'closed.json').exists()
    assert not out.exists()
    source_path=ROOT/'fixed_preview_native_cpu_20261014.py'
    source=source_path.read_text()
    def replace(a,b):
        nonlocal source
        assert source.count(a)==1,a[:80]
        source=source.replace(a,b)
    replace('        seen=[]','        seen=[];parameters=[]')
    replace("            seen.append(kwargs['messages'])", """            assert kwargs.get('seed')==row['seed'],'seed did not reach native transport'
            parameters.append({k:kwargs.get(k) for k in ('model','seed','temperature','top_p','top_k','max_tokens','reasoning_effort')})
            seen.append(kwargs['messages'])""")
    replace('            http_calls=0,model_calls=0,gpu_calls=0,', """            transport_parameters=parameters,all_three_transport_seeds_matched=True,
            parent_plan_sha256=PLAN_PIN,parent_fixture_sha256=PARENT_FIXTURE_SHA,
            diagnostic_source_sha256=DIAGNOSTIC_SHA,
            http_calls=0,model_calls=0,gpu_calls=0,""")
    # Execute only the original function definitions; avoid its CLI entry point.
    ns=dict(__name__='closed_seed_transport_fixture',__file__=str(source_path),
            PLAN_PIN=PIN,PARENT_FIXTURE_SHA=sha(source_path),DIAGNOSTIC_SHA=sha(Path(__file__)))
    sys.path.insert(0,str(ROOT))
    exec(compile(source,str(source_path),'exec'),ns)
    ns['main'](ROOT,ROOT/'public-preview.private.json',index,out)

def batch():
    dest=Path(__file__).parent/'closed-seed-transport-18997'
    dest.mkdir(exist_ok=False)
    for index in (0,1,8,9):
        out=dest/f'{index}.json'
        try:
            result=subprocess.run([sys.executable,str(Path(__file__)),str(index),str(out)],
                                  capture_output=True,text=True,timeout=90)
        except subprocess.TimeoutExpired:
            print(json.dumps(dict(index=index,passed=False,reason='CPU fixture timeout; no raw log exported')))
            return 1
        if result.returncode:
            print(json.dumps(dict(index=index,passed=False,reason='CPU fixture failed; no raw log exported')))
            return 1
        data=json.loads(out.read_text())
        assert data['http_calls']==data['model_calls']==data['gpu_calls']==0
        print(json.dumps(dict(index=index,passed=True,sha256=sha(out),
            prompt_sha256=data['first_prompt_sha256'],parameters=data['transport_parameters'],
            native_client_sha256=data['native_client_sha256'])),flush=True)
    return 0

if __name__=='__main__':
    if sys.argv[1:]==['--batch']:raise SystemExit(batch())
    main(*sys.argv[1:])
