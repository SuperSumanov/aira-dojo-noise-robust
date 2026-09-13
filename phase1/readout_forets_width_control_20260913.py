"""Closed eight-run width comparison; action primary, iteration secondary."""
import argparse
from contextlib import closing
import csv
import datetime as dt
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import sys
from forets_environment_build_20260912 import read,write,encode,sha
from read_forets_action_delivery_20260913 import read_latest

TASKS=('leaf-classification','spaceship-titanic')
ARMS=('batch_four','direct_two')
SEEDS=(38,39)
FILES=('readout_forets_width_control_20260913.py','readout_width_core_20260913.py',
    'read_forets_action_delivery_20260913.py','readout_forets_generation_capacity_20260912.py','verify_branching_selection_20260913.py')

def paired_effects(rows):
    if len(rows)!=8 or {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in TASKS for s in SEEDS for a in ARMS}:
        raise ValueError('all eight distinct planned searches required')
    for r in rows:
        for k in ('technical_eligible','action_valid','iteration_valid'):
            if type(r[k]) is not bool:raise ValueError('Boolean eligibility required')
        for endpoint in ('action','iteration'):
            v=r[endpoint+'_score']
            if r[endpoint+'_valid']:
                if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('finite valid score')
            elif v is not None:raise ValueError('missing cannot be imputed')
    pairs=[];groups=[]
    for endpoint in ('action','iteration'):
        for task in TASKS:
            vals=[]
            for seed in SEEDS:
                a,b=[next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm)) for arm in ARMS]
                technical=a['technical_eligible'] and b['technical_eligible']
                comparable=technical and a[endpoint+'_valid'] and b[endpoint+'_valid']
                gain=((a[endpoint+'_score']-b[endpoint+'_score']) if task==TASKS[0] else (b[endpoint+'_score']-a[endpoint+'_score'])) if comparable else None
                pairs.append(dict(endpoint=endpoint,task=task,seed=seed,technical_comparable=technical,quality_comparable=comparable,
                    batch_valid=a[endpoint+'_valid'],direct_valid=b[endpoint+'_valid'],direct_oriented_gain=gain,
                    direct_minus_batch_api_usd=b['api_cost_usd']-a['api_cost_usd']))
                if gain is not None:vals.append(gain)
            groups.append(dict(endpoint=endpoint,task=task,planned_pairs=2,quality_comparable=len(vals),
                wins=sum(v>0 for v in vals),ties=sum(v==0 for v in vals),losses=sum(v<0 for v in vals),
                median_gain=statistics.median(vals) if vals else None,sample_std_gain=statistics.stdev(vals) if len(vals)>1 else None))
    return dict(pairs=pairs,groups=groups)

def main(root):
    root=root.resolve(strict=True);build=read(root/'build.json');plan=read(root/'readout-plan.json')
    if (plan['root'],plan['source_tree'],plan['prepared_sha256'])!=(str(root),build['source_tree'],build['prepared_sha256']):raise ValueError('frozen binding')
    if set(plan['readers'])!=set(FILES):raise ValueError('full reader inventory')
    for f,h in plan['readers'].items():
        if sha(Path(__file__).with_name(f).read_bytes())!=h:raise ValueError('reader drift')
    write(root/'readout-intent.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),readout_plan_sha256=sha((root/'readout-plan.json').read_bytes()))))
    import readout_width_core_20260913 as core
    core.verify(root,seeds=SEEDS,blocks=(1,2))
    original=read(root/'wallclock-summary.json');prepared=read(root/'prepared.json',build['prepared_sha256'])
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    from mlebench.registry import registry
    import pandas as pd
    from verify_branching_selection_20260913 import verify_pool
    registry=registry.set_data_dir(root.parent/'mle-bench-data');answers={};rows=[];proofs=[];replays=[]
    for r in original['rows']:
        planned=next(p for p in prepared['run_configs'] if p['run_id']==r['run_id'])
        cfg=read(root/'configs'/(r['run_id']+'.json'),planned['config_sha256']);s=cfg['solver']
        width={'batch_four':4,'direct_two':2}[r['arm']]
        if (s['selection_policy'],s['num_children'],s['num_children_to_choose'],s['action_delivery_protocol'])!=(
            'uniform_random',width,2,'original_search_visible_action_delivery_v1'):raise ValueError('actual configured contrast')
        cp=Path(s['checkpoint_path'])
        if list((cp/'forets-contextual-judge-private').glob('batch-*/request-*.json')):raise ValueError('unexpected ranking')
        counts=dict(pools=0,generated=0,candidate_execution_attempts=0,candidate_execution_returned=0,debug_attempts=0)
        for path in sorted((cp/'forets-candidates-private').glob('batch-*.sqlite')):
            before=sha(path.read_bytes())
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
                payload,digest=db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchone()
            if sha(payload.encode())!=digest or sha(path.read_bytes())!=before:raise ValueError('pool snapshot drift')
            value=json.loads(payload);replay=verify_pool(value,s,{**r,'arm':'uniform_random'})
            if len(value['candidates'])>width:raise ValueError('observed width exceeds config')
            counts['pools']+=1;counts['generated']+=len(value['candidates'])
            for c in value['task_calls']:
                if c['intent']['role']=='candidate':
                    counts['candidate_execution_attempts']+=1;counts['candidate_execution_returned']+=c['state']=='returned'
                else:counts['debug_attempts']+=1
            replays.append(dict(run_id=r['run_id'],pool=path.name,sha256=before,**replay))
        # Candidate totals include the shared fixed RF start; it does not call
        # the generator. Do not rename this count as actual LLM calls.
        row=dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],proposal_width=width,
            selection_policy='uniform_random',execution_cap_per_batch=2,source_tree=build['source_tree'],controller_commit=build['commit'],
            job=r['job'],technical_eligible=r['technical_eligible'],termination_reason=r['termination_reason'],
            iteration_valid=r['valid'],iteration_score=r['score'],iteration_code_sha256=r['selected_code_sha256'],
            action_valid=False,action_score=None,action_code_sha256=None,action_elapsed_seconds=None,
            search_budget_seconds=600,program_timeout_seconds=300,worker_elapsed_seconds=r['worker_elapsed_seconds'],api_cost_usd=r['api_cost_usd'],
            returned_candidate_records_including_start=counts['generated'],candidate_execution_attempts_including_start=counts['candidate_execution_attempts'],
            candidate_execution_returned_including_start=counts['candidate_execution_returned'],debug_execution_attempts=counts['debug_attempts'],
            recorded_pools=counts['pools'],new_critic_calls=0)
        if r['search_start_ns'] is not None:
            data=read_latest(root/'incumbents'/r['run_id'],start_ns=r['search_start_ns'],seconds=600)
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
                independently=core.numerical(r['task'],pd.read_csv(archive/'submission.csv'),answers[r['task']])
                if round(independently,5)!=report['score']:raise ValueError('independent action grade')
                row.update(action_valid=True,action_score=report['score'],action_code_sha256=receipt['code_sha256'],
                    action_elapsed_seconds=(data['observation_ns']-data['start_ns'])/1e9)
                proofs.append(dict(run_id=r['run_id'],submission_sha256=receipt['submission_sha256'],report_sha256=receipt['report_sha256']))
        rows.append(row)
    result=dict(role='proposal_width_two_vs_four_uniform_e2e_development',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        primary_endpoint='action',secondary_endpoint='iteration',source_tree=build['source_tree'],controller_commit=build['commit'],
        rows=rows,**paired_effects(rows),proofs=proofs,selection_replays=replays,
        allocation_gpu_hours=original['allocation_gpu_hours'],billing=original['billing'],
        original_summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),
        limitations='Four fresh task-seed pairs; only proposal width differs. Actual token samples differ, no critic efficacy or new algorithm/scaling claim. Invalid/technical failures not imputed.')
    digest=write(root/'width-summary.json',encode(result))
    with (root/'width-runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(root/'readout-finished.json',encode(dict(status='verified',utc=result['utc'],source_tree=build['source_tree'],files={
        n:sha((root/n).read_bytes()) for n in ('wallclock-summary.json','wallclock-runs.csv','width-summary.json','width-runs.csv')})))
    print(json.dumps(dict(summary_sha256=digest,groups=result['groups'],allocation_gpu_hours=result['allocation_gpu_hours'])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();os.umask(0o077);main(a.root)
