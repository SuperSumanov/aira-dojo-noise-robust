"""Read all fresh debug executions only after their allocation is terminal."""
import argparse,csv,json,math,os,subprocess
from pathlib import Path
from run_comparison_live_debug_execute_20260919 import check,BASE,setup,source_check,read,write,sha,now
from readout_comparison_spooky_pool_20260919 import numerical


def main(root):
    p=check(root);source_check();job=read(root/'launch.json')['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    allocation,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if allocation[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'} or allocation[3]!='gpu28':raise ValueError('allocation not terminal')
    if dict(x.split('=',1) for x in allocation[4].split(','))['gres/gpu']!=str(p['gpus']):raise ValueError('GPU count')
    setup(root,p['commit'])
    import pandas as pd
    from mlebench.registry import registry
    from mlebench.grade import validate_submission
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    competition=registry.set_data_dir(BASE/'mle-bench-data').get_competition('spooky-author-identification')
    rows=[];devices=[];truth=None
    for original in p['rows']:
        i=original['index'];row=dict(original,valid=None,score=None,independent_score=None,wall_seconds=None,
                                   execution_status='not_started' if original['runnable'] else 'no_runnable_generation')
        path=root/f'result-{i}.json'
        if path.exists():
            record=read(path)
            if any(record[k]!=v for k,v in original.items()):raise ValueError('code/request identity')
            row.update(execution_status=record['status'],wall_seconds=record['wall_seconds'])
            if record['status']=='returned':
                binding=read(root/f'identity-{i}.native-binding.json',record['native_binding_sha256'])
                if binding['native_identity']['job']!=job or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('hardware binding')
                devices.append(binding['native_identity']['selected_uuid'])
                row.update(valid=False,exit_code=record['exit_code'],timed_out=record['timed_out'])
                if record['exit_code']==0 and not record['timed_out'] and record['submission_sha256']:
                    submission=root/f'work-{i}/submission.csv'
                    if submission.is_symlink() or sha(submission.read_bytes())!=record['submission_sha256']:raise ValueError('submission drift')
                    valid,_=validate_submission(submission,competition)
                    if valid:
                        grade,_=evaluate_submission(submission,BASE/'mle-bench-data','spooky-author-identification',root/f'grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if truth is None:truth=pd.read_csv(competition.answers)
                            numeric=numerical('spooky-author-identification',pd.read_csv(submission),truth)
                            if round(numeric,5)!=float(grade):raise ValueError('independent external grade differs')
                            row.update(valid=True,score=float(grade),independent_score=numeric)
                    if sha(submission.read_bytes())!=record['submission_sha256']:raise ValueError('submission changed during grading')
        rows.append(row)
    if len(devices)!=len(set(devices)):raise ValueError('distinct concurrent GPU devices')
    result=dict(role='fresh_native_debug_draws_not_live_e2e',utc=now(),job=job,allocation_state=allocation[1],
                prepared_sha256=sha((root/'prepared.json').read_bytes()),rows=rows,
                execution_allocation_seconds=int(allocation[2]),execution_gpus=p['gpus'],
                execution_gpu_hours=int(allocation[2])*p['gpus']/3600,
                generation_job=p['generation_job'],generation_allocation_seconds=p['generation_allocation_seconds'],
                generation_gpus=2,generation_gpu_hours=p['generation_allocation_seconds']*2/3600,
                total_gpu_hours=(int(allocation[2])*p['gpus']+p['generation_allocation_seconds']*2)/3600,
                paid_api_calls=0,training=False,
                validity=sum(r['valid'] is True for r in rows),no_valid_output=sum(r['valid'] is False for r in rows),
                unknown=sum(r['valid'] is None for r in rows),
                caveat='Two new requests on fixed development prefixes, not E2E or same-total-budget confirmation. No best-response selection. Generation failures are retained, never replaced.')
    write(root/'summary.json',result)
    with (root/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for r in rows for k in r}));writer.writeheader();writer.writerows(rows)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);main(parser.parse_args().root)
