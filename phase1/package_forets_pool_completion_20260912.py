"""Share all sixteen revealed development programs; no raw logs or task data."""
import hashlib
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT=Path('/research/d7/spc/yzyang4/forets-pool-completion-20260912-2u45zbx4')
PARENT=ROOT.parent/'forets-wallclock-20260912-cxb9p0og'
SUMMARY='4af0927191826f5c574f5c6caafe61337651c4d4aca62a96badcd6252749afb6'

def build():
    import sys
    sys.path.insert(0,str(ROOT));import forets_pool_completion_20260912 as worker
    worker.checked(ROOT)
    raw=(ROOT/'pool-completion-summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SUMMARY:raise ValueError('verified summary drift')
    summary=json.loads(raw);payloads={};programs=[];pools=[]
    for pi,pool in enumerate(summary['pools']):
        rid=pool['parent_run_id'];cfg=json.loads(worker.safe_bytes(PARENT/'configs'/(rid+'.json'),PARENT))
        cp=Path(cfg['solver']['checkpoint_path']);data,_=worker.snap(cp/'forets-candidates-private/batch-1.sqlite')
        for row,candidate in zip(pool['rows'],data['candidates']):
            code=candidate['node']['code'].encode();slot=row['slot']
            if hashlib.sha256(code).hexdigest()!=row['code_sha256'] or worker.SECRET.search(code):raise ValueError('code security/hash')
            name=f'pool-{pi}/code-{slot}.py';payloads[name]=code
            programs.append(dict(row,code_file=name))
        pools.append({k:v for k,v in pool.items() if k!='rows'})
    if len(programs)!=16 or len({r['code_sha256'] for r in programs})!=16:raise ValueError('all unique slots required')
    payloads['programs.json']=json.dumps(programs,indent=2,allow_nan=False).encode()
    payloads['pools.json']=json.dumps(pools,indent=2,allow_nan=False).encode()
    manifest=dict(role='revealed_development_only_not_new_test',job='13165',parent_job='13156',
        summary_sha256=SUMMARY,source_tree=summary['source_tree'],controller_commit=summary['controller_commit'],
        original_failed_call_not_rerun=True,protected_cohort_included=False,files={n:hashlib.sha256(b).hexdigest() for n,b in payloads.items()},
        limitation='Sixteen unique codes, fifteen known outcomes and one original infrastructure unknown. Do not use revealed outcome metadata as decision-time judge input. No fresh confirmation or e2e claim.')
    payloads['manifest.json']=json.dumps(manifest,indent=2,allow_nan=False).encode()
    if any(worker.SECRET.search(b) for b in payloads.values()):raise ValueError('secret in package')
    path=ROOT/'forets-first-pool-completion-20260912.zip'
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,b in sorted(payloads.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,9,12,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16;archive.writestr(info,b)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:raise ValueError('zip corruption')
        for n,b in payloads.items():
            if archive.read(n)!=b:raise ValueError('zip bytes differ')
    print(json.dumps(dict(path=str(path),entries=len(payloads),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())))

if __name__=='__main__':build()
