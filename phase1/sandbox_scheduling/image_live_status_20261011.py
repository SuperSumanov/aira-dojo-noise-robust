"""Counts-only status of one frozen fresh development experiment, no log text."""
import json,os,re,subprocess,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v1')
def read(p):
    try:return json.loads(p.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
def status():
    launch=read(R/'launch.json');out=dict(submitted=launch is not None)
    if launch:
        job=launch['job'];assert re.fullmatch(r'\d+',job)
        env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
        q=subprocess.check_output(['squeue','-j',job,'-h','-o','%T|%N|%R'],env=env,text=True,timeout=15).strip()
        out.update(job=job,scheduler=q)
    out['started_runs']=sum((R/f'episode-{i}/deadline.json').exists() for i in range(32))
    out['finished_runs']=sum((R/f'episode-{i}/finished.json').exists() for i in range(32))
    out['pools_with_ready_service']=sum((R/f'block-{i}/service-ready.json').exists() for i in range(4))
    out['closed_equal_budget_pools']=sum((R/f'block-{i}/budget-slot.json').exists() for i in range(4))
    out['returned_candidates']=out['valid_development_returns']=out['cuda_observed_runs']=0
    out['event_counts']={s:0 for s in ('runtime_hooks_installed','kernel_ready','generation_started','generation_returned','operation_ready','cell_return','cleanup')}
    for i in range(32):
        ep=R/f'episode-{i}'
        for p in ep.glob('candidate-*.json'):
            if '.private.' in p.name:continue
            r=read(p)
            if r:
                out['returned_candidates']+=1;out['valid_development_returns']+=int(r['valid'])
        trainings=[read(p) for p in ep.glob('gpu-training-*.json') if 'missing' not in p.name]
        out['cuda_observed_runs']+=int(any(r and r.get('cuda_gradient_steps',0)>0 for r in trainings))
        events=ep/'events.jsonl'
        if events.exists():
            for line in events.read_text().splitlines():
                try:event=json.loads(line).get('event')
                except json.JSONDecodeError:continue
                if event in out['event_counts']:out['event_counts'][event]+=1
    c=read(R/'closed.json')
    if c:out['closure']=c
    # Only predefined classes/flags, never arbitrary private error lines.
    flags={s:0 for s in ('Traceback','ValueError','RuntimeError','AssertionError','TypeError','ModuleNotFoundError','PermissionError',
                         'resource temporarily unavailable','pthread_create','CUDA out of memory','InvalidStateError','TimeoutError')}
    frames=[]
    for p in list(R.glob('allocation-*.err'))+list(R.glob('block-*/lane-*.private.log'))+list(R.glob('episode-*/worker.private.log')):
        text=p.read_text(errors='replace')
        for flag in flags:flags[flag]+=text.count(flag)
        for file,line,func in re.findall(r'File "([^"\n]+)", line (\d+), in ([A-Za-z_][A-Za-z_0-9]*)',text):
            frames.append(dict(log=str(p.relative_to(R)),file=Path(file).name,line=int(line),function=func))
    out['error_flag_counts']=flags
    unique={}
    for f in frames:
        key=(f['file'],f['line'],f['function'])
        if key not in unique:unique[key]=dict(file=key[0],line=key[1],function=key[2],occurrences=0)
        unique[key]['occurrences']+=1
    out['exception_frames']=list(unique.values())
    out['service_phases']=[]
    for p in sorted(R.glob('block-*/service.private.log')):
        text=p.read_text(errors='replace')
        markers=('Loading safetensors checkpoint shards','Loading model weights','Model loading took',
                 'Graph capturing','Capturing CUDA graphs','Application startup complete','Traceback','ValueError','RuntimeError')
        out['service_phases'].append(dict(block=p.parent.name,bytes=p.stat().st_size,markers={s:text.count(s) for s in markers}))
    print(json.dumps(out,sort_keys=True))
if __name__=='__main__':
    if len(sys.argv)>1:
        assert sys.argv[1] in ('v2','v3')
        R=R.with_name('scheduling-image-live-2plus4-20261011-'+sys.argv[1])
    status()
