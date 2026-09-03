"""Bounded CPU wrapper. Each child may only emit its aggregate JSON receipt."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

SOURCES = ['phase1/historical_global_local_source_gate.py',
           'phase1/verify_historical_global_local_source_gate.py',
           'phase1/historical_global_local_pool_readiness.py',
           'phase1/historical_train_encoding_readiness.py',
           'phase1/scripts/run_historical_global_local_source_gate_20260904.py']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if re.fullmatch('[0-9a-f]{40}', args.source_commit) is None:
        raise ValueError('full_commit_required')
    args.output.mkdir(exist_ok=False)
    source_hashes = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES}
    config = dict(source_commit=args.source_commit, source_hashes=source_hashes,
                  python=sys.version, platform=platform.platform(),
                  cpu_math_threads=1, child_timeout_seconds=180, model_fits=0, gpu_jobs=0, api_calls=0,
                  started_at_utc=datetime.now(timezone.utc).isoformat())
    (args.output / 'execution_context.json').write_text(json.dumps(config, indent=2, sort_keys=True) + '\n')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PYTHONHASHSEED='0')
    rows = []
    def child(name, module, extra=()):
        command = [sys.executable, '-B', '-m', module, *extra]
        started = time.monotonic()
        process = subprocess.run(command, env=env, capture_output=True, timeout=180)
        elapsed = time.monotonic() - started
        # Preserve failures without printing arbitrary child exception text.
        (args.output / f'{name}.json').write_bytes(process.stdout)
        stderr_hash = hashlib.sha256(process.stderr).hexdigest()
        rows.append(dict(name=name, command=json.dumps(command), source_commit=args.source_commit,
                         rc=process.returncode, elapsed_seconds=elapsed, stderr_bytes=len(process.stderr),
                         stderr_sha256=stderr_hash, seed='not_applicable', gpu_jobs=0, api_calls=0, model_fits=0))
        with (args.output / 'runs.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        if process.returncode or process.stderr:
            raise RuntimeError('child_failed_receipt_preserved_no_stderr_disclosed')
        json.loads(process.stdout)
        print(json.dumps(dict(stage=name, rc=process.returncode, elapsed_seconds=elapsed)), flush=True)
    for name in ('producer_a', 'producer_b'):
        child(name, 'phase1.historical_global_local_source_gate')
    a, b = [(args.output / f'{n}.json').read_bytes() for n in ('producer_a', 'producer_b')]
    if a != b:
        raise ValueError('producer_byte_drift')
    receipt = args.output / 'producer_a.json'
    digest = hashlib.sha256(a).hexdigest()
    for name in ('verifier_a', 'verifier_b'):
        child(name, 'phase1.verify_historical_global_local_source_gate',
              ['--receipt', str(receipt.resolve()), '--expect-receipt-sha256', digest])
    if (args.output / 'verifier_a.json').read_bytes() != (args.output / 'verifier_b.json').read_bytes():
        raise ValueError('verifier_byte_drift')
    if source_hashes != {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES}:
        raise ValueError('source_drift')
    outputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir() if p.is_file()}
    (args.output / 'manifest.json').write_text(json.dumps(outputs, sort_keys=True, indent=2) + '\n')
    print(json.dumps(dict(status='COMPLETE_NOT_EFFECT_ELIGIBLE', receipt_sha256=digest,
                         source_commit=args.source_commit)), flush=True)


if __name__ == '__main__':
    main()
