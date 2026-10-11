"""Independent 12-case denominator, actual event, cleanup and cost audit."""
import csv,hashlib,json,os,re,statistics,subprocess,sys,time
from pathlib import Path
from kernel_restart_guard import overlay
from kernel_shutdown_guard import METHOD_SHA
ROOT=Path('/research/d7/spc/yzyang4/resource-restart-guard-trial-20261011-v2')
PIN='4a27286e2480951f8b0114107f751e3cc8685a2317226038dccf22430f979929'
JOB='17569'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit():
    p=read(ROOT/'plan.json');c=read(ROOT/'closed.json')
    assert sha(ROOT/'plan.json')==PIN
    assert read(ROOT/'launch.json')==dict(job=JOB,plan_sha256=PIN,readout_sha256=sha(Path(__file__)))
    assert p['version']==2 and p['planned']==c['planned']==12 and p['execution_timeout']==12 and p['gpus']==1
    assert p['source_commit']=='f7ccd79323112b10ccc82d8e9ec9d6cf089df607' and p['no_gpu_compute'] and p['no_task_data']
    manifest=all(sha(ROOT/n)==h for n,h in p['files'].items())
    assert (ROOT/'source-guard'/ 'src/dojo/core/interpreters/jupyter/jupyter_client.py').read_text()==overlay((ROOT/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py').read_text())
    matrix=[]
    for rep in range(3):
        for arm in (('old','guard') if rep%2==0 else ('guard','old')):
            for case in (('normal','exit') if rep%2==0 else ('exit','normal')):matrix.append(dict(index=len(matrix),repeat=rep,arm=arm,case=case))
    assert p['schedule']==matrix
    attempts={x['index'] for x in c['rows']};assert len(attempts)==c['attempted']
    rows=[]
    for row in matrix:
        ep=ROOT/f"case-{row['index']}";f=ep/'receipt.json';r=read(f) if f.exists() else {};out=r.get('result') or {}
        events=[json.loads(x) for x in (ep/'kernel-lifecycle.jsonl').read_text().splitlines()] if (ep/'kernel-lifecycle.jsonl').exists() else []
        native=any(e['event']=='exit_observed' and e['returncode']==17 for e in events)
        notice=any(e['kind']=='status' and e['state']=='restarting' and not e['has_parent'] for e in r.get('messages',[]))
        install=ep/'kernel-shutdown-guard-installed.json'
        correct_install=(read(install)==dict(original_sha256=METHOD_SHA,transition_timeout=15,no_candidate_retry=True)) if install.exists() else False
        log=(ep/'worker.private.log').read_text(errors='replace') if (ep/'worker.private.log').exists() else ''
        # Raw log stays remote; these fixed flags cannot contain source, URL or token.
        flags=dict(http500=bool(re.search(r'\b500 DELETE /api/kernels/',log)),invalid_state='InvalidStateError' in log,
                   forced_server_kill='did not terminate; sending SIGKILL' in log,terminated='Singularity Jupyter server terminated' in log)
        normal=row['case']=='normal'
        expected=(out.get('exit_code')==0 and out.get('timed_out') is False and out.get('normal_marker')) if normal else (
            out.get('exit_code')==1 and native and notice and out.get('timed_out') is (row['arm']=='old')
            and (row['arm']=='old' or out.get('lifecycle_marker') and out.get('seconds',999)<=8))
        good=bool(r.get('complete') and expected and (ep/'kernel-lifecycle-installed.json').exists()
                  and correct_install==(row['arm']=='guard') and flags['terminated'] and not any(flags[k] for k in ('http500','invalid_state','forced_server_kill')))
        rows.append(dict(**row,job=JOB,seed=p['source_seed'],source_commit=p['source_commit'],plan_sha256=PIN,
            attempted=row['index'] in attempts,complete=r.get('complete',False),error_type=r.get('error_type'),seconds=out.get('seconds'),
            normal_stdout_sha256=out.get('stdout_sha256'),exit_code=out.get('exit_code'),timed_out=out.get('timed_out'),
            exit17_recorded=native,parentless_restart_received=notice,shutdown_guard=correct_install,
            cleanup_seconds=(r['end']-out['end']) if out.get('end') else None,case_gate=good,**flags))
    assert sum(r['complete'] for r in rows)==c['complete']
    normals=[r for r in rows if r['case']=='normal'];same=bool(all(r['normal_stdout_sha256'] for r in normals) and len({r['normal_stdout_sha256'] for r in normals})==1)
    summary=[]
    for arm in ('old','guard'):
        for case in ('normal','exit'):
            group=[r for r in rows if r['arm']==arm and r['case']==case];times=[r['seconds'] for r in group if r['seconds'] is not None]
            cleanup=[r['cleanup_seconds'] for r in group if r['cleanup_seconds'] is not None]
            summary.append(dict(arm=arm,case=case,planned=3,observed=len(times),complete=sum(r['complete'] for r in group),
                median_seconds=statistics.median(times) if times else None,sample_sd_seconds=statistics.stdev(times) if len(times)>1 else None,
                median_cleanup_seconds=statistics.median(cleanup) if cleanup else None))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',JOB,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    accounting=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==JOB];assert len(accounting)==1
    state,elapsed,tres=accounting[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
    assert re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1]=='1' and int(elapsed)<=600
    before=read(ROOT/'before.json')['uid_counts'];after=read(ROOT/'after.json')['uid_counts']
    clean=after['visible_processes']<=before['visible_processes'] and after['visible_threads']<=before['visible_threads'] and after['zombies']==0 and after['unreadable_or_racing']==0
    result=dict(job=JOB,plan_sha256=PIN,closed_sha256=sha(ROOT/'closed.json'),planned=12,attempted=c['attempted'],complete=c['complete'],unstarted=12-c['attempted'],
        manifest_ok=manifest,normal_outputs_equal=same,summary=summary,before_uid=before,after_uid=after,uid_returned_to_baseline=clean,
        gpu_seconds=int(elapsed),gpu_seconds_cap=600,scheduler_state=state,
        gate=bool(manifest and same and clean and c['complete']==12 and all(r['case_gate'] for r in rows) and state=='COMPLETED'),
        boundary='Controlled CPU-only exit17 fault. Not prevention of native crash, six-GPU capacity, historical EAGAIN root cause or MLE quality. UID counts are visible lower bounds.')
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))
if __name__=='__main__':
    assert sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN,readout_sha256=sha(Path(__file__))),f)
        print('launch pinned')
    elif sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='watch':
        previous=None;end=time.monotonic()+650
        while time.monotonic()<end:
            rows=[read(f) for f in ROOT.glob('case-*/receipt.json')]
            status=dict(job=JOB,terminals=len(rows),complete=sum(r['complete'] for r in rows),closed=(ROOT/'closed.json').exists())
            if status!=previous:print(json.dumps(status),flush=True);previous=status
            if status['closed']:break
            time.sleep(10)
