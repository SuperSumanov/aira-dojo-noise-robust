"""Both allocations closed, all24 retained, trusted external grade + numeric check."""
import argparse,csv,json,math,os,statistics,subprocess
from pathlib import Path
from run_first_pool_replay_20260914 import BASE,prepared,read,checked,sha,write,source_check,setup,now
from readout_forets_generation_capacity_20260912 import numerical
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED','BOOT_FAIL','DEADLINE'}
def compare(a,b,task):
    if a['valid'] is None or b['valid'] is None:return None,None
    if a['valid'] and b['valid']:
        gain=(a['score']-b['score'])*(-1 if task=='leaf-classification' else 1)
        return (gain>0)-(gain<0),gain
    return int(a['valid'])-int(b['valid']),None
def run(root):
    p=prepared(root);source_check();launches=[read(root/f'launch-{b}.json') for b in (1,2)]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    acct=subprocess.check_output(['sacct','-X','-j',','.join(x['job'] for x in launches),'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
    allocations={x.split('|')[0]:x.split('|') for x in acct.splitlines()}
    for launch in launches:
        a=allocations[launch['job']]
        if a[1].split()[0].rstrip('+') not in TERMINAL or a[3]!='gpu28':raise ValueError('both allocations closed on gpu28 required')
        tres=dict(v.split('=',1) for v in a[4].split(','))
        if tres.get('gres/gpu')!='1':raise ValueError('singleGPU required')
    setup(root,p)
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(BASE/'mle-bench-data');answers={};rows=[];proofs={}
    for slot in p['rows']:
        i=slot['index'];row=dict(slot,valid=None,score=None,independent_score=None,status='not_started',wall_seconds=None)
        rp=root/f'result-{i}.json'
        if rp.exists():
            r=read(rp);proofs[rp.name]=sha(rp.read_bytes())
            if any(r[k]!=slot[k] for k in slot):raise ValueError('case binding')
            row.update(status=r['status'],wall_seconds=r['wall_seconds'])
            if r['status']=='returned':
                binding=root/f'identity-{i}.native-binding.json';b=read(binding,r['native_binding_sha256'])
                if not b['namespace']['exact_device_namespace']:raise ValueError('native GPU isolation')
                row['valid']=False
                if r['exit_code']==0 and not r['timed_out'] and r['submission_sha256'] is not None:
                    sub=root/f'work-{i}'/'submission.csv';checked(sub,r['submission_sha256'],False)
                    comp=registry.get_competition(slot['task']);valid,_=validate_submission(sub,comp)
                    if valid:
                        grade,_=evaluate_submission(sub,BASE/'mle-bench-data',slot['task'],root/f'grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if slot['task'] not in answers:answers[slot['task']]=pd.read_csv(comp.answers)
                            numeric=numerical(slot['task'],pd.read_csv(sub),answers[slot['task']])
                            if round(numeric,5)!=float(grade):raise ValueError('independent numerical grade')
                            row.update(valid=True,score=float(grade),independent_score=numeric)
                    checked(sub,r['submission_sha256'],False)
        rows.append(row)
    pairs=[]
    for policy in p['policies']:
        rr={r['slot']:r for r in rows if r['source_run_id']==policy['source_run_id']}
        if set(rr)!={0,1}:raise ValueError('all same-pool choices')
        outcomes={arm:rr[slot] for arm,slot in policy['choices'].items()};contrasts=[]
        for arm in ('short_code','learned_validity','class_gate'):
            for baseline in ('uniform','short_code','learned_validity'):
                if baseline==arm:continue
                sign,gain=compare(outcomes[arm],outcomes[baseline],policy['task'])
                contrasts.append(dict(arm=arm,baseline=baseline,sign=sign,gain=gain))
        observed=[(old,rr[slot]['valid']) for slot,old in enumerate(policy['original_initial_labels']) if old is not None and rr[slot]['valid'] is not None]
        pairs.append(dict(**policy,labels=[rr[i]['valid'] for i in (0,1)],grades=[rr[i]['score'] for i in (0,1)],contrasts=contrasts,
            original_known_retest=len(observed),original_validity_disagreements=sum(bool(a)!=b for a,b in observed)))
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        for arm in ('short_code','learned_validity','class_gate'):
            for baseline in ('uniform','short_code','learned_validity'):
                if baseline==arm:continue
                cc=[c for q in pairs if q['task']==task for c in q['contrasts'] if (c['arm'],c['baseline'])==(arm,baseline)]
                vv=[c['gain'] for c in cc if c['gain'] is not None]
                groups.append(dict(task=task,arm=arm,baseline=baseline,runs=len(cc),wins=sum(c['sign']==1 for c in cc),ties=sum(c['sign']==0 for c in cc),losses=sum(c['sign']==-1 for c in cc),unknown=sum(c['sign'] is None for c in cc),
                    conditional_both_valid_median_gain=statistics.median(vv) if vv else None,sample_sd_conditional_gain=statistics.stdev(vv) if len(vv)>1 else None))
    out=dict(role='posthoc_first_pool_full_information_replay_not_e2e',rows=rows,pairs=pairs,groups=groups,source_tree=p['source_tree'],prepared_sha256=sha((root/'prepared.json').read_bytes()),
        allocations=allocations,allocation_gpu_hours=sum(int(a[2]) for a in allocations.values())/3600,proofs=proofs,api_calls=0,models_fit=0,script_sha256=sha(Path(__file__).read_bytes()),
        limitation='All original first pools, not disagreement-selected. Replayed from clean workspaces without earlier artifacts; original chosen-code retest shown. No debug or later search. Missing infrastructure stays unknown; not independent causal E2E effect.')
    h=write(root/'summary.json',out)
    with (root/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(root/'readout-finished.json',dict(summary_sha256=h,csv_sha256=sha((root/'runs.csv').read_bytes()),utc=now()))
    print(json.dumps(dict(summary_sha256=h,groups=groups,valid=sum(r['valid'] is True for r in rows),unknown=sum(r['valid'] is None for r in rows))))
if __name__=='__main__':p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
