"""Read-only numeric diagnostics; never modifies a frozen experiment or gate."""
import argparse,ast,contextlib,io,json,re,statistics,subprocess,os
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

def identities(root,block):
    service=funnel.read(root/f'block-{block}/service-native.json')
    lanes=[funnel.read(root/f'block-{block}/lane-{i}-native.json') for i in range(4)]
    workers=[funnel.read(root/f'episode-{block*8+i}/native.json') for i in range(8)]
    if not service or not all(lanes) or not all(workers):return dict(complete=False)
    def physical(x):return {(r['socket'],r['core']) for r in x['cpu_topology']}
    groups=[physical(x) for x in lanes]+[physical(service)]
    gpu_sets=[{x['gpu_uuid']} for x in lanes]+[set(service['gpu_uuids'])]
    valid=(len(groups[-1])==8 and len(gpu_sets[-1])==2
        and all(len(g)==4 for g in groups[:4])
        and all(not groups[i]&groups[j] and not gpu_sets[i]&gpu_sets[j] for i in range(5) for j in range(i))
        and all(w['job']==lanes[i//2]['job']==service['job'] and w['step']==lanes[i//2]['step']
                and w['gpu_uuids']==[lanes[i//2]['gpu_uuid']] for i,w in enumerate(workers)))
    cleanup=funnel.read(root/f'block-{block}/service-cleanup.json')
    return dict(complete=True,independent_identity_check=valid,
        service_cleanup_verified=cleanup.get('gpu_clean') if cleanup else None,
        lane_devices=[x['gpu_uuid'] for x in lanes],service_devices=service['gpu_uuids'])

def inspect(which):
    path,pin=ROOTS[which];root=Path(path);funnel.ROOT=root;funnel.PIN=pin
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf):funnel.summarize()
    report=json.loads(buf.getvalue());report['pools']=[];report['native_usage']=[];report['native_syntax']=[]
    for row in report['rows']:
        for ordinal,node in enumerate(funnel.events(root/f"episode-{row['index']}/checkpoint/journal.jsonl")):
            code=node.get('code') or ''
            try:ast.parse(code);parseable=bool(code.strip())
            except (SyntaxError,ValueError):parseable=False
            terminal=node.get('term_out') or node.get('_term_out') or ''
            if isinstance(terminal,list):terminal='\n'.join(str(x) for x in terminal)
            flags={name:bool(re.search(r'(?<![A-Za-z_])'+name+r'\b',str(terminal))) for name in
                ('SyntaxError','IndentationError','NameError','KeyError','FileNotFoundError','ModuleNotFoundError','RuntimeError','TypeError','ValueError','OutOfMemoryError')}
            report['native_syntax'].append(dict(index=row['index'],node_ordinal=ordinal,
                nonempty_code=bool(code.strip()),ast_parseable=parseable,exit_code=node.get('exit_code'),error_flags=flags))
            roles=node.get('operators_used',[])
            for j,metric in enumerate(node.get('operators_metrics',[])):
                usage=metric.get('usage',{})
                numeric={k:v for k,v in usage.items() if k in ('prompt_tokens','completion_tokens','total_tokens','latency') and type(v) in (int,float)}
                role=roles[j] if j<len(roles) and roles[j] in ('draft','debug','improve','analyze','crossover') else 'unmapped'
                report['native_usage'].append(dict(index=row['index'],node_ordinal=ordinal,operator_ordinal=j,role=role,usage=numeric))
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
        report['pools'].append(dict(block=bd.name,identity=identities(root,int(bd.name.split('-')[1])),service_ready=funnel.read(bd/'service-ready.json'),
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
    p=argparse.ArgumentParser();p.add_argument('which',choices=ROOTS);p.add_argument('--verify-scores',action='store_true');args=p.parse_args()
    if args.verify_scores:
        path,pin=ROOTS[args.which];funnel.ROOT=Path(path);funnel.PIN=pin;funnel.verify_available_scores()
    else:inspect(args.which)
