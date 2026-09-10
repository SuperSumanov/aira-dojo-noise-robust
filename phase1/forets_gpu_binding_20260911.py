"""Explicitly enabled Singularity adapter for the fixed ForeTS development pool.

Keeps the original task command/image/workspace/env except for documented GPU
bindings, loader path and equivalent allocated-GPU UUID visibility. Not a Slurm
launcher. No legacy --nv fallback, credentials, model or task-result reads.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

from forets_opencl_allowlist_20260911 import IMAGE, GATE, driver_binds

# gpu28 was checked INSIDE Slurm: login linux5 has a different installation path.
REAL_SINGULARITY='/usr/bin/singularity'
DEV_ROOT=Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')


def split_command(args):
    """Accept only the pinned server's GPU container shape; preserve arguments."""
    if args[:5] != ['exec','--containall','--cleanenv','--no-home','--nv']:
        raise ValueError('unsupported Singularity command shape')
    if args.count('--nv') != 1 or args.count(str(IMAGE)) != 1:
        raise ValueError('ambiguous image/GPU arguments')
    i=args.index(str(IMAGE))
    prefix=args[5:i]
    j=0
    while j<len(prefix):
        if prefix[j] not in ('--overlay','--bind','--pwd') or j+1>=len(prefix):
            raise ValueError('unsupported task container option')
        j+=2
    tail=args[i+1:]
    if not tail or tail[0]!='env': raise ValueError('expected explicit container environment')
    variables={}; j=1
    while j<len(tail) and re.match(r'^[A-Za-z_][A-Za-z0-9_]*=',tail[j]):
        name,value=tail[j].split('=',1)
        if name in variables: raise ValueError('duplicate environment variable')
        variables[name]=value;j+=1
    payload=tail[j:]
    if payload[:2]!=['python','-c']: raise ValueError('expected pinned Python bootstrap')
    if variables.get('HOME')!='/workspace/.home': raise ValueError('task home differs')
    return list(prefix),variables,list(payload)


def rewrite(args, *, minor, uuid, libraries, vendors):
    prefix,variables,payload=split_command(args)
    if type(minor) is not int or minor<0 or not re.fullmatch(r'GPU-[a-fA-F0-9-]+',uuid):
        raise ValueError('invalid allocation identity')
    devices=[f'/dev/nvidia{minor}','/dev/nvidiactl','/dev/nvidia-uvm']
    out=[REAL_SINGULARITY,'exec','--containall','--cleanenv','--no-home',
         '--no-mount','bind-paths,cwd']+prefix
    for device in devices:out+=['--bind',f'{device}:{device}']
    for name,p in sorted(libraries.items()):
        if '/' in name or any(c in str(p) for c in ',:\n'):raise ValueError('unsafe library bind')
        out+=['--bind',f'{p}:/run/forets-driverlibs/{name}:ro']
    if any(c in str(vendors) for c in ',:\n'):raise ValueError('unsafe ICD path')
    out+=['--bind',f'{vendors}:/etc/OpenCL/vendors:ro']
    variables['CUDA_VISIBLE_DEVICES']=uuid
    variables['CUDA_DEVICE_ORDER']='PCI_BUS_ID'
    prior=variables.get('LD_LIBRARY_PATH','')
    variables['LD_LIBRARY_PATH']='/run/forets-driverlibs'+(':'+prior if prior else '')
    final=out+[str(IMAGE),'env']+[f'{k}={v}' for k,v in variables.items()]+payload
    # Separate, credential-free gate before starting Jupyter or executing code.
    gate=out+[str(IMAGE),'env',f'EXPECTED_GPU_MINORS={minor}',
              'EXPECTED_GPU_MAJOR=195','python','-c',GATE]
    return final,gate


def observed_binding(env, runner=subprocess.run):
    # The flawed Slurm-ID -> NVML-index implementation is removed, not hidden
    # behind a boolean/hash that could accidentally re-enable it. Keep the old
    # evidence in Git; a future implementation needs independent mapping facts.
    raise RuntimeError('Slurm-to-physical mapping unverified; adapter withdrawn')


def main(args=None):
    args=list(sys.argv[1:] if args is None else args)
    if args==['--version']:
        os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args)  # no subprocess on malformed/unsupported invocation
    env=os.environ
    # Production records live next to worker identity, outside agent workspace.
    # A bounded integration test can use its own explicitly selected isolated root.
    identity=Path(env.get('DOJO_WORKER_IDENTITY_PATH',''))
    root=DEV_ROOT
    if env.get('FORETS_GPU_INTEGRATION_ROOT'):
        root=Path(env['FORETS_GPU_INTEGRATION_ROOT']).resolve(strict=True)
        if (root.parent!=DEV_ROOT.parent or not root.name.startswith('forets-gpu-adapter-20260911-')):
            raise ValueError('invalid integration root')
    if (not identity.is_absolute() or identity.is_symlink()
            or not identity.resolve().is_relative_to(root.resolve(strict=True))
            or not identity.parent.is_dir()):
        raise ValueError('identity receipt outside allowed development root')
    minor,uuid,libs,driver=observed_binding(env)
    vendors=Path(__file__).with_name('opencl-vendors')
    if (vendors/'nvidia.icd').read_text().strip()!='libnvidia-opencl.so.1':raise ValueError('ICD drift')
    final,gate=rewrite(args,minor=minor,uuid=uuid,libraries=libs,vendors=vendors)
    clean={k:env[k] for k in ('PATH','HOME','USER','LOGNAME') if k in env}
    result=subprocess.run(gate,env=clean,capture_output=True,text=True,timeout=25)
    lines=[json.loads(s.removeprefix('ALLOWLIST_GATE ')) for s in result.stdout.splitlines() if s.startswith('ALLOWLIST_GATE ')]
    if result.returncode or len(lines)!=1 or lines[0].get('exact_device_namespace') is not True:
        raise RuntimeError('GPU namespace/driver binding gate failed; no task code started')
    receipt=identity.with_name(identity.name+f'.gpu-binding-{os.getpid()}.json')
    record=dict(role='explicit_step_gpu_binding',utc=datetime.now(timezone.utc).isoformat(),
                allocation=env['SLURM_JOB_ID'],step=env['SLURM_STEP_ID'],minor=minor,uuid=uuid,
                gate=lines[0],driver_version=driver,adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                image=str(IMAGE),libraries={k:str(v) for k,v in libs.items()},
                source_commit=env.get('FORETS_SOURCE_COMMIT','unknown'))
    with receipt.open('x') as f:json.dump(record,f,indent=2)
    # No fallback on exec failure. The launched process retains its PID, matching
    # the server's normal child identity and termination handling.
    os.execve(REAL_SINGULARITY,final,clean)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # Never print argv / generated Jupyter auth tokens or inherited secrets.
        print('FORETS_GPU_BINDING_FAILED '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(70)
