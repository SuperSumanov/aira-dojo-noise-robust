"""Closed original-selected program feasibility, not a scheduler effect."""
import argparse,csv,json,math,os,re,subprocess,sys
from pathlib import Path
import run_comparison_pizza_selected_second_20260919 as wrapper
from readout_comparison_pizza_online_20260919 import numerical
ROOT=wrapper.driver.BASE/'comparison-pizza-selected-second-20260919-u2nkqs5y'
EXPECTED='51f32ba6bc25e6e25a58f8a1f8c4594206c2780c6cdcc5c9cbdd96b6e4400103'

def main(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('reader commit')
    wrapper.configure();driver=wrapper.driver;old=driver.old;p=driver.prepared(ROOT)
    if old.sha((ROOT/'prepared.json').read_bytes())!=EXPECTED:raise ValueError('prepared identity')
    job=old.read(ROOT/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    account,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if account[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY'}:raise ValueError('allocation active')
    if account[3]!='gpu28' or dict(x.split('=',1) for x in account[4].split(','))['gres/gpu']!='2':raise ValueError('hardware/resources')
    old.write(ROOT/'readout-claim.json',dict(commit=commit,reader_sha256=old.sha(Path(__file__).read_bytes()),utc=old.now()))
    old.setup(ROOT,p['commit'])
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    import pandas as pd
    comp=registry.set_data_dir(old.BASE/'mle-bench-data').get_competition(driver.TASK);truth=None;rows=[];devices=[]
    for original in p['rows']:
        i=original['index'];row={k:original[k] for k in ('index','seed','run','node','task','raw_code_sha256','code_sha256')}
        row.update(status='unknown',valid=None,score=None,independent_score=None)
        path=ROOT/f'result-{i}.json'
        if path.exists():
            result=old.read(path)
            if any(result[k]!=v for k,v in original.items()):raise ValueError('row identity')
            row.update(status=result['status'],wall_seconds=result['wall_seconds'])
            if result['status']=='returned':
                binding=old.read(ROOT/f'identity-{i}.native-binding.json',result['native_binding_sha256'])
                if binding['native_identity']['job']!=job or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('isolation')
                devices.append(binding['native_identity']['selected_uuid']);row.update(valid=False,exit_code=result['exit_code'],timed_out=result['timed_out'],execution_seconds=result['execution_seconds'])
                if result['exit_code']==0 and not result['timed_out'] and result['submission_sha256']:
                    path=ROOT/f'work-{i}/submission.csv'
                    if path.is_symlink() or old.sha(path.read_bytes())!=result['submission_sha256']:raise ValueError('submission drift')
                    valid,_=validate_submission(path,comp)
                    if valid:
                        grade,_=evaluate_submission(path,old.BASE/'mle-bench-data',driver.TASK,ROOT/f'closed-grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if truth is None:truth=pd.read_csv(comp.answers)
                            numeric=numerical(driver.TASK,pd.read_csv(path),truth)
                            if round(numeric,5)!=float(grade):raise ValueError('independent AUC mismatch')
                            row.update(valid=True,score=float(grade),independent_score=numeric)
                    if old.sha(path.read_bytes())!=result['submission_sha256']:raise ValueError('submission mutated')
        rows.append(row)
    if len(set(devices))!=len(devices):raise ValueError('worker device overlap')
    out=dict(role='fixed_original_selected_sibling_feasibility_not_policy_gain',job=job,commit=p['commit'],prepared_sha256=EXPECTED,
        reader_commit=commit,reader_sha256=old.sha(Path(__file__).read_bytes()),utc=old.now(),rows=rows,
        allocation_state=account[1],allocation_seconds=int(account[2]),gpu_hours=int(account[2])*2/3600,api_calls=0,
        valid=sum(r['valid'] is True for r in rows),invalid=sum(r['valid'] is False for r in rows),unknown=sum(r['valid'] is None for r in rows),
        native_analyze_not_yet_tested=True,not_an_e2e_result=True)
    old.write(ROOT/'summary.json',out)
    with (ROOT/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for r in rows for k in r}));writer.writeheader();writer.writerows(rows)
    print(json.dumps(out,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reader-commit',required=True);main(parser.parse_args().reader_commit)
