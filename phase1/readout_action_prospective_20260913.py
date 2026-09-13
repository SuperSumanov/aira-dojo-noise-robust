"""One closed readout: actual same-trajectory delivery, no outcome reselection."""
import argparse
from contextlib import closing
import csv
import datetime as dt
import json
import math
import os
from pathlib import Path
import statistics
import sqlite3
import sys
from forets_environment_build_20260912 import read,write,encode,sha
from read_forets_action_delivery_20260913 import read_latest

FILES=('readout_action_prospective_20260913.py','readout_action_prospective_core_20260913.py',
    'read_forets_action_delivery_20260913.py','readout_forets_generation_capacity_20260912.py','verify_branching_selection_20260913.py')

def paired_effects(rows):
    if len(rows)!=8 or {(r['task'],r['seed']) for r in rows}!={(t,s) for t in ('leaf-classification','spaceship-titanic') for s in (34,35,36,37)}:
        raise ValueError('all planned distinct runs')
    for r in rows:
        flags=('technical_eligible','primary_valid','action_valid','quality_comparable')
        if any(type(r[k]) is not bool for k in flags):raise ValueError('Boolean eligibility required')
        if r['quality_comparable'] is not (r['technical_eligible'] and r['primary_valid'] and r['action_valid']):raise ValueError('paired eligibility')
        v=r['action_oriented_gain']
        if r['quality_comparable']:
            if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('finite paired effect')
        elif v is not None:raise ValueError('missing effect must remain missing')
    groups=[]
    for task in ('leaf-classification','spaceship-titanic'):
        rs=[r for r in rows if r['task']==task];values=[r['action_oriented_gain'] for r in rs if r['quality_comparable']]
        groups.append(dict(task=task,runs=len(rs),quality_comparable=len(values),wins=sum(v>0 for v in values),
            ties=sum(v==0 for v in values),losses=sum(v<0 for v in values),
            median_gain=statistics.median(values) if values else None,sample_std_gain=statistics.stdev(values) if len(values)>1 else None,
            primary_missing_action_valid=sum(r['technical_eligible'] and not r['primary_valid'] and r['action_valid'] for r in rs),
            primary_valid_action_missing=sum(r['technical_eligible'] and r['primary_valid'] and not r['action_valid'] for r in rs)))
    return groups

def main(root):
    root=root.resolve(strict=True);build=read(root/'build.json');plan=read(root/'readout-plan.json')
    if (plan['root'],plan['source_tree'],plan['prepared_sha256'])!=(str(root),build['source_tree'],build['prepared_sha256']):raise ValueError('frozen binding')
    for f,h in plan['readers'].items():
        if sha(Path(__file__).with_name(f).read_bytes())!=h:raise ValueError('reader drift')
    write(root/'readout-intent.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),readout_plan_sha256=sha((root/'readout-plan.json').read_bytes()))))
    import readout_action_prospective_core_20260913 as core
    core.verify(root,seeds=(34,35,36,37),blocks=(1,2))
    original=read(root/'wallclock-summary.json');prepared=read(root/'prepared.json',build['prepared_sha256'])
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(root.parent/'mle-bench-data');answers={};rows=[];proof=[];policy_replays=[]
    from verify_branching_selection_20260913 import verify_pool
    for r in original['rows']:
        cfg_row=next(p for p in prepared['run_configs'] if p['run_id']==r['run_id'])
        cfg=read(root/'configs'/(r['run_id']+'.json'),cfg_row['config_sha256'])
        if cfg['solver']['selection_policy']!='uniform_random':raise ValueError('not planned uniform policy')
        cp=Path(cfg['solver']['checkpoint_path'])
        if list((cp/'forets-contextual-judge-private').glob('batch-*/request-*.json')):raise ValueError('unexpected ranking request')
        for p in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(p.read_bytes())
            with closing(sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)) as db:
                payload,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(payload.encode())!=digest or sha(p.read_bytes())!=before:raise ValueError('pool snapshot drift')
            replay=verify_pool(json.loads(payload),cfg['solver'],r)
            policy_replays.append(dict(run_id=r['run_id'],pool=p.name,sha256=before,**replay))
        row=dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],source_tree=build['source_tree'],controller_commit=build['commit'],job=r['job'],
            search_policy='uniform_random',search_budget_seconds=600,program_timeout_seconds=300,
            technical_eligible=r['technical_eligible'],termination_reason=r['termination_reason'],
            primary_valid=r['valid'],primary_score=r['score'],primary_code_sha256=r['selected_code_sha256'],
            action_valid=False,action_score=None,action_code_sha256=None,action_number=None,action_elapsed_seconds=None,
            selected_submission_differs=None,quality_comparable=False,action_oriented_gain=None,
            api_cost_usd=r['api_cost_usd'],new_critic_calls=0)
        if r['search_start_ns'] is not None:
            base=root/'incumbents'/r['run_id'];data=read_latest(base,start_ns=r['search_start_ns'],seconds=600)
            if data is not None and data['submission'] is not None:
                receipt=data['submission'];archive=Path(receipt['archive_dir'])
                expected=Path(cfg['task']['results_output_dir'])/'submission-escrow'
                if archive.is_symlink() or archive.parent.resolve()!=expected.resolve():raise ValueError('action archive path')
                complete=read(archive/'complete.json')
                if any(receipt.get(k)!=v for k,v in complete.items()):raise ValueError('action execution binding')
                for name,key in (('submission.csv','submission_sha256'),('report.json','report_sha256')):
                    if sha((archive/name).read_bytes())!=receipt[key]:raise ValueError('action submission hash')
                report=read(archive/'report.json')
                if report['valid_submission'] is not True:raise ValueError('chosen action invalid')
                if r['task'] not in answers:answers[r['task']]=pd.read_csv(registry.get_competition(r['task']).answers)
                independent=core.numerical(r['task'],pd.read_csv(archive/'submission.csv'),answers[r['task']])
                if round(independent,5)!=report['score']:raise ValueError('independent action grade differs')
                row.update(action_valid=True,action_score=report['score'],action_code_sha256=receipt['code_sha256'],
                    action_number=data['action'],action_elapsed_seconds=(data['observation_ns']-data['start_ns'])/1e9,
                    selected_submission_differs=receipt['code_sha256']!=r['selected_code_sha256'])
                proof.append(dict(run_id=r['run_id'],action=data['action'],submission_sha256=receipt['submission_sha256'],report_sha256=receipt['report_sha256']))
        row['quality_comparable']=row['technical_eligible'] and row['primary_valid'] and row['action_valid']
        if row['quality_comparable']:
            row['action_oriented_gain']=(row['primary_score']-row['action_score']) if row['task']=='leaf-classification' else row['action_score']-row['primary_score']
        rows.append(row)
    result=dict(role='prospective_same_trajectory_delivery_not_critic_efficacy',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        rows=rows,groups=paired_effects(rows),source_tree=build['source_tree'],controller_commit=build['commit'],
        original_summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),proofs=proof,policy_replays=policy_replays,
        allocation_gpu_hours=original['allocation_gpu_hours'],billing=original['billing'],
        limitation='Two tasks/four new seeds. Both outputs share actual execution and recording overhead; not independent searches, no zero-overhead counterfactual, no oracle selection or algorithm/scaling claim.')
    result_sha=write(root/'action-delivery-summary.json',encode(result))
    with (root/'action-delivery-runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    finish=dict(status='verified',utc=result['utc'],source_tree=build['source_tree'],files={n:sha((root/n).read_bytes()) for n in
        ('wallclock-summary.json','wallclock-runs.csv','action-delivery-summary.json','action-delivery-runs.csv')})
    write(root/'readout-finished.json',encode(finish));print(json.dumps(dict(summary_sha256=result_sha,groups=result['groups'],allocation_gpu_hours=result['allocation_gpu_hours'])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();os.umask(0o077);main(a.root)
