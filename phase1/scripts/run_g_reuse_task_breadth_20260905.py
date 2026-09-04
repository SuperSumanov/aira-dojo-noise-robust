"""Run two producers and two independent verifiers into a new result root."""
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


def run(command, timeout):
    started = time.monotonic()
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, check=False, env={**os.environ,
                               'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1',
                               'MKL_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1'})
    return completed, time.monotonic() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    root, source_root = Path(args.root).absolute(), Path(args.source_root).absolute()
    if root.exists() or not source_root.is_dir():
        raise ValueError('root_exists_or_source_missing')
    root.mkdir(parents=True, mode=0o700)
    producer = source_root/'phase1/g_reuse_task_breadth.py'
    verifier = source_root/'phase1/verify_g_reuse_task_breadth.py'
    for path in (producer, verifier):
        if path.is_symlink() or not path.is_file():
            raise ValueError('unsafe_source')
    runs = []
    receipts = []
    for label in ('a', 'b'):
        completed, elapsed = run([sys.executable, '-B', str(producer)], 180)
        stdout_path, stderr_path = root/f'producer_{label}.json', root/f'producer_{label}.stderr'
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        runs.append(dict(role=f'producer_{label}', returncode=completed.returncode,
                         elapsed_seconds=elapsed, stdout_sha256=digest(stdout_path),
                         stderr_sha256=digest(stderr_path), stderr_bytes=stderr_path.stat().st_size))
        if completed.returncode != 0 or stderr_path.stat().st_size or not completed.stdout.endswith(b'\n'):
            raise RuntimeError('producer_failed')
        payload = json.loads(completed.stdout)
        if payload['source_sha256'] != digest(producer):
            raise RuntimeError('producer_source_mismatch')
        receipts.append(stdout_path)
    if receipts[0].read_bytes() != receipts[1].read_bytes():
        raise RuntimeError('producer_ab_mismatch')
    receipt_sha = digest(receipts[0])
    for label in ('a', 'b'):
        completed, elapsed = run([sys.executable, '-B', str(verifier), '--receipt',
                                  str(receipts[0]), '--sha256', receipt_sha], 180)
        stdout_path, stderr_path = root/f'verifier_{label}.json', root/f'verifier_{label}.stderr'
        stdout_path.write_bytes(completed.stdout)
        stderr_path.write_bytes(completed.stderr)
        runs.append(dict(role=f'verifier_{label}', returncode=completed.returncode,
                         elapsed_seconds=elapsed, stdout_sha256=digest(stdout_path),
                         stderr_sha256=digest(stderr_path), stderr_bytes=stderr_path.stat().st_size))
        if completed.returncode != 0 or stderr_path.stat().st_size or not completed.stdout.endswith(b'\n'):
            raise RuntimeError('verifier_failed')
    if (root/'verifier_a.json').read_bytes() != (root/'verifier_b.json').read_bytes():
        raise RuntimeError('verifier_ab_mismatch')
    payload = json.loads(receipts[0].read_bytes())
    independent = json.loads((root/'verifier_a.json').read_bytes())
    if payload['metrics'] != independent['metrics']:
        raise RuntimeError('aggregate_mismatch')
    context = dict(status='G_REUSE_TASK_BREADTH_RUN_COMPLETE', commit=args.commit,
                   python=sys.version, executable=sys.executable, source_sha256={
                   str(producer.relative_to(source_root)): digest(producer),
                   str(verifier.relative_to(source_root)): digest(verifier)},
                   producer_receipt_sha256=receipt_sha, runs=runs,
                   gpu_jobs=0, api_calls=0, model_fits=0)
    (root/'context.json').write_text(json.dumps(context, sort_keys=True, indent=2)+'\n')
    manifest = []
    for path in sorted(root.iterdir()):
        if path.name != 'SHA256SUMS':
            manifest.append(f'{digest(path)}  {path.name}')
    (root/'SHA256SUMS').write_text('\n'.join(manifest)+'\n')
    return dict(status=payload['status'], metrics=payload['metrics'],
                producer_receipt_sha256=receipt_sha, context_sha256=digest(root/'context.json'),
                manifest_sha256=digest(root/'SHA256SUMS'), runs=len(runs),
                gpu_jobs=0, api_calls=0, model_fits=0)


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
