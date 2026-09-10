"""One real task-image CUDA check inside the replacement campaign allocation.

Uses the pinned task runtime's command builder, without datasets or a generator.
Does not install packages, modify the SIF, or substitute a host Python for it.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from forets_e2e_package import SOURCE, IMAGES, IMAGE_VERSION, write_new

CUDA_CODE = '''import json, torch
assert torch.cuda.is_available(), "task image has no working CUDA"
assert torch.cuda.device_count() == 1, "expected one assigned GPU"
p = torch.cuda.get_device_properties(0)
assert "3090" in p.name, "not the reviewed GPU family"
x = torch.ones((64, 64), device="cuda", requires_grad=True)
y = (x @ x).square().mean()
y.backward()
torch.cuda.synchronize()
assert x.is_cuda and x.grad.is_cuda and torch.isfinite(x.grad).all().item()
print("FORETS_CONTAINER_CUDA=" + json.dumps(dict(torch_version=torch.__version__,
    cuda_version=torch.version.cuda, gpu_name=p.name, capability=list(torch.cuda.get_device_capability(0)),
    gpu_total_memory_bytes=p.total_memory, forward_backward_cuda=True)))
'''


def validate_allocation_identity(environment, node):
    if node not in ('gpu27', 'gpu28') or environment.get('SLURMD_NODENAME') != node:
        raise RuntimeError('replacement deployment requires the reviewed 3090 node')
    if not environment.get('SLURM_JOB_ID', '').isdigit() or not environment.get('SLURM_STEP_ID', '').isdigit():
        raise RuntimeError('container check requires its own allocated Slurm step')
    if not environment.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('launcher did not assign a visible GPU')


def run(root, node):
    validate_allocation_identity(os.environ, node)
    from forets_e2e_campaign import validate_inputs
    _, configs = validate_inputs(root)
    cfg = configs[0]['interpreter']
    if (cfg['container_runtime'] != 'singularity' or cfg['superimage_directory'] != str(IMAGES)
            or cfg['superimage_version'] != IMAGE_VERSION or cfg['read_only_overlays'] or cfg['read_only_binds']):
        raise RuntimeError('unexpected task-image configuration')
    sys.path.insert(0, str(SOURCE/'src'))
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import (
        _build_singularity_command, _build_container_environment, _build_runtime_environment)
    import shutil
    executable = shutil.which('singularity')
    if not executable:
        raise RuntimeError('task Singularity executable is unavailable')
    work = root/'container-compatibility'
    work.mkdir(mode=0o700, exist_ok=False)
    image = IMAGES/('superimage.root.'+IMAGE_VERSION+'.sif')
    before = image.stat()
    container_env = _build_container_environment(cfg['env'])
    # Same task-image isolation and GPU exposure. No task data or private binds.
    command = _build_singularity_command(runtime_executable=executable, image_path=image,
        working_dir=work, bind_inputs_dir=None, read_only_overlays=[], read_only_binds={},
        container_env=container_env, token='unused-no-jupyter-server')
    python_index = command.index('python', command.index(str(image))+1)
    command = command[:python_index] + ['python', '-c', CUDA_CODE]
    environment = _build_runtime_environment(os.environ)
    for name in tuple(environment):
        if any(word in name.upper() for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')):
            environment.pop(name)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, env=environment, start_new_session=True, text=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=10)
    with os.fdopen(os.open(work/'runtime.private.log', os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600), 'w') as log:
        log.write(stdout); log.write(stderr)
    after = image.stat()
    rows = [line.partition('=')[2] for line in stdout.splitlines() if line.startswith('FORETS_CONTAINER_CUDA=')]
    if timed_out or process.returncode != 0 or len(rows) != 1:
        write_new(root/'container.compatibility.failed.json', dict(returncode=process.returncode, timed_out=timed_out))
        raise RuntimeError('task-image GPU check failed; inspect private log')
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('task image metadata changed during check')
    result = json.loads(rows[0])
    if result.get('forward_backward_cuda') is not True or '3090' not in result.get('gpu_name',''):
        raise RuntimeError('invalid GPU compatibility result')
    result.update(allocation_id=os.environ['SLURM_JOB_ID'], step_id=os.environ['SLURM_STEP_ID'],
        node=node, visible_gpu=os.environ['CUDA_VISIBLE_DEVICES'], image=str(image),
        image_bytes=before.st_size, image_mtime_ns=before.st_mtime_ns,
        image_content_rehashed=False, task_data_read=False, generator_calls=0)
    write_new(root/'container.compatibility.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--node', choices=('gpu27','gpu28'), required=True)
    args = parser.parse_args()
    run(args.package.resolve(strict=True), args.node)
