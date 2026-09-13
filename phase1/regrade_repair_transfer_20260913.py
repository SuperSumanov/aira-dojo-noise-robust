"""Post-closure independent submission arithmetic and allocation receipt.

No program rerun, candidate reselection, API, model, or protected cohort access.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE/'forets-repair-transfer-20260913-d151en61'
TERMINAL = {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}


def read(path):
    if path.is_symlink():
        raise ValueError('symlink')
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    closure = read(ROOT/'readout-finished.json')
    if sha(ROOT/'summary.json') != closure['summary_sha256']:
        raise ValueError('readout hash')
    summary = read(ROOT/'summary.json')
    allocations = []
    submitted = {}
    for block in (0,1):
        work = ROOT/f'block-{block}'
        launch = read(work/'launch.json')
        finish = read(work/'execution-finished.json')
        if launch['job'] != finish['job']:
            raise ValueError('closure job')
        acct = subprocess.check_output(['sacct','-X','-j',launch['job'],'-nP','-o','JobIDRaw,State,ElapsedRaw,NodeList,AllocTRES%128'],
            env={**os.environ,'SLURM_CONF':'/opt1/slurm/gpu-slurm.conf'}, text=True, timeout=25).strip().split('|')
        if len(acct)!=5 or acct[0]!=launch['job'] or acct[1].split()[0].rstrip('+') not in TERMINAL or acct[3]!='gpu28':
            raise ValueError('allocation not closed')
        tres = dict(item.split('=',1) for item in acct[4].split(',') if '=' in item)
        if tres.get('gres/gpu')!='1' or tres.get('cpu')!='6':
            raise ValueError('allocation hardware')
        devices = set()
        spec = read(work/'prepared.json')
        for row in spec['rows']:
            i = row['local_index']
            path = work/f'result-{i}.json'
            if not path.exists():
                continue
            if str(path) not in summary['proof'] or sha(path)!=summary['proof'][str(path)]:
                raise ValueError('result drift')
            result = read(path)
            binding_path = work/f'identity-{i}.native-binding.json'
            if result['status']!='infrastructure_error':
                binding = read(binding_path)
                if binding['native_identity']['job']!=launch['job'] or not binding['namespace']['exact_device_namespace']:
                    raise ValueError('native hardware binding')
                devices.add(binding['native_identity']['selected_uuid'])
            if result['status']=='valid':
                submission = work/f'work-{i}/submission.csv'
                if submission.is_symlink() or sha(submission)!=result['submission_sha256']:
                    raise ValueError('submission hash')
                submitted[row['index']] = (submission, result)
        if len(devices)>1:
            raise ValueError('physical GPU changed within block')
        allocations.append(dict(job=acct[0],state=acct[1],elapsed_seconds=int(acct[2]),gpu_count=1,cpus=6,node=acct[3],physical_devices=len(devices)))
    from readout_forets_generation_capacity_20260912 import numerical
    from mlebench.registry import registry
    import pandas as pd
    registry = registry.set_data_dir(BASE/'mle-bench-data')
    truth = {}
    proofs = []
    for row in summary['rows']:
        if row['repair_success'] is not True:
            continue
        path, result = submitted.pop(row['index'])
        task = row['task']
        if task not in truth:
            truth[task] = pd.read_csv(registry.get_competition(task).answers)
        score = numerical(task, pd.read_csv(path), truth[task])
        if round(score,5)!=row['score'] or row['score']!=result['score']:
            raise ValueError('independent task grade')
        proofs.append(dict(index=row['index'],task=task,submission_sha256=sha(path),score=row['score'],independent_score=score))
    if submitted:
        raise ValueError('valid submission omitted')
    seconds = sum(a['elapsed_seconds'] for a in allocations)
    output = dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),verified=True,
        summary_sha256=closure['summary_sha256'],allocations=allocations,allocation_seconds=seconds,
        allocation_gpu_hours=seconds/3600,numeric_regrades=len(proofs),proofs=proofs,
        numerical_reader_sha256=sha(Path(__file__).with_name('readout_forets_generation_capacity_20260912.py')),
        caveat='Checks delivered predictions and arithmetic, not training-data integrity or e2e utility. No rerun or replacement.')
    raw = (json.dumps(output,sort_keys=True,indent=2)+'\n').encode()
    with (ROOT/'independent-submissions.json').open('xb') as stream:
        stream.write(raw)
    print(json.dumps(output|dict(receipt_sha256=hashlib.sha256(raw).hexdigest())))


if __name__=='__main__':
    main()
