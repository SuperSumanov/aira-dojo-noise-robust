"""Closed-allocation full-pool development diagnostic, not deployable selection."""
import argparse,csv,itertools,json,math,os,statistics,subprocess
from pathlib import Path
from run_comparison_spooky_pool_20260919 import BASE,prepared,read,write,sha,setup,source_check,now

def pairs_summary(rows):
    if len(rows)!=6 or len({r['slot'] for r in rows})!=6 or sum(r['original_selected'] for r in rows)!=2:
        raise ValueError('complete unique six-candidate pool required')
    if any(r['valid'] is None for r in rows):return dict(status='UNKNOWN_NO_EFFECT_CLAIM')
    for r in rows:
        if r['valid'] and (type(r['score']) not in (float,int) or not math.isfinite(r['score'])):raise ValueError('finite valid score')
    def best(pair):
        values=[r['score'] for r in pair if r['valid']]
        return min(values) if values else None
    original=[r for r in rows if r['original_selected']];chosen=best(original)
    alternatives=list(itertools.combinations(rows,2));wins=ties=losses=0;conditional=[]
    for pair in alternatives:
        other=best(pair)
        if chosen is None and other is None:sign=0
        elif chosen is None:sign=-1
        elif other is None:sign=1
        else:
            sign=(other>chosen)-(other<chosen);conditional.append(other-chosen)
        wins+=sign>0;ties+=sign==0;losses+=sign<0
    all_valid=[r['score'] for r in rows if r['valid']]
    return dict(status='COMPLETE_EXPLORATORY_POOL',candidates=6,valid=sum(r['valid'] for r in rows),
        selected_valid=sum(r['valid'] for r in original),uniform_expected_valid=sum(sum(r['valid'] for r in p) for p in alternatives)/15,
        selected_has_valid=chosen is not None,uniform_probability_any_valid=sum(best(p) is not None for p in alternatives)/15,
        selected_oracle_best=chosen,pool_oracle_best=min(all_valid) if all_valid else None,
        selected_vs_all_uniform_pairs=dict(wins=wins,ties=ties,losses=losses,pairs=len(alternatives)),
        conditional_both_pairs_valid_mean_oriented_gain=statistics.mean(conditional) if conditional else None,
        limitation='Best-of-two is post-execution oracle diagnostic; not final selection policy or E2E effect.')


def numerical(task,pred,truth):
    import numpy as np
    if task!='spooky-author-identification':raise ValueError('task')
    idcol='id';columns=['EAP','HPL','MWS']
    if set(pred.columns)!=set(columns+[idcol]) or set(truth.columns)!=set(columns+[idcol]):raise ValueError('columns')
    if (pred[idcol].duplicated().any() or truth[idcol].duplicated().any() or pred[idcol].isna().any()
        or truth[idcol].isna().any() or set(pred[idcol])!=set(truth[idcol]) or len(truth)==0):raise ValueError('ids')
    p=pred.set_index(idcol).sort_index()[columns].to_numpy(dtype=float)
    y=truth.set_index(idcol).sort_index()[columns].to_numpy(dtype=float)
    if not np.isfinite(p).all() or not ((p>=0)&(p<=1)).all() or not np.allclose(p.sum(axis=1),1,rtol=1e-5,atol=1e-6):raise ValueError('probabilities')
    if not ((y==0)|(y==1)).all() or not (y.sum(axis=1)==1).all():raise ValueError('onehot')
    p=np.clip(p,np.finfo(float).eps,1-np.finfo(float).eps)
    return float(-np.mean(np.sum(y*np.log(p),axis=1)))

def main(root):
    p=prepared(root);source_check();launch=read(root/'launch.json');job=launch['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    account=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    lines=[x.split('|') for x in account.splitlines() if x.split('|')[0]==job]
    if len(lines)!=1:raise ValueError('allocation identity')
    a=lines[0];terminal={'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}
    if a[1].split()[0].rstrip('+') not in terminal or a[3]!='gpu28':raise ValueError('allocation not closed on intended node')
    tres=dict(v.split('=',1) for v in a[4].split(','))
    if tres.get('gres/gpu')!='6':raise ValueError('allocated GPU count')
    setup(root,p['commit'])
    import pandas as pd
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    comp=registry.set_data_dir(BASE/'mle-bench-data').get_competition('spooky-author-identification')
    truth=None;rows=[]
    for original in p['rows']:
        i=original['index'];r=dict(original,status='not_started',valid=None,score=None,independent_score=None,wall_seconds=None)
        path=root/f'result-{i}.json'
        if path.exists():
            value=read(path)
            if any(value[k]!=v for k,v in original.items()):raise ValueError('row identity')
            r.update(status=value['status'],wall_seconds=value['wall_seconds'])
            if value['status']=='returned':
                b=read(root/f'identity-{i}.native-binding.json',value['native_binding_sha256'])
                if b['native_identity']['job']!=job or b['namespace']['exact_device_namespace'] is not True:raise ValueError('native allocation binding')
                r.update(valid=False,exit_code=value['exit_code'],timed_out=value['timed_out'])
                if value['exit_code']==0 and not value['timed_out'] and value['submission_sha256']:
                    sub=root/f'work-{i}/submission.csv'
                    if sub.is_symlink() or sha(sub.read_bytes())!=value['submission_sha256']:raise ValueError('submission changed')
                    valid,_=validate_submission(sub,comp)
                    if valid:
                        grade,_=evaluate_submission(sub,BASE/'mle-bench-data','spooky-author-identification',root/f'grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if truth is None:truth=pd.read_csv(comp.answers)
                            numeric=numerical('spooky-author-identification',pd.read_csv(sub),truth)
                            if round(numeric,5)!=float(grade):raise ValueError('independent numerical mismatch')
                            r.update(valid=True,score=float(grade),independent_score=numeric)
                    if sha(sub.read_bytes())!=value['submission_sha256']:raise ValueError('submission changed after grading')
        rows.append(r)
    pools=[dict(seed=s,**pairs_summary([r for r in rows if r['seed']==s])) for s in (1,2,3)]
    result=dict(utc=now(),role='complete_initial_pool_exploration_not_e2e',job=job,allocation_state=a[1],
        allocation_seconds=int(a[2]),allocated_gpus=6,gpu_hours=int(a[2])*6/3600,api_calls=0,
        prepared_sha256=sha((root/'prepared.json').read_bytes()),rows=rows,pools=pools,
        valid=sum(r['valid'] is True for r in rows),program_failure=sum(r['valid'] is False for r in rows),
        unknown=sum(r['valid'] is None for r in rows))
    write(root/'summary.json',result)
    keys=sorted({k for r in rows for k in r})
    with (root/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);main(parser.parse_args().root)
