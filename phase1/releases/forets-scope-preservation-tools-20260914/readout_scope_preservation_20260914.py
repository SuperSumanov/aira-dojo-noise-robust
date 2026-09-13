"""Conditional twelve-run preservation comparison; action primary, iteration secondary."""
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
ARMS=('whole_program','preserve_program','model_module')
SEEDS=(46,47)
FILES=('readout_scope_preservation_20260914.py','readout_scope_preservation_core_20260914.py',
    'read_forets_action_delivery_20260913.py','readout_forets_generation_capacity_20260912.py','verify_branching_selection_20260913.py','forets_edit_scope_20260914.py','scope_preservation_effects_20260914.py')

def candidate_counts(value):
    # The ledger preallocates pending slots. They are not returned programs.
    returned=sum(isinstance(c.get('node'),dict) and isinstance(c['node'].get('code'),str)
        for c in value['candidates'])
    attempts=[c for c in value['task_calls'] if c['intent']['role']=='candidate']
    return dict(generated=returned,candidate_execution_attempts=len(attempts),
        candidate_execution_returned=sum(c['state']=='returned' for c in attempts),
        debug_attempts=sum(c['intent']['role']=='debug' for c in value['task_calls']))

def paired_effects(rows):
    from scope_preservation_effects_20260914 import effects
    return effects(rows)

def main(root):
    root=root.resolve(strict=True);build=read(root/'build.json');plan=read(root/'readout-plan.json')
    if (plan['root'],plan['source_tree'],plan['prepared_sha256'])!=(str(root),build['source_tree'],build['prepared_sha256']):raise ValueError('frozen binding')
    if set(plan['readers'])!=set(FILES):raise ValueError('full reader inventory')
    for f,h in plan['readers'].items():
        if sha(Path(__file__).with_name(f).read_bytes())!=h:raise ValueError('reader drift')
    write(root/'readout-intent.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),readout_plan_sha256=sha((root/'readout-plan.json').read_bytes()))))
    import readout_scope_preservation_core_20260914 as core
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
        width={'whole_program':2,'preserve_program':2,'model_module':2}[r['arm']]
        if (s['selection_policy'],s['num_children'],s['num_children_to_choose'],s['action_delivery_protocol'])!=(
            'uniform_random',width,2,'original_search_visible_action_delivery_v1'):raise ValueError('actual configured contrast')
        if s['edit_scope'] != ('model_module' if r['arm']=='model_module' else 'whole_program'):raise ValueError('actual edit scope')
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
            counts['pools']+=1
            for key,number in candidate_counts(value).items():counts[key]+=number
            replays.append(dict(run_id=r['run_id'],pool=path.name,sha256=before,**replay))
        # Candidate totals include the shared fixed RF start; it does not call
        # the generator. Do not rename this count as actual LLM calls.
        row=dict(run_id=r['run_id'],task=r['task'],seed=r['seed'],arm=r['arm'],proposal_width=width,
            selection_policy='uniform_random',execution_cap_per_batch=2,source_tree=build['source_tree'],controller_commit=build['commit'],
            job=r['job'],technical_eligible=r['technical_eligible'],termination_reason=r['termination_reason'],
            iteration_valid=r['valid'],iteration_score=r['score'],iteration_code_sha256=r['selected_code_sha256'],
            action_valid=False,action_score=None,action_code_sha256=None,action_elapsed_seconds=None,
            search_budget_seconds=1200,program_timeout_seconds=300,worker_elapsed_seconds=r['worker_elapsed_seconds'],api_cost_usd=r['api_cost_usd'],
            returned_candidate_records_including_start=counts['generated'],candidate_execution_attempts_including_start=counts['candidate_execution_attempts'],
            candidate_execution_returned_including_start=counts['candidate_execution_returned'],debug_execution_attempts=counts['debug_attempts'],
            recorded_pools=counts['pools'],new_critic_calls=0)
        if r['search_start_ns'] is not None:
            data=read_latest(root/'incumbents'/r['run_id'],start_ns=r['search_start_ns'],seconds=1200)
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
    result=dict(role='preservation_strong_control_1200_e2e_development',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        primary_endpoint='action',secondary_endpoint='iteration',source_tree=build['source_tree'],controller_commit=build['commit'],
        rows=rows,**paired_effects(rows),proofs=proofs,selection_replays=replays,
        allocation_gpu_hours=original['allocation_gpu_hours'],billing=original['billing'],
        original_summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),
        limitations='Four fresh task-seed triplets. Whole, preservation-prompt/full-output, and module-interface arms; all three pairwise contrasts and both endpoints retained. Same common start and resource caps, actual cost may differ. Exploratory only; no critic, scaling, novel algorithm, or task-population claim. Missingness not imputed.')
    digest=write(root/'scope-preservation-summary.json',encode(result))
    with (root/'scope-preservation-runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(root/'readout-finished.json',encode(dict(status='verified',utc=result['utc'],source_tree=build['source_tree'],files={
        n:sha((root/n).read_bytes()) for n in ('wallclock-summary.json','wallclock-runs.csv','scope-preservation-summary.json','scope-preservation-runs.csv')})))
    print(json.dumps(dict(summary_sha256=digest,groups=result['groups'],allocation_gpu_hours=result['allocation_gpu_hours'])))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();os.umask(0o077);main(a.root)
