"""Read-only numeric diagnostics; never modifies a frozen experiment or gate."""
import argparse,contextlib,io,json,re,statistics,subprocess,os
from pathlib import Path
import image_live_funnel_20261011 as funnel

ROOTS={
    'old':('/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v3',
        '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66'),
    'deadline':('/research/d7/spc/yzyang4/scheduling-image-generation-deadline-20261011-v1',
        'd153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7')}

def stats(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        max=max(values) if values else None,min=min(values) if values else None)

def inspect(which):
    path,pin=ROOTS[which];root=Path(path);funnel.ROOT=root;funnel.PIN=pin
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):funnel.summarize()
    report=json.loads(buf.getvalue());report['pools']=[]
    for bd in sorted(root.glob('block-*')):
        log=bd/'service.private.log';text=log.read_text(errors='replace') if log.exists() else ''
        metrics={name:stats([float(v) for v in re.findall(pattern,text)]) for name,pattern in {
            'running_requests':r'Running:\s*(\d+)\s*reqs',
            'waiting_requests':r'Waiting:\s*(\d+)\s*reqs',
            'prompt_tokens_per_second':r'Avg prompt throughput:\s*([\d.]+)\s*tokens/s',
            'generation_tokens_per_second':r'Avg generation throughput:\s*([\d.]+)\s*tokens/s',
            'gpu_kv_cache_percent':r'GPU KV cache usage:\s*([\d.]+)%',
            'prefix_cache_hit_percent':r'Prefix cache hit rate:\s*([\d.]+)%'}.items()}
        first=[]
        for row in report['rows']:
            if row['block']!=int(bd.name.split('-')[1]):continue
            ev=funnel.events(root/f"episode-{row['index']}/events.jsonl")
            start=next((e for e in ev if e['event']=='generation_started' and e['call']==0),None)
            end=next((e for e in ev if e['event']=='generation_returned' and e['call']==0),None)
            first.append(dict(index=row['index'],task=row['task'],started=start is not None,
                start_time=start['time'] if start else None,start_elapsed=start['elapsed'] if start else None,
                returned=end is not None,success=end['success'] if end else None,seconds=end['seconds'] if end else None))
        report['pools'].append(dict(block=bd.name,service_ready=funnel.read(bd/'service-ready.json'),
            budget=funnel.read(bd/'budget-slot.json'),metrics=metrics,first_generations=first))
    launch=funnel.read(root/'launch.json');report['launch']=launch
    if launch:
        assert re.fullmatch(r'\d+',launch['job'])
        raw=subprocess.check_output(['sacct','-X','-j',launch['job'],'-n','-P',
            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
        account=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==launch['job']]
        assert len(account)<=1
        report['accounting']=account
    print(json.dumps(report,allow_nan=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('which',choices=ROOTS);inspect(p.parse_args().which)
