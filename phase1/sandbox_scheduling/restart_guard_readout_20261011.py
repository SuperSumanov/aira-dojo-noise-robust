"""Independent frozen12-case fault-observation audit, including missing cases."""
import csv,hashlib,json,os,re,statistics,subprocess,sys,time
from pathlib import Path
from kernel_restart_guard import overlay

ROOT=Path('/research/d7/spc/yzyang4/resource-restart-guard-trial-20261011-v1')
PIN='47f008933f0bb055bf26d1866444ff074eafb8f950b281d32b8340ada2024f62'
JOB='17568'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit():
    p=read(ROOT/'plan.json');c=read(ROOT/'closed.json')
    assert sha(ROOT/'plan.json')==PIN and read(ROOT/'launch.json')==dict(job=JOB,plan_sha256=PIN,readout_sha256=sha(Path(__file__)))
    assert p['planned']==c['planned']==12 and p['execution_timeout']==12 and p['gpus']==1 and p['no_task_data'] and p['no_gpu_compute']
    assert p['source_commit']=='f7ccd79323112b10ccc82d8e9ec9d6cf089df607'
    manifest=all(sha(ROOT/n)==h for n,h in p['files'].items())
    before=(ROOT/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py').read_text()
    assert (ROOT/'source-guard/src/dojo/core/interpreters/jupyter/jupyter_client.py').read_text()==overlay(before)
    matrix=[]
    for repeat in range(3):
        for arm in (('old','guard') if repeat%2==0 else ('guard','old')):
            for case in (('normal','exit') if repeat%2==0 else ('exit','normal')):matrix.append(dict(index=len(matrix),repeat=repeat,arm=arm,case=case))
    assert p['schedule']==matrix
    attempted={x['index'] for x in c['rows']};assert len(attempted)==c['attempted']
    rows=[];traces=[]
    for row in matrix:
        ep=ROOT/f"case-{row['index']}";f=ep/'receipt.json';receipt=read(f) if f.exists() else {}
        out=receipt.get('result') or {};ev=[json.loads(x) for x in (ep/'kernel-lifecycle.jsonl').read_text().splitlines()] if (ep/'kernel-lifecycle.jsonl').exists() else []
        for e in ev:
            assert e['event'] in ('launched','exit_observed') and type(e['pid']) is int
            assert set(e)==({'event','pid','time'} if e['event']=='launched' else {'event','pid','time','returncode'})
        messages=receipt.get('messages',[])
        status=any(x['kind']=='status' and x['state']=='restarting' and not x['has_parent'] for x in messages)
        native=any(x['event']=='exit_observed' and x['returncode']==17 for x in ev)
        values=dict(**row,job=JOB,source_commit=p['source_commit'],seed=p['source_seed'],plan_sha256=PIN,attempted=row['index'] in attempted,
            complete=receipt.get('complete',False),error_type=receipt.get('error_type'),exit_code=out.get('exit_code'),timed_out=out.get('timed_out'),seconds=out.get('seconds'),
            normal_marker=out.get('normal_marker'),stdout_sha256=out.get('stdout_sha256'),lifecycle_marker=out.get('lifecycle_marker'),
            exit17_recorded=native,parentless_restart_received=status,observer_installed=(ep/'kernel-lifecycle-installed.json').exists())
        rows.append(values);traces.append(dict(index=row['index'],events=ev,messages=messages))
    assert sum(x['attempted'] for x in rows)==c['attempted'] and sum(x['complete'] for x in rows)==c['complete']
    checks=[];summary=[]
    for arm in ('old','guard'):
        for case in ('normal','exit'):
            group=[x for x in rows if x['arm']==arm and x['case']==case]
            valid=all(x['complete'] and x['observer_installed'] for x in group)
            if case=='normal':valid &= all(x['exit_code']==0 and x['timed_out'] is False and x['normal_marker'] for x in group)
            else:
                valid &= all(x['exit_code']==1 and x['exit17_recorded'] and x['parentless_restart_received'] for x in group)
                valid &= all(x['timed_out'] is (arm=='old') for x in group)
                if arm=='guard':valid &= all(x['lifecycle_marker'] and x['seconds']<=8 for x in group if x['seconds'] is not None)
            checks.append(valid);times=[x['seconds'] for x in group if x['seconds'] is not None]
            summary.append(dict(arm=arm,case=case,planned=3,observed=len(times),complete=sum(x['complete'] for x in group),
                median_seconds=statistics.median(times) if times else None,sample_sd_seconds=statistics.stdev(times) if len(times)>1 else None,gate=valid))
    normal=[x for x in rows if x['case']=='normal'];normal_same=all(x['stdout_sha256'] for x in normal) and len({x['stdout_sha256'] for x in normal})==1
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    accounting=subprocess.check_output(['sacct','-X','-j',JOB,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    a=[x.split('|') for x in accounting.splitlines() if x.split('|')[0]==JOB];assert len(a)==1
    state,elapsed,tres=a[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==1 and int(elapsed)<=600
    result=dict(job=JOB,plan_sha256=PIN,closed_sha256=sha(ROOT/'closed.json'),planned=12,attempted=c['attempted'],complete=c['complete'],unstarted=12-c['attempted'],
        manifest_ok=manifest,normal_stdout_all_equal=bool(normal_same),summary=summary,gpu_seconds=int(elapsed),gpu_seconds_cap=600,scheduler_state=state,
        gate=bool(c['complete']==12 and manifest and normal_same and all(checks) and state=='COMPLETED'),traces=traces,
        boundary='Artificial os._exit17 cause known by construction. Confirms control-event handling only; not spontaneous crash prevention,historical EAGAIN resolution,GPU throughput or MLE quality.')
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k!='traces'}))

def watch():
    previous=None;end=time.monotonic()+650
    while time.monotonic()<end:
        try:
            rows=[read(f) for f in ROOT.glob('case-*/receipt.json')]
            state=dict(job=JOB,terminals=len(rows),complete=sum(x['complete'] for x in rows),closed=(ROOT/'closed.json').exists())
            if state!=previous:print(json.dumps(state),flush=True);previous=state
            if state['closed']:print(json.dumps(read(ROOT/'closed.json')),flush=True);return
        except (OSError,ValueError):pass
        time.sleep(10)

if __name__=='__main__':
    assert sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN,readout_sha256=sha(Path(__file__))),f)
        print('launch and audit code pinned')
    elif sys.argv[1]=='watch':watch()
    elif sys.argv[1]=='audit':audit()
