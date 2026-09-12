"""Independent closed-allocation readout of cutoff-qualified incumbents only.

No new execution, candidate-score selection, private test-cohort reads or
missing-to-zero. Every planned slot is represented, including unstarted runs.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys

from readout_forets_generation_capacity_20260912 import numerical

TASKS=('leaf-classification','spaceship-titanic')
ARMS=('uniform_random','critic_topk_random')
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path):
    if path.is_symlink():raise ValueError('artifact is a symlink')
    return json.loads(path.read_bytes())


def effects(rows):
    expected={(t,s,a) for t in TASKS for s in (22,23) for a in ARMS}
    if len(rows)!=8 or {(r['task'],r['seed'],r['arm']) for r in rows}!=expected:
        raise ValueError('all eight unique planned rows required')
    for r in rows:
        if r['valid']:
            if type(r['score']) not in (int,float) or not math.isfinite(r['score']):raise ValueError('valid score absent')
        elif r['score'] is not None:raise ValueError('invalid missing imputation')
    pairs=[];groups=[]
    for task in TASKS:
        for seed in (22,23):
            a,b=[next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm)) for arm in ARMS]
            comparable=a['valid'] and b['valid']
            gain=((a['score']-b['score']) if task==TASKS[0] else (b['score']-a['score'])) if comparable else None
            pairs.append(dict(task=task,seed=seed,random_valid=a['valid'],critic_valid=b['valid'],
                comparable=comparable,critic_oriented_score_gain=gain,
                both_technically_eligible=a['technical_eligible'] and b['technical_eligible']))
        for arm in ARMS:
            rs=[r for r in rows if (r['task'],r['arm'])==(task,arm)]
            values=[r['score'] for r in rs if r['valid']]
            groups.append(dict(task=task,arm=arm,runs=2,valid=len(values),
                conditional_median_score=statistics.median(values) if values else None,
                conditional_sample_std_score=statistics.stdev(values) if len(values)>1 else None,
                api_cost_usd=sum(r['api_cost_usd'] for r in rs)))
    gains=[]
    for task in TASKS:
        values=[r['critic_oriented_score_gain'] for r in pairs if r['task']==task and r['comparable']]
        gains.append(dict(task=task,comparable_seeds=len(values),median_gain=statistics.median(values) if values else None,
            sample_std_gain=statistics.stdev(values) if len(values)>1 else None))
    return dict(pairs=pairs,groups=groups,gain_summary=gains)


def verify(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('explicit new development package only')
    if (root/'wallclock-summary.json').exists():raise ValueError('readout already complete')
    build,launch=read(root/'build.json'),read(root/'launch.json')
    if sha((root/'prepared.json').read_bytes())!=build['prepared_sha256']:raise ValueError('preparation hash')
    prepared=read(root/'prepared.json');os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    acct=subprocess.check_output(['sacct','-j',launch['job'],'-nP','-o','JobIDRaw,State%32,NodeList,ElapsedRaw,AllocTRES%128'],text=True,timeout=25)
    records={}
    for line in acct.splitlines():
        fields=line.split('|')
        if len(fields)!=5 or fields[0] in records:raise ValueError('accounting shape/duplicates')
        records[fields[0]]=fields
    allocation=records[launch['job']]
    if allocation[1].split()[0].rstrip('+') not in TERMINAL or allocation[2]!='gpu28':raise ValueError('allocation not closed')
    tres=dict(x.split('=',1) for x in allocation[4].split(',') if '=' in x)
    if tres.get('gres/gpu')!='1':raise ValueError('allocation GPU count')
    start=read(root/'block-1.runtime/started.json')
    pool=read(root/start['pool_manifest'])
    if pool['allocation_id']!=launch['job'] or set(pool['tasks'])!={r['run_id'] for r in prepared['run_configs']}:
        raise ValueError('pool identity')
    if any(t['status'] in ('launching','running') for t in pool['tasks'].values()):
        raise ValueError('closed allocation has unresolved controller rows; diagnose first')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')]
    from dojo.solvers.fore_ts.wallclock import read_incumbent
    from forets_paid_budget_20260911 import snapshot
    from mlebench.registry import registry
    import pandas as pd
    registry=registry.set_data_dir(root.parent/'mle-bench-data')
    billing=snapshot(root/'paid.sqlite');scopes={r['scope']:r for r in billing['scopes']}
    rows=[];proofs=[];uuids=set();answers={}
    for planned in prepared['run_configs']:
        rid=planned['run_id'];task=pool['tasks'][rid];scope=scopes.get(rid,{})
        row={k:planned[k] for k in ('run_id','task','seed','arm')}
        row.update(job=launch['job'],source_tree=build['source_tree'],controller_commit=build['commit'],
            search_budget_seconds=600,planned_step_cap=64,runtime_status=task['status'],
            api_cost_usd=scope.get('settled_usd',0),api_responsibility_usd=scope.get('held_usd',0),
            valid=False,score=None,independent_score=None,selected_step=None,selected_code_sha256=None,
            worker_elapsed_seconds=None,technical_eligible=False,termination_reason='not_started')
        if task['attempt']==0:
            if task['attempts']:raise ValueError('unstarted slot has attempts')
            rows.append(row);continue
        if task['attempt']!=1 or len(task['attempts'])!=1:raise ValueError('replayed run')
        identity=Path(task['attempts'][0]['identity_path'])
        if not identity.resolve().is_relative_to(root/'runs/srun_pool'):raise ValueError('identity outside pool')
        ident=read(identity);step=records[ident['full_step_id']]
        if ident['run_id']!=rid or ident['allocation_id']!=launch['job'] or step[1].split()[0].rstrip('+') not in TERMINAL:
            raise ValueError('step identity/not terminal')
        path=identity.with_suffix('.bounded')/'execution/summary.json'
        summary=read(path)
        if summary.get('search_seconds')!=600 or type(summary.get('search_start_ns')) is not int:
            raise ValueError('worker cutoff origin missing')
        row['worker_elapsed_seconds']=summary['elapsed_seconds']
        reason=summary['status']
        if reason=='failed':
            # Match only the deliberate, fixed exception marker; never export
            # model text or use arbitrary errors as evidence of budget closure.
            error_path=path.parent/'stderr.private.log'
            with error_path.open('rb') as stream:
                stream.seek(max(0,error_path.stat().st_size-4096));tail=stream.read()
            if tail.rstrip().endswith(b'SearchBudgetExpired: insufficient search time for a bounded API request'):
                reason='api_admission_budget_expired'
        row['termination_reason']=reason
        bindings=list(identity.parent.glob(identity.name+'.native-binding-*.json'))
        for binding_path in bindings:
            binding=read(binding_path)
            if (binding['native_identity']['job']!=launch['job'] or not binding['namespace']['exact_device_namespace']):
                raise ValueError('task hardware binding')
            uuids.add(binding['native_identity']['selected_uuid'])
        row['technical_eligible']=bool(bindings) and reason in ('completed','timed_out','api_admission_budget_expired') and not scope.get('unresolved',0)
        selected=read_incumbent(root/'incumbents'/rid,expected_start_ns=summary['search_start_ns'],expected_seconds=600)
        if selected is not None and selected['submission'] is not None:
            config=read(root/'configs'/(rid+'.json'));receipt=selected['submission']
            archive=Path(receipt['archive_dir']);expected=Path(config['task']['results_output_dir'])/'submission-escrow'
            if archive.is_symlink() or archive.parent.resolve()!=expected.resolve():raise ValueError('wrong selected archive')
            complete=read(archive/'complete.json')
            if any(receipt.get(k)!=v for k,v in complete.items()):raise ValueError('archive receipt mismatch')
            for name,key in [('submission.csv','submission_sha256'),('report.json','report_sha256')]:
                if sha((archive/name).read_bytes())!=receipt[key]:raise ValueError('selected submission/report hash')
            report=read(archive/'report.json')
            if report['valid_submission'] is not True:raise ValueError('incumbent archive invalid')
            competition=planned['task']
            if competition not in answers:answers[competition]=pd.read_csv(registry.get_competition(competition).answers)
            independently=numerical(competition,pd.read_csv(archive/'submission.csv'),answers[competition])
            if round(independently,5)!=report['score']:raise ValueError('independent score mismatch')
            row.update(valid=True,score=report['score'],independent_score=independently,
                selected_step=selected['current_step'],selected_code_sha256=receipt['code_sha256'])
            proofs.append(dict(run_id=rid,submission_sha256=receipt['submission_sha256'],
                report_sha256=receipt['report_sha256'],durable_cutoff_selected=True))
        rows.append(row)
    if len(uuids)>1:raise ValueError('physical GPU differed within allocation')
    result=effects(rows)
    result.update(source_tree=build['source_tree'],controller_commit=build['commit'],job=launch['job'],
        role='wallclock_development_e2e_not_confirmatory',all_planned_slots_reported=True,rows=rows,proofs=proofs,
        independent_numeric_regrades=len(proofs),allocation_seconds=int(allocation[3]),allocation_gpu_hours=int(allocation[3])/3600,
        billing={k:v for k,v in billing.items() if k!='scopes'},same_physical_gpu=len(uuids)==1,
        complete_technical_matrix=all(r['technical_eligible'] for r in rows),
        limitation='Two tasks/two fresh seeds; cutoff includes online critic. Cleanup is extra and charged. No exact physical-cost equality or scaling claim.')
    with (root/'wallclock-summary.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    with (root/'wallclock-runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','proofs')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args();verify(args.root)
