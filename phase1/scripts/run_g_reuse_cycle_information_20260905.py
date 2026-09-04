"""Run producer/verifier A/B for frozen G-reuse cycle-information diagnostic."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def close(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(close(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close(a, b) for a, b in zip(left, right))
    if isinstance(left, float) or isinstance(right, float):
        return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=1e-7)
    return left == right


def execute(command):
    start = time.monotonic()
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240,
                          check=False, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                          'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
    return done, time.monotonic()-start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root, source = args.root.absolute(), args.source_root.absolute()
    if root.exists() or not source.is_dir():
        raise ValueError('root_exists_or_source_missing')
    root.mkdir(parents=True, mode=0o700)
    producer = source/'phase1/g_reuse_cycle_information.py'
    verifier = source/'phase1/verify_g_reuse_cycle_information.py'
    records, producer_paths = [], []
    for label in ('a', 'b'):
        done, elapsed = execute([sys.executable, '-B', str(producer)])
        stdout, stderr = root/f'producer_{label}.json', root/f'producer_{label}.stderr'
        stdout.write_bytes(done.stdout); stderr.write_bytes(done.stderr)
        records.append({'role': f'producer_{label}', 'returncode': done.returncode,
                        'elapsed_seconds': elapsed, 'stdout_sha256': digest(stdout),
                        'stderr_sha256': digest(stderr), 'stderr_bytes': stderr.stat().st_size})
        if done.returncode or stderr.stat().st_size or not done.stdout.endswith(b'\n'):
            raise RuntimeError('producer_failed')
        if json.loads(done.stdout)['source_sha256'] != digest(producer):
            raise RuntimeError('producer_source_mismatch')
        producer_paths.append(stdout)
    if producer_paths[0].read_bytes() != producer_paths[1].read_bytes():
        raise RuntimeError('producer_ab_mismatch')
    receipt_sha = digest(producer_paths[0])
    verifier_paths = []
    for label in ('a', 'b'):
        done, elapsed = execute([sys.executable, '-B', str(verifier), '--receipt',
                                 str(producer_paths[0]), '--sha256', receipt_sha])
        stdout, stderr = root/f'verifier_{label}.json', root/f'verifier_{label}.stderr'
        stdout.write_bytes(done.stdout); stderr.write_bytes(done.stderr)
        records.append({'role': f'verifier_{label}', 'returncode': done.returncode,
                        'elapsed_seconds': elapsed, 'stdout_sha256': digest(stdout),
                        'stderr_sha256': digest(stderr), 'stderr_bytes': stderr.stat().st_size})
        if done.returncode or stderr.stat().st_size or not done.stdout.endswith(b'\n'):
            raise RuntimeError('verifier_failed')
        verifier_paths.append(stdout)
    verifier_a = json.loads(verifier_paths[0].read_bytes())
    verifier_b = json.loads(verifier_paths[1].read_bytes())
    if not close(verifier_a, verifier_b):
        raise RuntimeError('verifier_ab_not_close')
    payload, verified = json.loads(producer_paths[0].read_bytes()), json.loads(verifier_paths[0].read_bytes())
    if not close(payload['metrics'], verified['metrics']):
        raise RuntimeError('producer_verifier_mismatch')
    context = {'status': 'G_REUSE_CYCLE_INFORMATION_RUN_COMPLETE', 'commit': args.commit,
               'python': sys.version, 'executable': sys.executable,
               'source_sha256': {str(producer.relative_to(source)): digest(producer),
                                 str(verifier.relative_to(source)): digest(verifier)},
               'producer_receipt_sha256': receipt_sha, 'runs': records,
               'producer_ab_requirement': 'byte_exact',
               'verifier_ab_requirement': 'recursive_rel_1e-8_abs_1e-7',
               'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}
    (root/'context.json').write_text(json.dumps(context, indent=2, sort_keys=True)+'\n')
    lines = [f'{digest(path)}  {path.name}' for path in sorted(root.iterdir()) if path.name != 'SHA256SUMS']
    (root/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
    return {'status': payload['status'], 'metrics': payload['metrics'],
            'producer_receipt_sha256': receipt_sha, 'context_sha256': digest(root/'context.json'),
            'manifest_sha256': digest(root/'SHA256SUMS'), 'runs': len(records),
            'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
