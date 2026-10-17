"""One guarded administrative replacement, ONLY if19118 never executed."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v2')
OUT=Path(__file__).with_name('quota-v2-never-started-cancel.safe.json')
JOB='19118'
PIN='8d4d402365257376ba3634d21929624031f349f971c314e2aa26786c42ea147b'
env=dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')


def command(args):
    return subprocess.check_output(args,env=env,text=True,timeout=25).strip()


assert not OUT.exists(), 'do not repeat supersession'
assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest()==PIN
assert json.loads((ROOT/'launch.json').read_text())['job']==JOB
assert not (ROOT/'closed.json').exists() and not (ROOT/'service-ready.json').exists()
assert not list(ROOT.glob('episode-*/deadline.json'))
finalize_only=sys.argv[1:]==['--finalize-only']
assert not sys.argv[1:] or finalize_only
before=command(['squeue','-j',JOB,'-h','-o','%i|%u|%T'])
if not finalize_only:
    assert before==JOB+'|yzyang4|PENDING', 'already started or unknown: DO NOT replace'
    subprocess.run(['scancel',JOB],env=env,check=True,timeout=25)
else:
    assert not before, 'read-only finalize expects job no longer queued'
record=None
for _ in range(15):
    text=command(['sacct','-j',JOB,'-n','-P','--format=JobIDRaw,State,ElapsedRaw,Start,End,AllocTRES,NodeList'])
    lines=[line.split('|') for line in text.splitlines() if line.split('|')[0]==JOB]
    if lines and lines[0][1].startswith('CANCELLED'):
        assert len(text.splitlines())==1, 'an actual step exists; do not replace'
        record=lines[0];break
    time.sleep(1)
assert record and int(record[2])==0 and not record[5] and record[6]=='None assigned', 'allocation exists: no successor'
assert record[3] in ('Unknown','None','N/A','',record[4]), 'nonzero execution interval: no successor'
assert not (ROOT/'service-ready.json').exists() and not list(ROOT.glob('episode-*/deadline.json'))
assert not command(['squeue','-j',JOB,'-h','-o','%i'])
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job=JOB,root=str(ROOT),plan_sha256=PIN,
            prior_state=before,final_state=record[1],elapsed_seconds=int(record[2]),start=record[3],end=record[4],
            node_list=record[6],allocated_tres=record[5],job_steps=0,
            gpu_seconds=0,workers_started=0,service_started=False,read_outcomes=False,
            scope='Administrative pre-start queue-expiry correction, not retry of an executed experiment. Original32matrix/seeds/hardware/100min/10GPUh/quality gates unchanged. Preserve originalroot/plan; no second actual GPU allocation.',
            reason='Three-hour reporting deadline was incorrectly also a launch cutoff. Replace never-started job with bounded queue validity while keeping reporting deadline and total allocation cap.',
            recorder_note='Initial cancellation succeeded but first recorder rejected Slurm filling Start=End=cancel timestamp. Read-only sacct/scontrol confirmed elapsed0, no allocatedTRES, no node/steps/service/workers. Finalize-only does not repeat cancellation.')
with OUT.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
