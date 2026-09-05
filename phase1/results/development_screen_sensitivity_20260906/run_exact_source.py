import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

commit = '48f58fe7eff0ea31b1f8764696e25fad5408ff32'
paths = ['phase1/development_screen_operating_characteristics_v1.json',
    'phase1/development_screen_operating_characteristics.py',
    'phase1/verify_development_screen_operating_characteristics.py',
    'phase1/tests/test_development_screen_operating_characteristics.py']
hashes = {}
for name in paths:
    raw = Path(name).read_bytes()
    assert raw == subprocess.check_output(['git', 'show', commit+':'+name])
    hashes[name] = hashlib.sha256(raw).hexdigest()
root = Path('tmp/screen-sensitivity-48f58fe')
assert not root.exists(); root.mkdir()
env = os.environ.copy()
env.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
    PYTHONDONTWRITEBYTECODE='1')
start = time.monotonic()
commands = [
    [sys.executable, '-m', 'pytest', paths[-1], '-q'],
    [sys.executable, '-m', 'phase1.development_screen_operating_characteristics',
     '--protocol', paths[0], '--output', str(root/'simulation'), '--commit', commit],
    [sys.executable, '-m', 'phase1.verify_development_screen_operating_characteristics',
     '--protocol', paths[0], '--result', str(root/'simulation/result.json'),
     '--output', str(root/'verification.json')],
]
record = {'commit': commit, 'source_sha256': hashes, 'commands': commands, 'returncodes': []}
try:
    for index, argv in enumerate(commands):
        with (root/f'step-{index}.log').open('xb') as f:
            r = subprocess.run(argv, env=env, stdout=f, stderr=subprocess.STDOUT,
                               timeout=max(1, 600-(time.monotonic()-start)))
        record['returncodes'].append(r.returncode)
        if r.returncode: raise RuntimeError(f'step_{index}_rc_{r.returncode}')
finally:
    record['elapsed_seconds'] = time.monotonic()-start
    (root/'execution.json').write_text(json.dumps(record, sort_keys=True, indent=2))
print((root/'verification.json').read_text())
