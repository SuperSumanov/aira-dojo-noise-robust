"""Independent 12-slot replication on gpu28; <=45min, no changes to candidates.

Default neural worker/schedule are retained. Only allocation node/bound/root vary
between studies; within this study serial/share2 use identical CPU/GPU/image.
"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import neural_pool_trial as n
from lifecycle_pilot import read, write, sha

R = Path('/research/d7/spc/yzyang4/scheduling-neural-gpu28-20261008-v1')
D = Path('/research/d7/spc/yzyang4/scheduling-neural-20261008-v1')
DONOR = '8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'
NAME = 'neural_node_replication.py'


def configure():
    n.R, n.NAME, n.NODE, n.CAP = R, NAME, 'gpu28', 2700
    return n.pilot()


def worker_ast(source):
    module = ast.parse(source)
    names = ('worker', 'run_one')
    return {s.name:ast.dump(s, include_attributes=False)
            for s in module.body if isinstance(s, ast.FunctionDef) and s.name in names}


def check_inputs():
    plan = n.check()
    for path, pin in plan['input_files'].items():
        if sha(path) != pin:
            raise ValueError('input drift')
    return plan


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}', commit) or sha(D/'plan.json') != DONOR:
        raise ValueError('source/donor pin')
    old = read(D/'plan.json')
    if read(D/'closed.json')['completed'] != 12:
        raise ValueError('donor qualification')
    here = Path(__file__).parent
    if worker_ast((D/'neural_pool_trial.py').read_text()) != worker_ast((here/'neural_pool_trial.py').read_text()):
        raise ValueError('candidate worker changed')
    R.mkdir(mode=0o700, exist_ok=False)
    inputs = {}
    for name, pin in old['files'].items():
        if sha(D/name) != pin:
            raise ValueError('donor drift')
        if name.startswith(('data-0/', 'data-1/')):
            inputs[str(D/name)] = pin
        elif name not in ('run.sbatch', 'bin/singularity') and not name.startswith('episode-'):
            dest = R/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(D/name, dest)
    for name in (NAME, 'neural_pool_trial.py', 'neural_pool_readout.py',
                 'audit_neural_result.py', 'verify_pool_outputs.py'):
        shutil.copyfile(here/name, R/name)
    for p in (0, 1):
        (R/f'data-{p}').symlink_to(D/f'data-{p}', target_is_directory=True)
    for i in list(range(12))+[36]:
        (R/f'episode-{i}/work/input_cache').mkdir(parents=True)
    (R/'empty-data').mkdir()
    (R/'bin').mkdir(exist_ok=True)
    wrapper = f'#!{n.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom neural_node_replication import configure\nconfigure().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper)
    os.chmod(R/'bin/singularity', 0o700)
    batch = (D/'run.sbatch').read_text().replace('r14-neural-v1','r14-neural-gpu28').replace(str(D),str(R)).replace('gpu27','gpu28').replace('01:30:00','00:45:00').replace('5360s','2660s').replace('neural_pool_trial.py controller',f'{NAME} controller')
    if '--time=00:45:00' not in batch or '2660s' not in batch:
        raise ValueError('allocation budget substitution')
    (R/'run.sbatch').write_text(batch)
    plan = {k:v for k,v in old.items() if k != 'files'}
    plan.update(source_commit=commit, donor_plan_sha256=DONOR, node='gpu28',
                gpu_hours_cap=.75, allocation_seconds=2700, input_files=inputs,
                question='Independent second-node replication of the fixed mixed neural pair; not a novel scheduler.',
                candidate_worker_AST_unchanged=True,
                preflight_items=dict(
                    actual_knob='block/episode arm plus candidate interval receipts; same node/image/CPU in both arms',
                    cheap_new_path='local/remote matrix and worker-AST tests; unchanged completed donor workers',
                    test_dedup='not applicable: no critic training or held-out access; deliberate replicas/restarts declared',
                    distribution='two fixed tasks; three paired blocks; no independent-training-seed claim',
                    balance='same code, public inputs, order within repeats, six CPUs and one GPU',
                    checkpoint='not a critic training job; per-episode files retained, closed failures not resumed',
                    leakage='only exact donor public-train fixture and outputs, no official test or sealed cohort',
                    rng='unchanged source seed42 and harness130701; original schedule retained',
                    credentials='no dotenv/API/model secrets; export safe summaries only',
                    walltime='donor actual1444GPUseconds; new cap2700 includes all overhead/failure, per-block worst-time gate; incomplete allowed without extension',
                    power='three source-seed restarts are a systems replication, not population or model-learning evidence',
                    returncodes='subprocess return checked; exclusive intent prevents duplicate submission',
                    fixed_sample='same donor programs and public inputs; no replacement or extra trials based on results'),
                files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not any(part in ('data-0','data-1') for part in p.relative_to(R).parts)})
    write(R/'plan.json', plan)
    m = configure().runtime()
    if sha(m.TASK_IMAGE) != n.IMAGE_SHA:
        raise ValueError('image drift')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    check_inputs()
    write(R/'preflight.json', dict(plan_sha256=sha(R/'plan.json'), image_sha256=n.IMAGE_SHA,
                                  worker_AST_unchanged=True, candidate_executions=0))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),gpu_hours_cap=.75)))


def main():
    os.umask(0o077)
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser()
    ap.add_argument('mode',choices=['prepare','submit','controller','worker','readout','audit'])
    ap.add_argument('--commit');ap.add_argument('--index',type=int);ap.add_argument('--plan-sha')
    args=ap.parse_args()
    if args.mode=='prepare':return prepare(args.commit)
    configure()
    if args.mode=='worker':return n.worker(args.index)
    if args.mode in ('submit','controller'):
        check_inputs()
        return getattr(n,args.mode)()
    if args.mode=='readout':
        import neural_pool_readout as r
        r.R=R
        return r.main()
    if args.mode=='audit':
        if not args.plan_sha or not re.fullmatch('[a-f0-9]{64}',args.plan_sha):
            raise ValueError('independently recorded exact plan SHA required')
        import audit_neural_result as a
        a.ROOT=R;a.PLAN_SHA=args.plan_sha
        return a.main()


if __name__=='__main__':
    sys.exit(main())
