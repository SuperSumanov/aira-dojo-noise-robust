import csv,hashlib,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
root=Path('/tmp/gl-label-reuse-20260904-HB29tF/followup')
os.chdir(root)
out=root/'results'; out.mkdir(mode=0o700,exist_ok=False)
source_commit='9d4a70a20c43de5f1613dd87629e1cb4996628f2'
env=dict(os.environ,PYTHONPATH=str(root),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
         OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONHASHSEED='0')
sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'phase1').rglob('*.py')}
context=dict(source_commit=source_commit,source_sha256=sources,launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             started_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,per_child_timeout_seconds=180,
             new_gpu_jobs=0,model_fits=0,api_calls=0)
(out/'execution_context.json').write_text(json.dumps(context,sort_keys=True,indent=2)+'\n')
rows=[]
try:
    for name in ('producer_a','producer_b'):
        cmd=[sys.executable,'-B','-m','phase1.historical_label_reuse_cost_source']
        start=time.monotonic(); p=subprocess.run(cmd,env=env,capture_output=True,timeout=180)
        (out/(name+'.json')).write_bytes(p.stdout)
        rows.append(dict(name=name,command=json.dumps(cmd),source_commit=source_commit,rc=p.returncode,
            seconds=time.monotonic()-start,stderr_bytes=len(p.stderr),stderr_sha256=hashlib.sha256(p.stderr).hexdigest(),
            new_gpu_jobs=0,model_fits=0,api_calls=0))
        with (out/'runs.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        if p.returncode or p.stderr:
            raise RuntimeError('child_failed_closed')
        print(json.dumps(dict(stage=name,rc=0,seconds=rows[-1]['seconds'])),flush=True)
    raw=(out/'producer_a.json').read_bytes()
    if raw!=(out/'producer_b.json').read_bytes(): raise RuntimeError('ab_drift')
    if sources!={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'phase1').rglob('*.py')}:
        raise RuntimeError('source_drift')
    result=json.loads(raw)
    if not result['independent_source_projection_equal']: raise RuntimeError('independent_projection_failed')
    (out/'COMPLETE').write_text('FOLLOWUP_VERIFIED_NO_TRAINING\n')
    print(json.dumps(dict(status='FOLLOWUP_COMPLETE',receipt_sha256=hashlib.sha256(raw).hexdigest(),
        source=result['reused_global_source'],cells=result['joint_source_config_cells'],cost=result['cached_input_cost']),sort_keys=True))
except Exception as exc:
    (out/'FAILED').write_text(type(exc).__name__+'\n')
    print(json.dumps(dict(status='FOLLOWUP_FAILED_CLOSED',exception_type=type(exc).__name__)))
    raise SystemExit(1)
finally:
    (out/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},sort_keys=True,indent=2)+'\n')
