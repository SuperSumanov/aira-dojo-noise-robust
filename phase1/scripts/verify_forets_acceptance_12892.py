"""One read-only independent receipt check, not a second model execution."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path('/research/d7/spc/yzyang4/forets-8b-acceptance-20260909-yhg2vq1o')
    finish_bytes=(root/'acceptance/finished.json').read_bytes()
    process_bytes=(root/'process/summary.json').read_bytes()
    finish,process=json.loads(finish_bytes),json.loads(process_bytes)
    assert finish['status']=='PASS' and finish['allocation_id']=='12892' and finish['model_loaded'] is True
    assert finish['entry_sha256']=='26ca7848f148ff184bf50d0738d58310eeaa4c952197a7c922ee7cb1f96ec4aa'
    assert finish['weights_sha256']=='bb0c6a1801cf0a753bb1f8aa1c923f9fcc7fff81fd654ae9d3a932ee280dfb74'
    assert finish['runtime_meta']['max_len']==16384 and finish['gpus']==1 and finish['batch_size']==1
    assert finish['local_http_requests']==2 and finish['generator_api_requests']==0
    assert finish['blocked_external_connection_attempts']==0 and finish['protected_data_read'] is False
    assert finish['versions']==dict(torch='2.11.0+cu128',transformers='4.57.1',accelerate='1.11.0',safetensors='0.5.3')
    assert process['status']=='completed' and process['returncode']==0
    assert process['term_sent'] is False and process['kill_sent'] is False
    rows=finish['observations']
    assert len(rows)==8
    assert {(x['seed'],x['fixture'],x['repetition']) for x in rows}=={
        (seed,fixture,rep) for seed in (6,7) for fixture in ('short','context_16k') for rep in (0,1)}
    assert all(math.isfinite(x['seconds']) and x['seconds']>0 for x in rows)
    assert all(x['encoded_tokens']==(16384 if x['fixture']=='context_16k' else 16) for x in rows)
    stats={}
    for fixture in ('short','context_16k'):
        times=[x['seconds'] for x in rows if x['fixture']==fixture]
        median,stdev=statistics.median(times),statistics.stdev(times)
        assert math.isclose(median,finish['median_seconds_by_fixture'][fixture],rel_tol=1e-12)
        assert math.isclose(stdev,finish['sample_stdev_seconds_by_fixture'][fixture],rel_tol=1e-12)
        stats[fixture]=dict(measurements=len(times),median_seconds=median,sample_stdev_seconds=stdev,
            by_seed={str(seed):dict(median_seconds=statistics.median([x['seconds'] for x in rows if x['fixture']==fixture and x['seed']==seed]),
                sample_stdev_seconds=statistics.stdev([x['seconds'] for x in rows if x['fixture']==fixture and x['seed']==seed])) for seed in (6,7)})
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    cmd=['sacct','-n','-P','-j','12892','--format=JobID,State,ExitCode,ElapsedRaw,AllocTRES,Start,End']
    result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30,check=True)
    records=[line.split('|') for line in result.stdout.splitlines() if line.strip()]
    allocation=[row for row in records if row[0]=='12892']
    step=[row for row in records if row[0]=='12892.0']
    assert len(allocation)==len(step)==1
    assert all(row[1]=='COMPLETED' and row[2]=='0:0' for row in records)
    row=allocation[0]
    assert dict(item.split('=') for item in row[4].split(','))['gres/gpu']=='1'
    seconds=int(row[3])
    assert 0<process['elapsed_seconds']<=seconds<20*60
    for relative in ('slurm-12892.out','slurm-12892.err','process/stdout.private.log','process/stderr.private.log'):
        text=(root/relative).read_text(errors='replace')
        assert not re.search(r'Traceback \(most recent call last\)|CUDA out of memory|OutOfMemoryError',text)
    check=dict(status='INDEPENDENT_ACCEPTANCE_RECEIPT_PASS',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        job_id='12892',slurm_records=records,allocation_seconds=seconds,allocation_gpu_hours=seconds/3600,
        process_seconds=process['elapsed_seconds'],model_load_seconds=finish['load_seconds'],
        observations=len(rows),local_http_requests=finish['local_http_requests'],timings=stats,
        max_peak_allocated_gib=max(x['peak_allocated_bytes'] for x in rows)/1024**3,
        max_peak_reserved_gib=max(x['peak_reserved_bytes'] for x in rows)/1024**3,
        saturated_observations=sum(x['sigmoid_saturated'] for x in rows),
        finished_sha256=hashlib.sha256(finish_bytes).hexdigest(),process_sha256=hashlib.sha256(process_bytes).hexdigest(),
        inference_executed_by_this_verifier=False,scientific_benefit_claim=False,
        limitation='Independent recomputation of receipts/scheduler/logs, not independent repeated inference; synthetic workloads only.')
    with args.output.open('x') as file:
        json.dump(check,file,indent=2,allow_nan=False)
        file.write('\n')
    print(json.dumps(check))


if __name__=='__main__':
    main()
