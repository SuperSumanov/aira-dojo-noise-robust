"""Run the repaired production gate's actual main in a new CPU-only directory.

Frozen19004 files are read-only dependencies. No old readout/preflight is run.
The gate forbids kernel constructors and LLM calls; this is not live acceptance.
"""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys,tempfile

OLD=Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1')
PIN='f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    stage=Path(__file__).parent
    assert sha(OLD/'plan.json')==PIN and (OLD/'closed.json').is_file()
    names=('generation_quota_trial_20261017.py','generation_quota_production_gate_20261017.py')
    hashes={n:sha(stage/n) for n in names}
    assert hashes[names[0]]=='ec1b52590b7bda69cc6d651f53a3d9588e84a14cdae3764d0eb2d34eb31df2b6'
    # Do not remove this directory on exit: it is failure/success evidence.
    fixture=Path(tempfile.mkdtemp(prefix='quota-main-cpu-',dir=stage));os.chmod(fixture,0o700)
    for name in names:
        shutil.copyfile(stage/name,fixture/name);assert sha(fixture/name)==hashes[name]
    env=os.environ.copy();env.update(PYTHONPATH=str(OLD),PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',CUDA_VISIBLE_DEVICES='')
    gate=fixture/names[1]
    cp=subprocess.run([sys.executable,'-B',str(gate),str(fixture)],cwd=fixture,env=env,capture_output=True,timeout=180)
    with (fixture/'process.private.log').open('xb') as f:f.write(cp.stdout+cp.stderr)
    assert sha(OLD/'plan.json')==PIN
    if cp.returncode:raise RuntimeError('CPU gate main failed; private evidence preserved at '+str(fixture))
    result=json.loads((fixture/'production-guard.safe.json').read_text())
    assert result['passed'] and len(result['cases'])==10 and result['production_source_sha256']==hashes[names[0]]
    assert {(r['index'],r['case']) for r in result['cases']}=={(i,c) for i in (0,8) for c in ('success','queue','admit','cancel','release')}
    assert all(r['passed'] and r['gpu_calls']==r['model_calls']==r['kernel_calls']==0 for r in result['cases'])
    out=dict(passed=True,fixture_root=str(fixture),runner_sha256=sha(__file__),source_hashes=hashes,
        old_plan_sha256=PIN,production_gate_sha256=sha(fixture/'production-guard.safe.json'),production_cases=10,
        gpu_calls=0,model_calls=0,kernel_calls=0,
        limitation='Actual CPU gate main only. No worker search, live quota borrowing, CUDA qualification or quality comparison.')
    dest=stage/'quota-gate-main-20261017.safe.json'
    with dest.open('x') as f:json.dump(out,f,indent=2,sort_keys=True)
    print(json.dumps(out,sort_keys=True))

if __name__=='__main__':main()
