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

R = Path('/research/d7/spc/yzyang4/scheduling-neural-gpu28-20261008-v2')
D = Path('/research/d7/spc/yzyang4/scheduling-neural-20261008-v1')
DONOR = '8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'
NAME = 'neural_node_replication.py'
NODE, CAP = 'gpu28', 2700
JOBNAME = 'r14-neural-gpu28'
FIXTURE_BUILDER = None
PLAN_MUTATOR = None
EXTRA_FILES = ()
QUESTION = 'Independent second-node replication of the fixed mixed neural pair; not a novel scheduler.'


def configure():
    n.R, n.NAME, n.NODE, n.CAP = R, NAME, NODE, CAP
    return n.pilot()


def worker_ast(source):
    module = ast.parse(source)
    names = ('worker', 'run_one')
    return {s.name:ast.dump(s, include_attributes=False)
            for s in module.body if isinstance(s, ast.FunctionDef) and s.name in names}


def batch_script(original):
    if '--time=01:30:00' not in original or '5350s srun' not in original:
        raise ValueError('unexpected donor budget')
    time_limit=f'{CAP//3600:02}:{CAP%3600//60:02}:00'
    outer=f'{CAP-40}s srun'
    result = original.replace('r14-neural-v1',JOBNAME).replace(str(D),str(R)).replace('gpu27',NODE).replace('01:30:00',time_limit).replace('5350s srun',outer).replace('neural_pool_trial.py controller',f'{NAME} controller')
    if '--time='+time_limit not in result or outer not in result:
        raise ValueError('allocation budget substitution')
    return result


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
    inputs = dict(old.get('input_files', {}))
    for name, pin in old['files'].items():
        if sha(D/name) != pin:
            raise ValueError('donor drift')
        if name.startswith(('data-0/', 'data-1/')):
            inputs[str(D/name)] = pin
        elif name not in ('run.sbatch', 'bin/singularity') and not name.startswith('episode-'):
            dest = R/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(D/name, dest)
    for name in set((NAME, 'neural_node_replication.py','neural_inputs.py','neural_pool_trial.py', 'neural_pool_readout.py',
                 'audit_neural_result.py', 'verify_pool_outputs.py')+EXTRA_FILES):
        shutil.copyfile(here/name, R/name)
    fixture = FIXTURE_BUILDER(R) if FIXTURE_BUILDER is not None else None
    for p in (0, 1):
        if not (R/f'data-{p}').exists():
            (R/f'data-{p}').symlink_to(D/f'data-{p}', target_is_directory=True)
    for i in list(range(12))+[36]:
        (R/f'episode-{i}/work/input_cache').mkdir(parents=True)
    (R/'empty-data').mkdir()
    (R/'bin').mkdir(exist_ok=True)
    wrapper = f'#!{n.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import configure\nconfigure().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper)
    os.chmod(R/'bin/singularity', 0o700)
    batch = batch_script((D/'run.sbatch').read_text())
    (R/'run.sbatch').write_text(batch)
    plan = {k:v for k,v in old.items() if k != 'files'}
    if fixture is not None:
        plan['programs'][1]['data']=str(R/'data-1')
        plan['fixture_scope']='cactus donor unchanged; denoising all public train except same two query images, whose cleaned targets are never read/mounted'
        plan['input_scale_receipt']=fixture
        inputs={path:pin for path,pin in inputs.items() if '/data-1/' not in path}
        inputs.update({str(p):sha(p) for p in (R/'data-1').rglob('*') if p.is_file()})
    plan.update(source_commit=commit, donor_plan_sha256=DONOR, node=NODE,
                gpu_hours_cap=CAP/3600, allocation_seconds=CAP, input_files=inputs,
                question=QUESTION,
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
                    walltime=f'donor mixed small-input actual1444GPUseconds, not a guarantee for new scope; new cap{CAP} includes overhead/failure, per-block worst-time gate; incomplete allowed without extension',
                    power='three source-seed restarts are a systems replication, not population or model-learning evidence',
                    returncodes='subprocess return checked; exclusive intent prevents duplicate submission',
                    fixed_sample='same donor programs and public inputs; no replacement or extra trials based on results'),
                files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not any(part in ('data-0','data-1') for part in p.relative_to(R).parts)})
    if PLAN_MUTATOR is not None:
        PLAN_MUTATOR(plan)
    write(R/'plan.json', plan)
    m = configure().runtime()
    if sha(m.TASK_IMAGE) != n.IMAGE_SHA:
        raise ValueError('image drift')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    check_inputs()
    write(R/'preflight.json', dict(plan_sha256=sha(R/'plan.json'), image_sha256=n.IMAGE_SHA,
                                  worker_AST_unchanged=True, candidate_executions=0))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),gpu_hours_cap=CAP/3600)))


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
