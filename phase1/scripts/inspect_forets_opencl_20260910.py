"""Read only image metadata on login CPU; no GPU exposure, task or training."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

IMAGE = Path('/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif')
CODE = '''import json, pathlib, ctypes.util
p=pathlib.Path('/etc/OpenCL/vendors')
print(json.dumps(dict(vendor_directory_exists=p.is_dir(),
    icd_files=sorted(x.name for x in p.glob('*.icd')) if p.is_dir() else [],
    loader_library=ctypes.util.find_library('OpenCL'))))
'''


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    before=IMAGE.stat()
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD'))}
    env['CUDA_VISIBLE_DEVICES']=''
    command=[shutil.which('singularity') or 'singularity', 'exec', '--containall', '--cleanenv', '--no-home',
             str(IMAGE), 'python', '-c', CODE]
    run=subprocess.run(command, capture_output=True, text=True, env=env, timeout=45)
    after=IMAGE.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    report=dict(role='image_filesystem_inspection_not_gpu_execution', image=str(IMAGE),
        gpu_requested=False, task_executions=0, source_image_unchanged=True, returncode=run.returncode)
    if run.returncode==0:
        report['image_opencl']=json.loads(run.stdout.strip().splitlines()[-1])
    else:
        report['error']='container_metadata_inspection_failed'
    with args.output.open('x') as f:
        json.dump(report,f,indent=2)
        f.write('\n')
    print(json.dumps(report))
    raise SystemExit(run.returncode)


if __name__=='__main__':main()
