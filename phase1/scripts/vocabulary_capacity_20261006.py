"""New posthoc ablation of the known representation control, not R12 reopening.

Reuse the already exercised native worker. Keep earlier batches immutable.
No outcome values are read by prepare/submit/worker/controller.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import matched_representation_20261005 as runner

B = Path('/research/d7/spc/yzyang4')
R = B/'vocabulary-capacity-20261006-v1'
PREV = B/'matched-representation-20261005-v1'
THIS = Path(__file__).name
CORE = 'matched_representation_program_20261005.py'
OVERRIDE = 'vocabulary_capacity_override_20261006.py'
PROGRAM = 'capacity_program.py'
PY = B/'venvs/aira/bin/python'
read, write, sha = runner.read, runner.write, runner.sha


def schedule():
    rows = []
    arms = ('word', 'word_25k', 'word_char')
    for j, seed in enumerate(runner.SEEDS):
        for t, task in enumerate(runner.TASKS):
            k = (j + t) % 3
            for arm in arms[k:] + arms[:k]:
                rows.append(dict(index=len(rows), task=task, task_index=t, seed=seed, arm=arm))
    return rows


def configure():
    runner.R, runner.NAME, runner.PROGRAM = R, THIS, PROGRAM
    runner.schedule = schedule
    runner.DONOR_SHA = sha(R/'runtime.py')


def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}', commit) and not R.exists()
    assert sha(PREV/'plan.json') == 'fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624'
    old = read(PREV/'plan.json')
    # Verify donor artifacts from the frozen plan before using any code.
    for rel, h in old['files'].items():
        assert sha(PREV/rel) == h, rel
    R.mkdir(mode=0o700)
    for rel, h in old['files'].items():
        if not rel.startswith(('source/', 'forets_', 'opencl-vendors/')):
            continue
        dst = R/rel; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PREV/rel, dst)
    original = (PREV/'runtime.py').read_bytes()
    assert hashlib.sha256(original).hexdigest() == 'b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
    pattern = b"re.fullmatch('episode-[0-7]',ep.name)"
    assert original.count(pattern) == 1
    (R/'runtime.py').write_bytes(original.replace(pattern, b"re.fullmatch('episode-(?:[0-9]|1[01])',ep.name)"))
    src = Path(__file__).parent
    for name in (THIS, OVERRIDE):
        shutil.copyfile(src/name, R/name)
    shutil.copyfile(PREV/'matched_representation_20261005.py', R/'matched_representation_20261005.py')
    core = (PREV/CORE).read_bytes()
    program = core + b'\n' + (src/OVERRIDE).read_bytes()
    compile(program, PROGRAM, 'exec')
    (R/PROGRAM).write_bytes(program)
    (R/'configs').mkdir(); (R/'bin').mkdir()
    wrapper = f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(THIS).stem} import configure,runner\nconfigure()\nrunner.runtime().task_runtime()\n'
    (R/'bin/singularity').write_text(wrapper); os.chmod(R/'bin/singularity', 0o700)
    old_schedule = old['schedule']
    for row in schedule():
        donor = next(x for x in old_schedule if x['task']==row['task'] and x['seed']==row['seed'] and x['arm']=='word')
        cfg = read(PREV/'configs'/f"{donor['index']}.json")
        ep = R/f"episode-{row['index']}"; ep.mkdir()
        cfg['id'] = f"capacity-{row['index']}"
        cfg['logger'].update(output_dir=str(ep/'native-log'), write_env_vars=False, use_wandb=False, print_config=False, use_console=False)
        cfg['metadata'].update(seed=row['seed'], base_path=str(R/'source'), git_commit_id=commit, script_id='vocabulary-capacity-20261006')
        cfg['task'].update(cache_dir=str(R/'no-official-data'), results_output_dir=str(ep/'native-log/results'))
        cfg['interpreter'].update(timeout=360, working_dir=str(ep/'action-0/work'))
        cfg['interpreter']['env'].update(PYTHONHASHSEED=str(row['seed']), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        write(R/'configs'/f"{row['index']}.json", cfg)
    batch = f'''#!/bin/bash
#SBATCH --job-name=vocabulary-capacity
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=01:00:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 3530s {PY} -B {R}/{THIS} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json', dict(protocol='vocabulary-capacity-posthoc-ablation-v1', source_commit=commit,
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()}, schedule=schedule(),
        donor_plan_sha256=sha(PREV/'plan.json'), core_program_sha256=sha(PREV/CORE), override_sha256=sha(src/OVERRIDE),
        grid=old['grid'], word_caps=dict(word=50000,word_25k=25000,word_char=25000), char_cap=25000,
        primary='word_char minus word_25k, oriented higher better; per-task pairs, median and sample variance',
        secondary='word_25k minus word; existing word/word_char deterministic replay identity; matched-grid inner diagnostics',
        interpretation='Posthoc confound check of a known positive control, NOT a novel method, fresh task or untouched test. No restart of R12/R13 gates.',
        limitations='Two reused tasks and overlapping internal splits; fixed fit opportunities, not equal realized time. Same word vocabulary cap does not isolate normalization or coefficient geometry from adding a block.',
        selection=old['selection'], deployment=old['deployment'], program_seconds=360, worker_seconds=440,
        assigned=12, classifier_fits_planned=348, binary_fits_planned=696,
        gpus=1, allocation_seconds=3600, gpu_hours_cap=1,
        stopping='Hard allocation cap; retain missing/failures, no automatic retry or follow-up expansion. Progress and closed episodes remain resumable evidence.',
        automatic_expansion=False, no_generator=True, no_paid_api=True, no_base_training=True, protected_opened=False))
    configure(); native = runner.runtime()
    from dojo.config_dataclasses.run import RunConfig
    for row in schedule():
        cfg = RunConfig.load_from_json(R/'configs'/f"{row['index']}.json"); cfg.validate()
        assert not Path(cfg.task.private_dir).exists() and not cfg.interpreter.read_only_binds
        assert sha(cfg.task.search_only_dev_scorer_path) == cfg.task.search_only_dev_scorer_sha256
        assert cfg.task.data_dir == cfg.task.public_dir and '/search-only-dev-' in cfg.task.data_dir
    module = runner.load('capacity_test', R/PROGRAM)
    result = module.capacity_tests(); assert module.synthetic()['status']=='PASS'
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json', dict(**result, typed_configs=12, plan_sha256=sha(R/'plan.json'), task_image_sha256=read(PREV/'preflight.json')['task_image_sha256']))
    print(__import__('json').dumps(dict(status='PREPARED', assigned=12, tests=result, plan_sha256=sha(R/'plan.json'))))


def controller():
    configure(); runner.check(); m=runner.runtime()
    assert read(R/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    codes=[]
    for row in schedule():
        ep=R/f"episode-{row['index']}"
        assert not (ep/'native.json').exists()
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:08:00',str(PY),'-B',str(R/THIS),'worker','--index',str(row['index'])]
        with (ep/'worker.private.log').open('xb') as f:
            result=subprocess.run(cmd,env=m.infra().clean_env(),stdout=f,stderr=f)
        write(ep/'closed.json',dict(returncode=result.returncode));codes.append(result.returncode)
    write(R/'closed.json',dict(returncodes=codes,assigned=12))


def local_tests():
    rows=schedule()
    assert len(rows)==12 and len({(x['task'],x['seed'],x['arm']) for x in rows})==12
    assert all(sum(x['task']==t and x['seed']==s for x in rows)==3 for t in runner.TASKS for s in runner.SEEDS)
    ast.parse(Path(__file__).read_text());ast.parse(Path(__file__).with_name(OVERRIDE).read_text())
    print('CAPACITY_STATIC_TESTS_PASS assigned=12 grid_per_program=28 fits=348')


if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','submit','worker','controller','check','tests']);p.add_argument('--commit');p.add_argument('--index',type=int);args=p.parse_args()
    if args.mode=='tests':local_tests()
    elif args.mode=='prepare':prepare(args.commit)
    elif args.mode=='controller':controller()
    else:
        configure()
        if args.mode=='worker':runner.worker(args.index)
        else:getattr(runner,args.mode)()
