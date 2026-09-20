"""Terminal-allocation readout; all predictions fixed before any fresh execution."""
import argparse,csv,itertools,json,math,os,re,statistics,subprocess
from pathlib import Path
from run_comparison_pizza_transfer_20260920 import prepared,base,rt,TASK,SEEDS
from comparison_auc_20260920 import numerical

def analyze(rows):
    if len(rows)!=6 or sorted(r['slot'] for r in rows)!=list(range(6)) or len({r['node'] for r in rows})!=6:raise ValueError('complete pool')
    if any(r['valid'] is None for r in rows):return dict(status='UNKNOWN_NO_EFFECT_CLAIM')
    if any(type(r['reward']) not in (int,float) or not math.isfinite(r['reward']) for r in rows):raise ValueError('finite reward')
    ranked=sorted(rows,key=lambda r:(-r['reward'],r['slot']));uniform=list(itertools.combinations(rows,2))
    policies={'uniform_two_of_six':uniform,'frozen_top_two':[tuple(ranked[:2])],'frozen_top_three_then_uniform_two':list(itertools.combinations(ranked[:3],2))}
    def best(pair):
        values=[r['score'] for r in pair if r['valid']]
        return max(values) if values else None
    def compare(a,b):
        if a is None:return 0 if b is None else -1
        if b is None:return 1
        return (a>b)-(a<b)
    output={}
    for name,pairs in policies.items():
        values=[best(pair) for pair in pairs];valid=[v for v in values if v is not None]
        signs=[compare(v,best(b)) for v in values for b in uniform]
        output[name]=dict(choices=len(pairs),probability_any_valid=len(valid)/len(values),mean_oracle_auc_given_valid=statistics.mean(valid) if valid else None,
            wins=signs.count(1),ties=signs.count(0),losses=signs.count(-1),net_preference=statistics.mean(signs))
    return dict(status='COMPLETE_ORACLE_DIAGNOSTIC_NOT_FINAL_CHOICE',valid_candidates=sum(r['valid'] for r in rows),critic_order=[r['slot'] for r in ranked],policies=output)

def main(root,commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or commit=='0'*40:raise ValueError('commit')
    p=prepared(root);base.source_check();job=base.read(root/'launch.json')['job']
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    a,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if a[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY'} or a[3]!='gpu28' or not re.search(r'(?:^|,)gres/gpu=6(?:,|$)',a[4]):raise ValueError('closed intended allocation')
    if base.read(root/'prediction-complete.json')['cases']!=12:raise ValueError('all twelve predictions before execution')
    predictions=[base.read(root/f'prediction-{i}.json') for i in range(12)]
    for seed in SEEDS:
        if (root/f'pool-start-{seed}.json').exists() and base.read(root/f'pool-start-{seed}.json')['utc']<base.read(root/'prediction-complete.json')['utc']:raise ValueError('execution before predictions')
    base.write(root/'readout-claim.json',dict(utc=base.now(),reader_commit=commit,reader_sha256=rt.sha(Path(__file__)),prepared_sha256=rt.sha(root/'prepared.json')))
    base.setup(root,p['commit'])
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    import pandas as pd
    comp=registry.set_data_dir(base.BASE/'mle-bench-data').get_competition(TASK);truth=None;rows=[];devices={}
    for original,prediction in zip(p['rows'],predictions):
        if any(original[k]!=prediction[k] for k in original):raise ValueError('prediction identity')
        i=original['index'];row=dict(original,reward=prediction['reward'],inference_seconds=prediction['inference_seconds'],status='not_started',valid=None,score=None,independent_score=None,wall_seconds=None)
        path=root/f'result-{i}.json'
        if path.exists():
            result=base.read(path)
            if any(result[k]!=v for k,v in original.items()):raise ValueError('execution identity')
            row.update(status=result['status'],wall_seconds=result['wall_seconds'])
            if result['status']=='returned':
                binding=base.read(root/f'identity-{i}.native-binding.json',result['native_binding_sha256'])
                if binding['native_identity']['job']!=job or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('task isolation')
                devices.setdefault(row['seed'],[]).append(binding['native_identity']['selected_uuid'])
                row.update(valid=False,exit_code=result['exit_code'],timed_out=result['timed_out'],execution_seconds=result['execution_seconds'])
                if result['exit_code']==0 and not result['timed_out'] and result['submission_sha256']:
                    sub=root/f'work-{i}/submission.csv'
                    if sub.is_symlink() or rt.sha(sub)!=result['submission_sha256']:raise ValueError('submission drift')
                    valid,_=validate_submission(sub,comp)
                    if valid:
                        grade,_=evaluate_submission(sub,base.BASE/'mle-bench-data',TASK,root/f'closed-grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if truth is None:truth=pd.read_csv(comp.answers,float_precision='round_trip')
                            numeric=numerical(pd.read_csv(sub,float_precision='round_trip'),truth)
                            if round(numeric,5)!=float(grade):raise ValueError('independent rank AUC mismatch')
                            row.update(valid=True,score=float(grade),independent_score=numeric)
                    if rt.sha(sub)!=result['submission_sha256']:raise ValueError('submission mutated')
        rows.append(row)
    if any(len(values)!=len(set(values)) for values in devices.values()):raise ValueError('concurrent worker overlap')
    output=dict(role='third_task_frozen_critic_complete_development_pool_diagnostic',utc=base.now(),job=job,allocation_state=a[1],allocation_seconds=int(a[2]),
        gpu_hours=int(a[2])*6/3600,api_calls=0,training=False,deployment_commit=p['commit'],reader_commit=commit,prepared_sha256=rt.sha(root/'prepared.json'),
        model=p['model'],encoder=base.read(root/'model-ready.json'),rows=rows,pools=[dict(seed=seed,**analyze([r for r in rows if r['seed']==seed])) for seed in SEEDS],
        valid=sum(r['valid'] is True for r in rows),invalid=sum(r['valid'] is False for r in rows),unknown=sum(r['valid'] is None for r in rows),
        full_e2e=False,independent_confirmation=False,final_native_selection_tested=False)
    digest=base.write(root/'summary.json',output)
    with (root/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in output.items() if k not in ('rows','model')}|dict(summary_sha256=digest,runs_sha256=rt.sha(root/'runs.csv')),allow_nan=False))

if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--reader-commit',required=True);a=p.parse_args();main(a.root,a.reader_commit)
