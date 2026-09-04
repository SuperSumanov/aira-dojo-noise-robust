"""Run deterministic A/B producers and A/B independent verifiers into a fresh root."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def execute(command, timeout):
    started = time.monotonic()
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, check=False,
                               env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                                    'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                                    'OPENBLAS_NUM_THREADS': '1'})
    return completed, time.monotonic()-started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root, source_root = args.root.absolute(), args.source_root.absolute()
    if root.exists() or not source_root.is_dir():
        raise ValueError('root_exists_or_source_missing')
    root.mkdir(parents=True, mode=0o700)
    producer = source_root/'phase1/g_reuse_record_consistent_sensitivity.py'
    verifier = source_root/'phase1/verify_g_reuse_record_consistent_sensitivity.py'
    for path in (producer, verifier):
        if path.is_symlink() or not path.is_file():
            raise ValueError('unsafe_source')
    records, producer_paths = [], []
    for label in ('a', 'b'):
        completed, elapsed = execute([sys.executable, '-B', str(producer)], 180)
        stdout, stderr = root/f'producer_{label}.json', root/f'producer_{label}.stderr'
        stdout.write_bytes(completed.stdout); stderr.write_bytes(completed.stderr)
        records.append({'role': f'producer_{label}', 'returncode': completed.returncode,
                        'elapsed_seconds': elapsed, 'stdout_sha256': digest(stdout),
                        'stderr_sha256': digest(stderr), 'stderr_bytes': stderr.stat().st_size})
        if completed.returncode or stderr.stat().st_size or not completed.stdout.endswith(b'\n'):
            raise RuntimeError('producer_failed')
        if json.loads(completed.stdout)['source_sha256'] != digest(producer):
            raise RuntimeError('producer_source_mismatch')
        producer_paths.append(stdout)
    if producer_paths[0].read_bytes() != producer_paths[1].read_bytes():
        raise RuntimeError('producer_ab_mismatch')
    receipt_sha = digest(producer_paths[0])
    verifier_paths = []
    for label in ('a', 'b'):
        completed, elapsed = execute([sys.executable, '-B', str(verifier), '--receipt',
                                      str(producer_paths[0]), '--sha256', receipt_sha], 180)
        stdout, stderr = root/f'verifier_{label}.json', root/f'verifier_{label}.stderr'
        stdout.write_bytes(completed.stdout); stderr.write_bytes(completed.stderr)
        records.append({'role': f'verifier_{label}', 'returncode': completed.returncode,
                        'elapsed_seconds': elapsed, 'stdout_sha256': digest(stdout),
                        'stderr_sha256': digest(stderr), 'stderr_bytes': stderr.stat().st_size})
        if completed.returncode or stderr.stat().st_size or not completed.stdout.endswith(b'\n'):
            raise RuntimeError('verifier_failed')
        verifier_paths.append(stdout)
    if verifier_paths[0].read_bytes() != verifier_paths[1].read_bytes():
        raise RuntimeError('verifier_ab_mismatch')
    payload, verified = json.loads(producer_paths[0].read_bytes()), json.loads(verifier_paths[0].read_bytes())
    if payload['metrics'] != verified['metrics']:
        raise RuntimeError('producer_verifier_mismatch')
    context = {'status': 'G_REUSE_RECORD_CONSISTENT_RUN_COMPLETE', 'commit': args.commit,
               'python': sys.version, 'executable': sys.executable,
               'source_sha256': {str(producer.relative_to(source_root)): digest(producer),
                                 str(verifier.relative_to(source_root)): digest(verifier)},
               'producer_receipt_sha256': receipt_sha, 'runs': records,
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
