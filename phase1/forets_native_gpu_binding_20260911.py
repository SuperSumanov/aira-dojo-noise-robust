"""Bind the GPU selected by native Slurm/CUDA visibility, not a Slurm ordinal.

The retired adapter's execution path remains disabled. Reuse only its pure
command builder. Both original image and task payload remain unchanged.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone

from forets_gpu_binding_20260911 import REAL_SINGULARITY, split_command, rewrite
from forets_opencl_allowlist_20260911 import driver_binds
from forets_native_cuda_identity_20260911 import identity as native_identity


def resolve_native(record, *, device_stat=os.lstat):
    matches=record.get('driver_metadata_matches',[])
    if (record.get('device_count')!=1 or record.get('cuda_visible_devices')!='0'
            or len(matches)!=1 or not re.fullmatch(r'GPU-[a-fA-F0-9-]{36}',record.get('selected_uuid',''))):
        raise ValueError('ambiguous native CUDA identity')
    match=matches[0]
    if match.get('bus_location','').lower()!=record.get('pci_bus_id','').lower():
        raise ValueError('native CUDA and proc PCI identity differ')
    minor=match.get('device_minor','')
    if not re.fullmatch(r'\d+',minor):raise ValueError('missing physical minor')
    minor=int(minor)
    # Only map a CUDA-selected UUID via its driver metadata. No Slurm/NVML
    # index conversion, no STEP_ID/GPU equality requirement, no default GPU9.
    info=device_stat('/dev/nvidia'+str(minor))
    if not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev)!=195 or os.minor(info.st_rdev)!=minor:
        raise ValueError('native device metadata and node differ')
    return minor,record['selected_uuid']


def main(args=None):
    args=list(sys.argv[1:] if args is None else args)
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args)
    root=Path(os.environ.get('FORETS_NATIVE_INTEGRATION_ROOT','')).resolve(strict=True)
    if (root.parent!=Path('/research/d7/spc/yzyang4')
            or not root.name.startswith('forets-native-gpu-adapter-20260911-')):
        raise ValueError('only the new bounded integration root is enabled')
    receipt=Path(os.environ.get('DOJO_WORKER_IDENTITY_PATH',''))
    if not receipt.is_absolute() or receipt.is_symlink() or receipt.parent.resolve()!=root:
        raise ValueError('receipt outside integration root')
    observed=native_identity()
    minor,uuid=resolve_native(observed)
    cache=subprocess.run(['/sbin/ldconfig','-p'],capture_output=True,text=True,timeout=10,check=True).stdout
    libraries=driver_binds(cache)
    vendors=Path(__file__).with_name('opencl-vendors')
    if (vendors/'nvidia.icd').read_text().strip()!='libnvidia-opencl.so.1':raise ValueError('ICD changed')
    final,gate=rewrite(args,minor=minor,uuid=uuid,libraries=libraries,vendors=vendors)
    clean={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    checked=subprocess.run(gate,env=clean,capture_output=True,text=True,timeout=25)
    rows=[json.loads(x.removeprefix('ALLOWLIST_GATE ')) for x in checked.stdout.splitlines()
          if x.startswith('ALLOWLIST_GATE ')]
    if checked.returncode or len(rows)!=1 or rows[0].get('exact_device_namespace') is not True:
        raise RuntimeError('native-selected device namespace check failed')
    report=dict(role='native_cuda_selected_device_binding_not_effect',
        utc=datetime.now(timezone.utc).isoformat(),native_identity=observed,namespace=rows[0],
        source_commit=os.environ.get('FORETS_SOURCE_COMMIT'),
        adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with receipt.with_suffix('.native-binding.json').open('x') as f:json.dump(report,f,indent=2)
    os.execve(REAL_SINGULARITY,final,clean)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FORETS_NATIVE_BINDING_FAILED '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(70)
