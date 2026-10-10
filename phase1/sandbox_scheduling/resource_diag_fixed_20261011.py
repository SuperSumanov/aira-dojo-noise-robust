"""Independent same-matrix validation of buffered-pipe readiness repair.

Old 17541 remains 7/14 attempted,6 complete. No timeout increase or label use.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import resource_diag_20261011 as d

DONOR = d.BASE / 'resource-diag-20261011-v5'
DONOR_SHA = '062087df7b04a8032a50e60bfdc7761a116188b850e8250b2a06cb7dc04552d1'
ROOT = d.BASE / 'resource-diag-readiness-fixed-20261011-v1'
NAME = Path(__file__).name
d.ROOT = ROOT
d.NAME = NAME


def prepare():
    if d.sha(DONOR / 'plan.json') != DONOR_SHA:
        raise ValueError('donor drift')
    old = json.loads((DONOR / 'plan.json').read_text())
    closed = json.loads((DONOR / 'closed.json').read_text())
    if (closed['planned'], closed['attempted'], closed['complete']) != (14, 7, 6):
        raise ValueError('wrong failed matrix')
    ROOT.mkdir(mode=0o700)
    for name, digest in old['files'].items():
        if d.sha(DONOR / name) != digest:
            raise ValueError('donor file drift')
        target = ROOT / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DONOR / name, target)
    for name in (NAME, 'gateway_readiness_overlay.py', 'test_gateway_pipe_readiness.py'):
        shutil.copyfile(Path(__file__).with_name(name), ROOT / name)
    from gateway_readiness_overlay import overlay
    target = ROOT / 'source/src/dojo/core/interpreters/jupyter/singularity_jupyter_server.py'
    original = target.read_text()
    patched = overlay(original, Path(__file__).with_name('singularity_jupyter_server.py').read_text())
    target.write_text(patched)
    for row in d.schedule():
        (ROOT / f"block-{row['block']}-worker-{row['index']}").mkdir()
    batch = (DONOR / 'run.sbatch').read_text().replace(str(DONOR), str(ROOT))
    batch = batch.replace('resource_diag_20261011.py', NAME).replace('resource-diag-v5', 'resource-readiness-fix')
    (ROOT / 'run.sbatch').write_text(batch)
    subprocess.run(['bash', '-n', str(ROOT / 'run.sbatch')], check=True)
    env = dict(os.environ, GATEWAY_SOURCE=str(target), PYTHONDONTWRITEBYTECODE='1')
    test = subprocess.run([str(d.PY), str(ROOT / 'test_gateway_pipe_readiness.py')], env=env,
                          capture_output=True, text=True, timeout=15)
    if test.returncode:
        raise ValueError('real-pipe regressions failed')
    d.configure()
    from dojo.core.interpreters.jupyter.singularity_jupyter_server import SingularityJupyterServer
    d.write(ROOT / 'preflight-fixed.json', dict(real_pipe_tests_pass=True, unchanged_image_pin=old['image_sha256'],
            image_reuse='Original immutable task image, fully rehashed in immediately preceding donor preparation; no image writes.',
            identity_publication_retained=original.count('_publish_container_identity(')==patched.count('_publish_container_identity(')))
    plan = {key: value for key, value in old.items() if key != 'files'}
    plan.update(donor_plan_sha256=DONOR_SHA, previous_job='17541',
         previous_planned=14, previous_attempted=7, previous_complete=6,
         previous_allocated_gpu_seconds=132, new_gpu_seconds_cap=1200,
         intervention='single buffered-pipe reader from startup, queue-based bounded readiness; no timeout extension',
         cleanup_exception_patch_included=False,
         evidence='Old frozen methods fail coalesced real-pipe readiness; new methods pass5 Linux/Windows pipe tests.',
         files={str(p.relative_to(ROOT)):d.sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    d.write(ROOT / 'plan.json', plan)
    print(json.dumps(dict(prepared=True, root=str(ROOT), plan_sha256=d.sha(ROOT / 'plan.json'))))


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'prepare':
        prepare()
    elif mode == 'allocation':
        d.write(ROOT / 'allocation.json', d.resource_pressure.snapshot())
    elif mode == 'controller':
        d.controller()
    elif mode == 'worker':
        sys.exit(d.worker(*map(int, sys.argv[2:])))
    else:
        raise ValueError('mode')
