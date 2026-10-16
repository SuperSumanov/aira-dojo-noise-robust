"""Independent Oct17 pairing experiment;18859 stays sealed and is not resumed.

Only root, window and submission-time guard differ from the frozen Oct16 design.
Same16 executions, four known programs, ABBA matchings,300s/program,3120s GPU cap.
"""
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone
import clock_pairing_20261016 as frozen

ROOT=Path('/research/d7/spc/yzyang4/clock-pairing-20261017-v2')
WINDOW_END=int(datetime(2026,10,17,0,49,tzinfo=timezone.utc).timestamp())
NAME=Path(__file__).name
ORIGINAL_PREPARE=getattr(frozen,'_oct17_original_prepare',frozen.prepare)
frozen._oct17_original_prepare=ORIGINAL_PREPARE


def guard_after_hash(now):
    if WINDOW_END-now<3300:
        raise RuntimeError('insufficient window after image hash: no submission')


def submit():
    b=frozen.base
    p=b.check()
    assert b.sha(Path(p['task_image']))==p['task_image_sha256']
    # Recheck AFTER the expensive image hash, not only before it.
    guard_after_hash(time.time())
    assert not (ROOT/'submit-intent.json').exists()
    b.write(ROOT/'submit-intent.json',dict(plan_sha256=b.sha(ROOT/'plan.json'),wall=time.time()))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),
        '--output='+str(ROOT/'allocation-%j.private.out'),
        '--error='+str(ROOT/'allocation-%j.private.err'),str(ROOT/'run.sbatch')],
        env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),
        text=True,capture_output=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():
        raise RuntimeError('ambiguous submission: do not repeat')
    b.write(ROOT/'launch.json',dict(job=job,plan_sha256=b.sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,root=str(ROOT),plan_sha256=b.sha(ROOT/'plan.json'))))


def configure():
    frozen.ROOT=ROOT;frozen.NAME=NAME;frozen.WINDOW_END=WINDOW_END
    # The new shim imports this module; include the unchanged frozen dependency
    # in the immutable prepared package. Scientific schedule and gate unchanged.
    source=inspect.getsource(ORIGINAL_PREPARE)
    needle="files=(NAME,'clock_pairing_readout_20261016.py'"
    assert source.count(needle)==1
    source=source.replace(needle,"files=(NAME,'clock_pairing_20261016.py','clock_pairing_readout_20261016.py'",1)
    scope=dict(vars(frozen))
    exec(compile(source,'independent-pairing-prepare','exec'),scope)
    frozen.prepare=scope['prepare']
    frozen.base.submit=submit
    frozen.configure()


def task_runtime():
    configure();frozen.task_runtime()


if __name__=='__main__':
    configure();sys.exit(frozen.main())
