"""Close only this bounded development run; no prompts, scores, or model replies."""
import datetime,hashlib,json,os,re,subprocess
from pathlib import Path

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'local-qwen27b-20260914-zcx1k1dy/integration-v6'
PRIOR={'13365':('integration-v3',80),'13366':('integration-v4',123),'13367':('integration-v5',369)}

def read(path):return json.loads(path.read_bytes())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if ROOT.resolve(strict=True)!=ROOT:raise ValueError('scope')
    launch=read(ROOT/'launch.json');last_job=launch['job']
    if not last_job.isdigit() or last_job in PRIOR:raise ValueError('launch identity')
    jobs=dict(PRIOR);jobs[last_job]=('integration-v6',None)
    output=ROOT/'public-calibration-readout.json'
    if output.exists():raise ValueError('readout already closed')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf',TZ='UTC')
    text=subprocess.check_output(['sacct','-X','-j',','.join(jobs),'-n','-P','-o',
          'JobID,State,ExitCode,ElapsedRaw,AllocTRES,NodeList,Start,End'],env=env,text=True,timeout=20)
    accounts={}
    for line in text.strip().splitlines():
        fields=line.split('|');job,state,exit_code,elapsed,tres,node,start,end=fields[:8]
        if job not in jobs or job in accounts or state not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED'):
            raise ValueError('accounting incomplete or unknown')
        resources=dict(v.split('=',1) for v in tres.split(','))
        if resources.get('gres/gpu')!='3' or node!='gpu28':raise ValueError('unexpected hardware allocation')
        expected=jobs[job][1]
        if expected is not None and (state!='FAILED' or int(elapsed)!=expected):raise ValueError('prior accounting drift')
        accounts[job]=dict(state=state,exit_code=exit_code,seconds=int(elapsed),gpus=3,node=node,start_utc=start,end_utc=end)
    if set(accounts)!=set(jobs):raise ValueError('missing allocation')
    total_gpu_seconds=sum(row['seconds']*row['gpus'] for row in accounts.values())
    if total_gpu_seconds>10800:raise ValueError('budget exceeded')
    closures={}
    for job,(folder,_) in jobs.items():
        path=ROOT.parent/folder/'closed.json'
        if path.exists():
            value=read(path)
            if value['job']!=job:raise ValueError('wrong closure')
            closures[job]=dict(status=value['status'],sha256=sha(path))
    prepared=read(ROOT/'prepared.json')
    if prepared['commit']!=launch['commit'] or sha(ROOT/'prepared.json')!=read(ROOT/'cpu-preflight.json')['prepared_sha256']:raise ValueError('source commit drift')
    result_path=ROOT/'calibration-results.json'
    results=read(result_path) if result_path.exists() else None
    allowed=('index','task','seed','status','finish_reason','prompt_tokens','completion_tokens','code_chars',
             'generation_seconds','execution_status','execution_seconds','exit_code','timed_out','submission_present',
             'submission_sha256','execution_error','error_type','commit','model','revision','job')
    rows=[{k:v for k,v in row.items() if k in allowed} for row in results['rows']] if results else []
    if results:
        if accounts[last_job]['state']!='COMPLETED' or closures[last_job]['status']!='worker_finished':raise ValueError('result without clean closure')
        if len(rows)!=2 or [r['task'] for r in rows]!=prepared['tasks'] or any(r['seed']!=49 or r['job']!=last_job for r in rows):
            raise ValueError('run matrix mismatch')
    ready=read(ROOT/'ready.json') if (ROOT/'ready.json').exists() else None
    if ready:
        if len(set(ready['service_uuids']))!=2 or len(set(ready['execution_uuids']))!=1 or set(ready['service_uuids'])&set(ready['execution_uuids']):
            raise ValueError('device overlap')
    value=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='CLOSED_DEVELOPMENT_NOT_EFFECT',
        model=prepared['model'],revision=prepared['revision'],commit=prepared['commit'],prepared_sha256=sha(ROOT/'prepared.json'),
        allocations=accounts,closures=closures,total_gpu_seconds=total_gpu_seconds,total_gpu_hours=total_gpu_seconds/3600,
        integration_completed=results is not None,ready_seconds=ready['startup_seconds'] if ready else None,
        rows=rows,warmup=read(ROOT/'warmup.json') if (ROOT/'warmup.json').exists() else None,
        limitations=['Two development drafts only; no cross-seed inference.','Submission presence is not externally graded quality.',
                     'No critic comparison, training, paid API, or protected-cohort read.'])
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if re.search(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})',raw):raise ValueError('credential shape')
    with output.open('xb') as f:f.write(raw)
    print(raw.decode(),flush=True)

if __name__=='__main__':main()
