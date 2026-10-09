"""CPU-only --help entry probe: no kernel/server/model/data/GPU is started.

The original frozen observer remains unchanged. The alternate entry exists
only in this diagnostic's private temporary directory, not production/runtime.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from lifecycle_pilot import write, sha

BASE = Path('/research/d7/spc/yzyang4')
IMAGE = BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'
ORIGINAL = BASE/'scheduling-readiness-gateway-20261009-v1/gateway_counter.py'
DEST = BASE/'scheduling-gateway-entry-probe-20261009-v1.json'


def main():
    if DEST.exists():
        raise ValueError('one-time diagnostic already exists')
    original = ORIGINAL.read_text()
    old = "if __name__=='__main__':runpy.run_module('jupyter',run_name='__main__')"
    new = "if __name__=='__main__':\n    from kernel_gateway.gatewayapp import KernelGatewayApp\n    KernelGatewayApp.launch_instance(argv=__import__('sys').argv[2:])"
    if original.count(old) != 1:
        raise ValueError('exact frozen entry shape')
    probe = Path(tempfile.mkdtemp(prefix='gateway-help-probe-', dir=BASE))
    os.chmod(probe, 0o700)
    rows = []
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'USER', 'LOGNAME') if k in os.environ}
    for name, source in [('original_cli', original), ('direct_help_entry', original.replace(old, new))]:
        directory = probe/name
        directory.mkdir(mode=0o700)
        script = directory/'counter.py'
        script.write_text(source)
        command = ['singularity', 'exec', '--containall', '--cleanenv', '--no-home',
                   '--no-mount', 'hostfs,bind-paths', '--bind', str(directory)+':/workspace',
                   '--pwd', '/workspace', str(IMAGE), 'python', '/workspace/counter.py', 'kernelgateway', '--help']
        result = subprocess.run(command, env=env, capture_output=True, timeout=45)
        counter = directory/'gateway-counts.json'
        counts = json.loads(counter.read_text()) if counter.exists() else None
        rows.append(dict(entry=name, returncode=result.returncode, source_sha256=sha(script),
                         counter_exists=counter.exists(), counts=counts,
                         stdout_bytes=len(result.stdout), stderr_bytes=len(result.stderr),
                         stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
    confirmed = (all(r['returncode'] == 0 for r in rows)
                 and not rows[0]['counter_exists'] and rows[1]['counter_exists'] and rows[1]['counts'] == {})
    value = dict(original_sha256=sha(ORIGINAL), analysis_sha256=sha(Path(__file__)),
                 help_entry_process_boundary_confirmed=confirmed, rows=rows,
                 no_kernel_or_server_started=True, no_gpu_model_data_api=True,
                 boundary='Confirms observer process survival on --help only, not operational transport capture, '
                          'not the cause/fix of original kernel readiness failure; no live experiment changed.')
    write(DEST, value)
    print(json.dumps(dict(receipt_sha256=sha(DEST), **value)))


if __name__ == '__main__':
    os.umask(0o077)
    main()
