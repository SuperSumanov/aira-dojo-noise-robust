"""Known-program pairing intervention, NOT a retry/new-source confirmation.

Identical four18819 programs, inputs, seeds and300s caps. Within-task matching
(0,1),(2,3) vs cross-task matching(0,3),(2,1), ABBA,16executions. Each block
reserves730s on one3090. Both matchings preserve per-program CPU cores/ports.
Readiness failure is fatal in this independent execution path. No retries.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import clock_rank_20261016 as rank

base=rank.base
OLD=Path('/research/d7/spc/yzyang4/clock-rank-20261016-v1')
ROOT=OLD.parent/'clock-pairing-20261016-v1'
OLD_PIN='4c22748699952da0b79bf862e1db5e785b7d2a9fb951bb26ee9c21be47ca3306'
NAME=Path(__file__).name
CAP=3120
BLOCK=730
WINDOW_END=1792142280
read,write,sha=base.read,base.write,base.sha
original_port_hook=base.port_hook


class InfrastructureReadinessError(RuntimeError): pass


def require_ready(call,*args,**kwargs):
    value=call(*args,**kwargs)
    if value is not True:
        raise InfrastructureReadinessError('kernel readiness failed before candidate execution')
    return value


def port_hook(job,program):
    original_port_hook(job,program)
    from dojo.core.interpreters.jupyter import jupyter_client as client
    cls=client.JupyterKernelClient
    original=getattr(cls.wait_for_ready,'_pairing_original',cls.wait_for_ready)
    def guarded(self,*a,**kw): return require_ready(original,self,*a,**kw)
    guarded._pairing_original=original
    cls.wait_for_ready=guarded


def schedule():
    return [dict(index=4*b+k,block=b,program=k,mode=mode,repeat=b//2,task=base.TASKS[k//2])
            for b,mode in enumerate(('within','cross','cross','within')) for k in range(4)]


def groups(block):
    pairs=[[0,1],[2,3]] if block in (0,3) else [[0,3],[2,1]]
    if block>=2: pairs=[list(reversed(g)) for g in reversed(pairs)]
    return [[4*block+p for p in group] for group in pairs]


def padded_groups(block):
    start=time.monotonic()
    for group in groups(block): yield group
    assert time.monotonic()-start<=BLOCK,'block budget exceeded: stop, no extension'
    while time.monotonic()-start<BLOCK:
        time.sleep(max(0.,min(1.,BLOCK-(time.monotonic()-start))))


def configure():
    rank.R=ROOT;rank.NAME=NAME;rank.CAP=CAP;rank.schedule=schedule;rank.groups=padded_groups
    rank.configure();base.port_hook=port_hook


def prepare(commit):
    configure();assert re.fullmatch('[a-f0-9]{40}',commit)
    assert sha(OLD/'plan.json')==OLD_PIN and (OLD/'closed.json').exists()
    old=read(OLD/'plan.json')
    for n,h in old['files'].items():assert sha(OLD/n)==h
    runtime=base.setup()
    ROOT.mkdir(mode=0o700)
    for d in ('configs','programs','bin'):(ROOT/d).mkdir()
    files=(NAME,'clock_pairing_readout_20261016.py','clock_rank_20261016.py',
           'clock_contention_20261016.py','closed_clock_screen_20261016.py')
    for n in files:shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    for k in range(4):shutil.copyfile(OLD/f'programs/{k}.private.py',ROOT/f'programs/{k}.private.py')
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from unittest.mock import patch
    for row in schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        original=read(OLD/f"configs/{row['index']}.json")
        cfg=json.loads(json.dumps(original).replace(str(OLD),str(ROOT)))
        assert json.loads(json.dumps(cfg).replace(str(ROOT),str(OLD)))==original
        assert cfg['interpreter']['timeout']==300
        assert cfg['interpreter']['env']['PYTHONHASHSEED']==str(old['programs'][row['program']]['seed'])
        write(ROOT/f"configs/{row['index']}.json",cfg)
        c=RunConfig.load_from_json(ROOT/f"configs/{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.logger.write_env_vars and not c.logger.use_wandb
        port_hook('100',row['program'])
        factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir)
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer'):
            assert factory.instance.port==base.gateway_port('100',row['program']) and factory.instance.timeout==300
            factory.close()
    (ROOT/'bin/singularity').write_text(f'#!{base.PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n')
    os.chmod(ROOT/'bin/singularity',0o700)
    (ROOT/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=r14-pairing
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --hint=nomultithread
#SBATCH --time=00:52:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=4 --gres=gpu:1 {base.PY} -B {ROOT/NAME} run
''')
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    pinned={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*')
            if p.is_file() and not p.relative_to(ROOT).parts[0].startswith('episode-')}
    write(ROOT/'plan.json',dict(source_commit=commit,donor_plan_sha256=old['donor_plan_sha256'],
        donor_files=old['donor_files'],prior_plan_sha256=OLD_PIN,files=pinned,
        schedule=schedule(),groups=[groups(b) for b in range(4)],programs=old['programs'],
        task_image=old['task_image'],task_image_sha256=old['task_image_sha256'],
        allocation_seconds=CAP,gpus=1,node='gpu27',worker_seconds=380,execution_seconds=300,
        block_reserved_seconds=BLOCK,window_end_utc=WINDOW_END,
        selection='All four known18819 programs, fixed before this intervention; outcome-known exploratory cohort, not independent replication.',
        primary='Full16valid, same inputs/isolation/cleanup, actual host training overlap in every pair. Cross task-best denoising oriented improvement>=.001 in BOTH repeat comparisons; aerial task-best nondecline in BOTH. Also report all program values, task medians/SD, actual full cost. No missing-score imputation or gate rescue.',
        stop='Any infrastructure/readiness/isolation/cleanup or first-block valid-CUDA failure stops remaining. No retries, replacements or new repair batch.',
        boundary='Pairing identity only. Each condition reserves2*730seconds across2blocks, same physicalGPU, per-program CPU cores, original image/seed/source300s cap. Known-program batch decision, not closed-loop E2E, task generalization or novelty; no other partition selected after results.',
        readiness_fix='Both conditions raise InfrastructureReadinessError before candidate execution if native wait_for_ready fails; no silent ordinary-timeout conversion.',
        preflight='One changed knob verified by group receipts;16real config roundtrips and prepared shim checked;all4original source hashes frozen;DEVonly/no train or protected inputs;seeds unchanged;noAPI/model-fit;all16denominator and task splits;whole allocation cap3120s;failure stop and no automatic retry.'))
    print(json.dumps(dict(status='PREPARED',root=str(ROOT),plan_sha256=sha(ROOT/'plan.json'),groups=[groups(b) for b in range(4)],programs=len(old['programs']))))


def task_runtime():
    configure();rank.task_runtime()


def entrycheck():
    configure();base.check();base.setup()
    import runpy
    from unittest.mock import patch
    class ReachedExec(Exception):pass
    with patch.object(sys,'argv',[str(ROOT/'bin/singularity'),'--version']),patch.object(os,'execv',side_effect=ReachedExec) as call:
        try:runpy.run_path(str(ROOT/'bin/singularity'),run_name='__main__')
        except ReachedExec:pass
        else:raise AssertionError('entry did not reach container binary')
        assert call.call_count==1
    from dojo.core.interpreters.jupyter import jupyter_client as client
    with patch.object(client.JupyterKernelClient,'wait_for_ready',new=lambda self,*a,**kw:False):
        port_hook('100',0)
        try:client.JupyterKernelClient.wait_for_ready(None)
        except InfrastructureReadinessError:pass
        else:raise AssertionError('real class hook failed to propagate readiness failure')
    print(json.dumps(dict(actual_prepared_shim_imports=True,readiness_failure_propagated=True,
        same_input_roundtrips=16,external_binary_not_executed=True)))


def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=('prepare','entrycheck','submit','run','worker'))
    a.add_argument('--commit');a.add_argument('--index',type=int);v=a.parse_args();configure()
    if v.action=='prepare':prepare(v.commit)
    elif v.action=='entrycheck':entrycheck()
    elif v.action=='submit':
        assert WINDOW_END-time.time()>=3300,'not enough time for allocation and readout; do not submit'
        base.submit()
    elif v.action=='worker':return base.worker(v.index)
    else:
        if WINDOW_END-time.time()<3300:
            write(ROOT/'window-refusal.json',dict(no_workers_started=True,remaining_seconds=WINDOW_END-time.time()))
            return 2
        return rank.run()


if __name__=='__main__':sys.exit(main())
