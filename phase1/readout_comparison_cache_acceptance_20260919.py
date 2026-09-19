"""Close native acceptance component without turning it into search utility."""
import argparse,csv,hashlib,json,math,os,re,subprocess
from pathlib import Path
from run_comparison_cache_acceptance_20260919 import configure,runtime,BASE,BANKS

def join_rows(cases,analyses,banks):
    if [c['request_seed'] for c in cases]!=list(range(801,809)):raise ValueError('fixed request matrix')
    if len({(c['run'],c['node']) for c in cases})!=8:raise ValueError('unique eight candidates')
    if len({r['index'] for r in analyses})!=len(analyses):raise ValueError('duplicate analysis')
    lookup={r['index']:r for r in analyses};out=[]
    if set(lookup)-{c['index'] for c in cases}:raise ValueError('unexpected analysis')
    for case in cases:
        source,=[r for r in banks[case['seed']]['rows'] if r['node']==case['node'] and r['run']==case['run']]
        if source['role']!='cache' or source['code_sha256']!=case['code_sha256']:raise ValueError('source match')
        row={k:case[k] for k in ('index','seed','request_seed','run','node','code_sha256','log_sha256')}
        analysis=lookup.get(case['index'])
        row.update(status='not_started',native_acceptance=None,official_valid=source['valid'])
        if analysis is not None:
            if any(analysis[k]!=case[k] for k in row if k in case):raise ValueError('analysis identity')
            row.update(status=analysis['status'],analysis_seconds=analysis['analysis_seconds'])
            if not math.isfinite(row['analysis_seconds']) or row['analysis_seconds']<0:raise ValueError('analysis cost')
            if analysis['status']=='analysis_returned':
                metric=analysis['native_metric'];bug=analysis['native_is_bug']
                if type(bug) is not bool or (metric is not None and (type(metric) not in (float,int) or not math.isfinite(metric))):raise ValueError('native schema')
                accepted=not bug and case['exit_code']==0 and not case['timed_out'] and metric is not None
                if analysis['would_accept_without_grader_guard'] is not accepted:raise ValueError('acceptance equation')
                row.update(native_acceptance=accepted,native_is_bug=bug,native_metric=metric,
                    accepted_with_external_validity_guard=accepted and source['valid'] is True)
        out.append(row)
    return out

def main(root,reader_commit):
    if not re.fullmatch('[a-f0-9]{40}',reader_commit):raise ValueError('reader commit')
    configure(root);p=runtime.check_files();job=runtime.read(root/'launch.json')['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    text=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    a,=[line.split('|') for line in text.splitlines() if line.split('|')[0]==job]
    if a[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'} or a[3]!='gpu28':raise ValueError('terminal allocation')
    if dict(item.split('=',1) for item in a[4].split(','))['gres/gpu']!='2':raise ValueError('GPU count')
    banks={}
    for seed,(path,digest) in BANKS.items():
        raw=(path/'summary.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest or runtime.SHAPES.search(raw):raise ValueError('source bank identity/security')
        banks[seed]=json.loads(raw)
    cases=runtime.read(root/'inputs.private.json')['cases']
    analyses=[runtime.read(root/f'analysis-{i}.json') for i in range(8) if (root/f'analysis-{i}.json').exists()]
    if analyses:
        service=runtime.read(root/'service-native.json')
        if service['job']!=job or len(set(service['uuid']))!=2:raise ValueError('native service binding')
    rows=join_rows(cases,analyses,banks)
    summary=dict(role='native_cache_acceptance_component_not_e2e',job=job,allocation_state=a[1],
        generation_commit=p['commit'],reader_commit=reader_commit,reader_sha256=runtime.sha(Path(__file__)),
        prepared_sha256=runtime.sha(root/'prepared.json'),allocation_seconds=int(a[2]),gpu_hours=int(a[2])*2/3600,
        source_summary_sha256={str(seed):digest for seed,(_,digest) in BANKS.items()},
        rows=rows,planned=8,returned=sum(r['native_acceptance'] is not None for r in rows),
        unknown=sum(r['native_acceptance'] is None for r in rows),
        officially_valid=sum(r['official_valid'] is True for r in rows),
        valid_and_accepted=sum(r['official_valid'] is True and r['native_acceptance'] is True for r in rows),
        invalid_but_accepted_without_guard=sum(r['official_valid'] is False and r['native_acceptance'] is True for r in rows),
        valid_rejected=sum(r['official_valid'] is True and r['native_acceptance'] is False for r in rows),
        valid_unknown=sum(r['official_valid'] is True and r['native_acceptance'] is None for r in rows),
        paid_api_calls=0,training=False,
        caveat='Native analysis of already executed fixed development caches. External validity used only after inference. Not a full search, randomized E2E effect, or latency gain.')
    runtime.write(root/'summary.json',summary)
    with (root/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for row in rows for k in row}));writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('--reader-commit',required=True);args=parser.parse_args();main(args.root,args.reader_commit)
