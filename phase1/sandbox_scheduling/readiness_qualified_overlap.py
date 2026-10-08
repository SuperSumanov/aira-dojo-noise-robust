"""New 10min qualification then 30min neural overlap study, 2026-10-08 evening.

No old writer or allocation is resumed. Same small public inputs, source seeds,
candidate timeouts and 12-slot pipeline/share2 contrast as 17021. Both arms use
the same opt-in info-only handshake change. This is an infrastructure retry,
not an independent workload or training-seed confirmation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time

import lifecycle_pilot as life
import neural_overlap_control as control
from bounded_readiness import wait_for_ready
from lifecycle_pilot import read, write, sha

B = Path('/research/d7/spc/yzyang4')
Q = B/'scheduling-readiness-live-20261008-evening-v1'
R = B/'scheduling-neural-qualified-overlap-20261008-evening-v1'
QD = B/'scheduling-lifecycle-20261006-v1'
NAME = 'readiness_qualified_overlap.py'
CLIENT_SHA = 'a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'
HELPER_SHA = '0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd'


def install_handshake():
    import dojo.core.interpreters.jupyter.jupyter_client as client
    if sha(client.__file__) != CLIENT_SHA or sha(Path(__file__).with_name('bounded_readiness.py')) != HELPER_SHA:
        raise ValueError('handshake source drift')
    receipts = []
    def bounded(self, timeout_seconds=None):
        start = time.monotonic()
        ok = wait_for_ready(self, 120 if timeout_seconds is None else timeout_seconds)
        receipts.append(dict(seconds=time.monotonic()-start, ready=ok,
                             requested_timeout=timeout_seconds))
        return ok
    client.JupyterKernelClient.wait_for_ready = bounded
    return receipts


def q_schedule():
    return [dict(index=i, repeat=i, arm='close_now', seed=130601) for i in range(3)]


def q_check():
    plan = read(Q/'plan.json')
    if plan['schedule'] != q_schedule() or plan['allocation_seconds'] != 600:
        raise ValueError('qualification plan')
    for name, pin in plan['files'].items():
        if sha(Q/name) != pin:
            raise ValueError('qualification file drift')
    return plan


def configure_q():
    life.R = Q
    life.NAME = NAME
    life.schedule = q_schedule
    life.check = q_check
    return life


def prepare_q(commit):
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('exact source commit')
    old = read(QD/'plan.json')
    if hashlib.sha256(life.PROGRAM.encode()).hexdigest() != old['program_sha256']:
        raise ValueError('qualification fixture drift')
    if not read(QD/'closed.json')['complete']:
        raise ValueError('closed lifecycle donor required')
    Q.mkdir(mode=0o700, exist_ok=False)
    for name, pin in old['files'].items():
        if name in ('run.sbatch', 'bin/singularity'):
            continue
        if sha(QD/name) != pin:
            raise ValueError('donor drift')
        dest = Q/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(QD/name, dest)
    # Imports needed by this wrapper, but qualification executes no candidates.
    for path in Path(__file__).parent.glob('*.py'):
        shutil.copyfile(path, Q/path.name)
    for row in q_schedule():
        (Q/f'episode-{row["index"]}/work').mkdir(parents=True)
    (Q/'empty-data').mkdir(exist_ok=True)
    (Q/'bin').mkdir(exist_ok=True)
    (Q/'bin/singularity').write_text(f'#!{life.PY}\nimport sys\nsys.path.insert(0,{str(Q)!r})\nfrom {Path(NAME).stem} import configure_q\nconfigure_q().runtime().task_runtime()\n')
    os.chmod(Q/'bin/singularity', 0o700)
    batch = f'''#!/bin/bash
#SBATCH --job-name=r14-ready-evening
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --time=00:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 560s {life.PY} -B {Q/NAME} qcontroller
'''
    (Q/'run.sbatch').write_text(batch)
    write(Q/'plan.json', dict(source_commit=commit, donor_plan_sha256=sha(QD/'plan.json'),
        schedule=q_schedule(), allocation_seconds=600, gpu_hours_cap=1/6, gpus=1, total_cpu=6,
        purpose='three fresh kernels: info handshake, exact GPU fixture, fetch, close; no speed claim',
        candidate_executions=0, no_data=True, no_api=True, no_base_training=True,
        helper_sha256=HELPER_SHA, client_source_sha256=CLIENT_SHA,
        fixed_fixture_sha256=old['program_sha256'],
        files={str(p.relative_to(Q)):sha(p) for p in Q.rglob('*') if p.is_file()}))
    configure_q().runtime()
    if sha(life.runtime().TASK_IMAGE) != control.n.IMAGE_SHA:
        raise ValueError('qualification image drift')
    q_check()
    subprocess.run(['bash', '-n', str(Q/'run.sbatch')], check=True)
    write(Q/'preflight.json', dict(plan_sha256=sha(Q/'plan.json'),
          image_sha256=control.n.IMAGE_SHA, no_gpu_execution=True))
    print(json.dumps(dict(status='PREPARED', study='qualification', plan_sha256=sha(Q/'plan.json'))))


def q_submit():
    q_check()
    if read(Q/'preflight.json')['plan_sha256'] != sha(Q/'plan.json'):
        raise ValueError('preflight drift')
    env = configure_q().runtime().infra().clean_env()
    jobs = subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'], env=env, text=True, timeout=15).split()
    if set(jobs)-{'12535'}:
        raise ValueError('unexpected active job')
    write(Q/'submit-intent.json', dict(plan_sha256=sha(Q/'plan.json'), gpu_seconds_cap=600))
    result = subprocess.run(['sbatch','--parsable','--chdir='+str(Q),
        '--output='+str(Q/'allocation-%j.out'),'--error='+str(Q/'allocation-%j.err'),str(Q/'run.sbatch')],
        env=env, capture_output=True, text=True, timeout=20)
    job = result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():
        raise RuntimeError('ambiguous submission: do not retry')
    write(Q/'launch.json', dict(job=job, plan_sha256=sha(Q/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED', study='qualification', job=job)))


def q_worker(index):
    configure_q().runtime()
    calls = install_handshake()
    try:
        life.worker(index)
    finally:
        write(Q/f'episode-{index}/handshake.json', calls)


def q_controller():
    configure_q(); q_check()
    for _ in range(40):
        if (Q/'launch.json').exists():
            break
        time.sleep(.25)
    if read(Q/'launch.json')['job'] != os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0] != 'gpu27':
        raise ValueError('qualification allocation')
    codes = []
    env = life.runtime().infra().clean_env()
    for row in q_schedule():
        ep = Q/f'episode-{row["index"]}'
        cmd = ['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6',
               '--gres=gpu:1','--time=00:02:00','--cpu-bind=cores','timeout',
               '--signal=TERM','--kill-after=10s','100s',str(life.PY),'-B',str(Q/NAME),
               'qworker','--index',str(row['index'])]
        with (ep/'worker.private.log').open('xb') as log:
            result = subprocess.run(cmd, env=env, stdout=log, stderr=log)
        codes.append(result.returncode)
        write(ep/'closed.json', dict(returncode=result.returncode))
        if result.returncode or not (ep/'completed.json').exists() or not read(ep/'completed.json')['complete']:
            break
    ok = len(codes) == 3 and not any(codes)
    if ok:
        ok = all(read(Q/f'episode-{i}/handshake.json') and
                 all(v['ready'] for v in read(Q/f'episode-{i}/handshake.json')) for i in range(3))
    write(Q/'closed.json', dict(planned=3, attempted=len(codes), complete=bool(ok), returncodes=codes))
    return 0 if ok else 1


def qualification_gate():
    q_check()
    if not read(Q/'closed.json')['complete']:
        raise ValueError('live qualification did not pass')
    for index in range(3):
        ep = Q/f'episode-{index}'
        done = read(ep/'completed.json')
        calls = read(ep/'handshake.json')
        if (read(ep/'closed.json')['returncode'] != 0 or not done['complete'] or
                not calls or not all(v['ready'] for v in calls) or
                read(ep/'work/fixture.json') != {'elements':16777216,'sum':16777216,'dtype':'torch.float32'}):
            raise ValueError('qualification execution/fetch evidence')
        phases = {r['phase']:r for r in read(ep/'samples.json')}
        if not {'release_verified','after_close_no_clients'} <= phases.keys():
            raise ValueError('qualification release evidence')
    job = read(Q/'launch.json')['job']
    raw = subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
          env=dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf'), text=True, timeout=20)
    rows = [x.split('|') for x in raw.splitlines() if x.split('|')[0] == job]
    if len(rows) != 1 or rows[0][1] != 'COMPLETED' or not 0 < int(rows[0][2]) <= 600:
        raise ValueError('qualification terminal accounting')
    if 'gres/gpu=1' not in rows[0][3].split(',') or 'cpu=6' not in rows[0][3].split(','):
        raise ValueError('qualification resources')
    return dict(job=job, actual_gpu_seconds=int(rows[0][2]), plan_sha256=sha(Q/'plan.json'),
                receipt_sha256=sha(Q/'closed.json'))


def mutate_plan(plan):
    control.mutate_plan(plan)
    plan.update(infrastructure_retry_of_jobs=['17014','17021'],
        prior_results_unchanged=True, not_independent_workload_or_training_seeds=True,
        live_qualification=qualification_gate(), common_handshake_sha256=HELPER_SHA,
        client_source_sha256=CLIENT_SHA, no_own_concurrent_heavy_preparation=True,
        new_evening_window_gpu_seconds_cap=2400,
        qualification_does_not_prove_timeout_root_cause_or_future_reliability=True)


def set_scope():
    control.R = R
    control.set_scope()
    control.r.NAME = NAME
    control.r.CAP = 1800
    control.r.JOBNAME = 'r14-qualified-overlap'
    control.r.PLAN_MUTATOR = mutate_plan
    control.r.EXTRA_FILES = ('neural_full_input_trial.py','neural_overlap_control.py','bounded_readiness.py')


def configure():
    set_scope()
    return control.r.configure()


def main():
    os.umask(0o077)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1')
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['qprepare','qsubmit','qcontroller','qworker','prepare','submit','controller','worker','readout','audit'])
    ap.add_argument('--commit'); ap.add_argument('--index', type=int); ap.add_argument('--plan-sha')
    args = ap.parse_args()
    if args.mode.startswith('q'):
        return {'qprepare':lambda:prepare_q(args.commit),'qsubmit':q_submit,
                'qcontroller':q_controller,'qworker':lambda:q_worker(args.index)}[args.mode]()
    if args.mode == 'prepare':
        set_scope()
        return control.r.prepare(args.commit)
    configure()
    if args.mode == 'worker':
        control.n.pilot().runtime()
        calls = install_handshake()
        try:
            return control.n.worker(args.index)
        finally:
            write(R/f'episode-{args.index}/handshake.json', calls)
    if args.mode in ('submit','controller'):
        control.r.check_inputs()
        if args.mode == 'submit':
            gate = qualification_gate()
            if gate != read(R/'plan.json')['live_qualification']:
                raise ValueError('qualification drift')
        return getattr(control.n, args.mode)()
    if args.mode == 'readout':
        import neural_pool_readout as report
        report.R = R; report.REFERENCE_ARM = 'pipeline'
        return report.main()
    if args.mode == 'audit':
        if not args.plan_sha or not re.fullmatch('[a-f0-9]{64}', args.plan_sha):
            raise ValueError('independent plan SHA required')
        return control.audit(args.plan_sha)


if __name__ == '__main__':
    sys.exit(main())
