"""Close the fixed depth-two no-code case without inventing an execution job.

No grades, answers or private model text are read. A truncated draw remains
unknown, not an invalid executed solution. Only the allocation cost is known.
"""
import argparse,csv,hashlib,json,os,re,subprocess
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/comparison-depth2-debug-exec-20260919-126ifhtp')
PREPARED='a6cdef6122f7d5c4c693ac41c9e426e20ca1f0c2f30cfd3a3723528e96943834'

def build(prepared,generation,allocation):
    if prepared['gpus']!=0 or any(row['runnable'] for row in prepared['rows']):
        raise ValueError('runnable code requires normal execution, not this reader')
    if [row['seed'] for row in prepared['rows']]!=[1,2] or [row['request_seed'] for row in prepared['rows']]!=[601,602]:
        raise ValueError('fixed requests')
    if len(generation['rows'])!=2:raise ValueError('generation count')
    if allocation[0]!=prepared['generation_job'] or allocation[1]!='COMPLETED' or allocation[3]!='gpu28':
        raise ValueError('generation not closed on expected node')
    if dict(x.split('=',1) for x in allocation[4].split(','))['gres/gpu']!='2':raise ValueError('GPU count')
    elapsed=int(allocation[2])
    if elapsed!=prepared['generation_allocation_seconds'] or elapsed<0:raise ValueError('cost drift')
    rows=[]
    for original,generated in zip(prepared['rows'],generation['rows']):
        for key in ('seed','request_seed','generation_seconds'):
            if original[key]!=generated[key]:raise ValueError('generation identity')
        if original['run']!=generated['source_run'] or original['generation_status']!=generated['status']:
            raise ValueError('generation identity')
        if generated['status'] not in {'truncated','no_code','generation_failed'}:raise ValueError('unrunnable status')
        if generated['status']=='truncated' and generated['finish_reason']!='length':raise ValueError('truncation identity')
        rows.append(dict(original,valid=None,score=None,independent_score=None,wall_seconds=None,
                         execution_status='no_runnable_generation'))
    return dict(role='fresh_native_debug_draws_not_live_e2e',job=None,allocation_state='NOT_SUBMITTED_NO_RUNNABLE_CODE',
        prepared_sha256=PREPARED,rows=rows,execution_allocation_seconds=0,execution_gpus=0,execution_gpu_hours=0,
        generation_job=prepared['generation_job'],generation_allocation_seconds=elapsed,generation_gpus=2,
        generation_gpu_hours=elapsed*2/3600,total_gpu_hours=elapsed*2/3600,
        paid_api_calls=0,training=False,validity=0,no_valid_output=0,unknown=2,
        caveat='Both draws retained as unknown, not program failures. No GPU execution submitted, no retry, no response salvage and no effect claim.')

def main(reader_commit):
    if not re.fullmatch('[a-f0-9]{40}',reader_commit):raise ValueError('reader commit')
    import run_comparison_depth2_execute_20260919 as wrapper
    from run_comparison_live_debug_execute_20260919 import read,sha,write,now
    p=wrapper.check(ROOT)
    if sha((ROOT/'prepared.json').read_bytes())!=PREPARED:raise ValueError('prepared identity')
    if any((ROOT/name).exists() for name in ('launch.json','submit-intent.json','execution-claim.json','summary.json','runs.csv')):
        raise ValueError('execution or prior closeout exists; do not repeat')
    wrapper.configure()
    source=wrapper.execution.GEN
    generation=read(source/'generation-summary.json',p['generation_summary_sha256'])
    if read(source/'closed.json')['status']!='two_draws_closed':raise ValueError('generation closure')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',p['generation_job'],'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    allocation,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==p['generation_job']]
    result=build(p,generation,allocation)
    result.update(utc=now(),reader_commit=reader_commit,reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  generation_summary_sha256=p['generation_summary_sha256'])
    write(ROOT/'summary.json',result)
    with (ROOT/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({key for row in result['rows'] for key in row}))
        writer.writeheader();writer.writerows(result['rows'])
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True)
    main(parser.parse_args().reader_commit)
