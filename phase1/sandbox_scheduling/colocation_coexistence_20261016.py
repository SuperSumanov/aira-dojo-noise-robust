"""Bounded common qualification of TWO original-image CUDA containers on ONE GPU.

Only synthetic tensors, no task data or scoring. Both hold a tensor until both
completion markers exist. This proves coexistence and namespace, not performance
or safety for arbitrary future memory demand. Included in the new batch budget.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

PROGRAM = """
import json,os,time
from pathlib import Path
import torch
i=int(os.environ['COEXIST_SLOT']); root=Path('/workspace')
assert torch.cuda.is_available() and torch.cuda.device_count()==1
x=torch.zeros(32*1024*1024,device='cuda')
a=torch.ones((256,256),device='cuda')
torch.cuda.synchronize()
(root/('ready-'+str(i))).write_text('ready')
limit=time.monotonic()+25
while not all((root/('ready-'+str(k))).exists() for k in (0,1)):
    if time.monotonic()>limit:raise TimeoutError('coexistence rendezvous')
    time.sleep(.02)
answer=(a@a).sum().item()
torch.cuda.synchronize()
assert answer==16777216
(root/('done-'+str(i))).write_text('done')
while not all((root/('done-'+str(k))).exists() for k in (0,1)):
    if time.monotonic()>limit:raise TimeoutError('coexistence completion')
    time.sleep(.02)
print('COEXIST_GATE '+json.dumps(dict(slot=i,passed=True,devices=1,
    result=answer,held_bytes=x.numel()*x.element_size(),both_ready=True,both_done=True)))
"""

def validate(rows):
    assert len(rows)==2 and {r["slot"] for r in rows}=={0,1}
    assert all(r["passed"] and r["devices"]==1 and r["result"]==16777216
               and r["held_bytes"]==134217728 and r["both_ready"] and r["both_done"] for r in rows)

def run(root, uid, namespace_command, image, gpu_sample):
    work=Path(root)/"coexistence-work";work.mkdir()
    processes=[];files=[];rows=[];receipts=[];commands=[];begin=time.monotonic()
    try:
        for i in (0,1):
            args=["exec","--containall","--cleanenv","--no-home","--nv",
                  "--bind",str(work)+":/workspace:rw","--pwd","/workspace",str(image),
                  "env","HOME=/workspace/.home",f"COEXIST_SLOT={i}","python","-c",PROGRAM]
            cmd,env,receipt=namespace_command(args,uid)
            receipts.append(receipt)
            commands.append((cmd,env))
        # Complete namespace checks before either rendezvous clock starts.
        # All setup still counts against the allocation and common240s gate.
        launched=time.monotonic()
        for i,(cmd,env) in enumerate(commands):
            log=(work/f"container-{i}.private.log").open("xb");files.append(log)
            processes.append(subprocess.Popen(cmd,env=env,stdout=log,stderr=log,start_new_session=True))
        for process in processes:
            process.wait(timeout=max(.1,70-(time.monotonic()-launched)))
        for log in files:log.close()
        assert all(p.returncode==0 for p in processes)
        for i in (0,1):
            text=(work/f"container-{i}.private.log").read_text(errors="replace")
            marks=[json.loads(s.removeprefix("COEXIST_GATE ")) for s in text.splitlines()
                   if s.startswith("COEXIST_GATE ")]
            assert len(marks)==1
            rows.extend(marks)
        validate(rows)
        assert all(r["gpu_uuid"]==uid and r["namespace"]["exact_device_namespace"] for r in receipts)
    finally:
        for p in processes:
            if p.poll() is None:
                os.killpg(p.pid,signal.SIGTERM)
                try:p.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
        for log in files:
            if not log.closed:log.close()
    clean=not gpu_sample(uid)["pids"]
    assert clean
    output=dict(passed=True,containers=2,gpu_uuid=uid,rows=rows,
        elapsed_seconds=time.monotonic()-begin,cleanup_verified=clean,
        scope="Two synthetic128MiB allocations coexist in original task containers; not arbitrary-code memory safety or speedup.")
    with (Path(root)/"coexistence-qualification.json").open("x") as f:
        json.dump(output,f,indent=2,allow_nan=False)
