"""Native GPU binding for the explicitly bounded saved DEVELOPMENT pool only."""
import json
import os
from pathlib import Path
import subprocess
import sys
from forets_closed_pool_20260911 import binding_context, now, write
from forets_native_gpu_binding_20260911 import resolve_native, native_identity
from forets_gpu_binding_20260911 import REAL_SINGULARITY, split_command, rewrite
from forets_opencl_allowlist_20260911 import driver_binds

def main():
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args);path=binding_context(os.environ)
    observed=native_identity();minor,uuid=resolve_native(observed)
    cache=subprocess.run(['/sbin/ldconfig','-p'],capture_output=True,text=True,timeout=10,check=True).stdout
    vendors=Path(__file__).with_name('opencl-vendors')
    if (vendors/'nvidia.icd').read_text().strip()!='libnvidia-opencl.so.1':raise ValueError('ICD changed')
    final,gate=rewrite(args,minor=minor,uuid=uuid,libraries=driver_binds(cache),vendors=vendors)
    clean={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    check=subprocess.run(gate,env=clean,capture_output=True,text=True,timeout=25)
    rows=[json.loads(s.removeprefix('ALLOWLIST_GATE ')) for s in check.stdout.splitlines() if s.startswith('ALLOWLIST_GATE ')]
    if check.returncode or len(rows)!=1 or rows[0].get('exact_device_namespace') is not True:raise RuntimeError('namespace failure')
    write(path,dict(role='closed_pool_native_binding_not_e2e',utc=now(),native_identity=observed,namespace=rows[0]))
    os.execve(REAL_SINGULARITY,final,clean)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('CLOSED_POOL_BINDING_FAILED '+type(exc).__name__,file=sys.stderr);raise SystemExit(70)
