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
ARMS=('uniform','short_code','learned_validity')
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path):
    if path.is_symlink():raise ValueError('artifact is a symlink')
    return json.loads(path.read_bytes())


def effects(rows, seeds=(46,47)):
    if tuple(seeds)!=(46,47) or len(rows)!=12 or {(r['task'],r['seed'],r['arm']) for r in rows}!={(t,s,a) for t in TASKS for s in seeds for a in ARMS}:
        raise ValueError('twelve exact cheap-selector rows required')
    for r in rows:
        if r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score'])):raise ValueError('valid score absent')
        if not r['valid'] and r['score'] is not None:raise ValueError('no missing imputation')
    return {}


def verify(root, seeds=(22,23), blocks=(1,)):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('explicit new development package only')
    if (root/'wallclock-summary.json').exists():raise ValueError('readout already complete')
    if (tuple(seeds),tuple(blocks)) != ((46,47),(1,2)):
        raise ValueError('explicit frozen seed/allocation layout required')
    build=read(root/'build.json')
    launches={b:read(root/(f'launch-b{b}.json' if len(blocks)>1 else 'launch.json')) for b in blocks}
    if sha((root/'prepared.json').read_bytes())!=build['prepared_sha256']:raise ValueError('preparation hash')
    prepared=read(root/'prepared.json');os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    artifact=read(root/'artifact.json')
    if artifact['source_tree']!=build['source_tree']:raise ValueError('source tree mismatch')
    for relative,digest in artifact['source_files'].items():
        path=root/'source'/relative
        if path.is_symlink() or not path.resolve().is_relative_to(root/'source') or sha(path.read_bytes())!=digest:
            raise ValueError('source changed during the experiment')
    acct=subprocess.check_output(['sacct','-j',','.join(launches[b]['job'] for b in blocks),'-nP','-o','JobIDRaw,State%32,NodeList,ElapsedRaw,AllocTRES%128'],text=True,timeout=25)
    records={}
    for line in acct.splitlines():
        fields=line.split('|')
        if len(fields)!=5 or fields[0] in records:raise ValueError('accounting shape/duplicates')
        records[fields[0]]=fields
    allocations={};pools={}
    if {r['block'] for r in prepared['run_configs']}!=set(blocks):raise ValueError('prepared blocks')
    for block in blocks:
        launch=launches[block];allocation=records[launch['job']];allocations[block]=allocation
        if allocation[1].split()[0].rstrip('+') not in TERMINAL or allocation[2]!='gpu28':raise ValueError('allocation not closed')
        tres=dict(x.split('=',1) for x in allocation[4].split(',') if '=' in x)
        if tres.get('gres/gpu')!='1':raise ValueError('allocation GPU count')
        start=read(root/f'block-{block}.runtime/started.json')
        pool=read(root/start['pool_manifest']);pools[block]=pool
        if pool['allocation_id']!=launch['job'] or set(pool['tasks'])!={r['run_id'] for r in prepared['run_configs'] if r['block']==block}:
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
    rows=[];proofs=[];uuids={b:set() for b in blocks};answers={}
    for planned in prepared['run_configs']:
        block=planned['block'];launch=launches[block];pool=pools[block]
        rid=planned['run_id'];task=pool['tasks'][rid];scope=scopes.get(rid,{})
        row={k:planned[k] for k in ('run_id','task','seed','arm')}
        row.update(job=launch['job'],source_tree=build['source_tree'],controller_commit=build['commit'],
            generator='qwen/qwen3-coder-flash',critic=None,
            provider='alibaba',image_version='2026-07-macos-v1',node='gpu28',allocated_gpus=1,allocated_cpus=6,
            program_timeout_seconds=300,selection_top_k=1,selection_coupling='common_priority_v1',
            search_budget_seconds=600,planned_step_cap=64,runtime_status=task['status'],
            critic_ranking_votes=0,
            api_cost_usd=scope.get('settled_usd',0),api_responsibility_usd=scope.get('held_usd',0),
            valid=False,score=None,independent_score=None,selected_step=None,selected_code_sha256=None,
            worker_elapsed_seconds=None,search_start_ns=None,technical_eligible=False,termination_reason='not_started')
        if task['attempt']==0:
            if task['attempts']:raise ValueError('unstarted slot has attempts')
            rows.append(row);continue
        if task['attempt']!=1 or len(task['attempts'])!=1:raise ValueError('replayed run')
        prepared_config=root/'configs'/(rid+'.json')
        if sha(prepared_config.read_bytes())!=planned['config_sha256']:raise ValueError('run config changed')
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
        row['search_start_ns']=summary['search_start_ns']
        reason=summary['status']
        if reason=='failed':
            # Match only the deliberate, fixed exception marker; never export
            # model text or use arbitrary errors as evidence of budget closure.
            error_path=path.parent/'stderr.private.log'
            with error_path.open('rb') as stream:
                stream.seek(max(0,error_path.stat().st_size-4096));tail=stream.read()
            if tail.rstrip().endswith(b'SearchBudgetExpired: insufficient search time for a bounded API request'):
                reason='api_admission_budget_expired'
            elif tail.rstrip().endswith(b'RunBudgetError: run adapter-attempt budget exhausted'):
                reason='adapter_attempt_budget_expired'
        row['termination_reason']=reason
        bindings=list(identity.parent.glob(identity.name+'.native-binding-*.json'))
        for binding_path in bindings:
            binding=read(binding_path)
            if (binding['native_identity']['job']!=launch['job'] or not binding['namespace']['exact_device_namespace']):
                raise ValueError('task hardware binding')
            uuids[block].add(binding['native_identity']['selected_uuid'])
        row['technical_eligible']=bool(bindings) and reason in ('completed','timed_out','api_admission_budget_expired','adapter_attempt_budget_expired') and not scope.get('unresolved',0)
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
    if any(len(u)>1 for u in uuids.values()):raise ValueError('physical GPU differed within allocation')
    result=effects(rows,seeds=seeds)
    seconds=sum(int(a[3]) for a in allocations.values())
    result.update(source_tree=build['source_tree'],controller_commit=build['commit'],job=launch['job'] if len(blocks)==1 else None,
        jobs_by_block={str(b):launches[b]['job'] for b in blocks},
        role='wallclock_development_e2e_not_confirmatory',seeds=list(seeds),all_planned_slots_reported=True,rows=rows,proofs=proofs,
        independent_numeric_regrades=len(proofs),allocation_seconds=seconds,allocation_gpu_hours=seconds/3600,
        billing={k:v for k,v in billing.items() if k!='scopes'},same_physical_gpu=(len(blocks)==1 and len(uuids[blocks[0]])==1),
        same_physical_gpu_within_each_block=all(len(u)==1 for u in uuids.values()),
        complete_technical_matrix=all(r['technical_eligible'] for r in rows),
        verifier_sha256=sha(Path(__file__).read_bytes()),
        numerical_helper_sha256=sha(Path(__file__).with_name('readout_forets_generation_capacity_20260912.py').read_bytes()),
        limitation='Two tasks/two new seeds; three cheap selectors with one common fresh-container backend. Same refactored start. This file retains the secondary iteration endpoint. Cleanup charged, no exact physical-cost equality, critic efficacy or scaling claim.')
    with (root/'wallclock-summary.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    with (root/'wallclock-runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','proofs')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path)
    parser.add_argument('--seeds',type=int,nargs=2,default=(22,23));args=parser.parse_args()
    verify(args.root,seeds=tuple(args.seeds))
