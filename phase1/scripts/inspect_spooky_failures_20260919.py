"""Closed-run bounded failure evidence; never repair or rerun candidates."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/comparison-spooky-pool-20260919-04qsl2xc')
EXPECTED = '721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1'
SECRET = re.compile(r'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{16,}|gh[pousr]_[a-z0-9]{16,}|github_pat_[a-z0-9_]{20,}|Bearer\s+[a-z0-9_.-]{20,}|AKIA[A-Z0-9]{16})')
SENSITIVE = re.compile(r'(?i)(api.?key|primary_key|password|access.?token|authorization|credential)')


def safe(line):
    if SENSITIVE.search(line):
        return '[REDACTED_SENSITIVE_LINE]'
    line = SECRET.sub('[REDACTED]', line)
    return re.sub(r'https?://\S+', '[URL]', line)[:800]


def main():
    import numpy as np
    import pandas as pd
    raw = (ROOT / 'summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError('closed summary drift')
    summary = json.loads(raw)
    failures, probabilities = [], []
    for row in summary['rows']:
        if row['valid'] is None:
            continue
        i = row['index']
        if row['valid'] is True:
            path = ROOT / f'work-{i}/submission.csv'
            meta = json.loads((ROOT / f'result-{i}.json').read_bytes())
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != meta['submission_sha256']:
                raise ValueError('submission identity')
            values = pd.read_csv(path)[['EAP', 'HPL', 'MWS']].to_numpy(dtype=float)
            sums = values.sum(axis=1)
            probabilities.append(dict(seed=row['seed'], slot=row['slot'],
                max_row_sum_absolute_deviation=float(np.max(np.abs(sums - 1))),
                within_frozen_tolerance=bool(np.allclose(sums, 1, rtol=1e-5, atol=1e-6))))
            continue
        path = ROOT / f'output-{i}.private.log'
        if path.is_symlink():
            raise ValueError('log symlink')
        with path.open('rb') as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            text = handle.read().decode(errors='replace')
        lines = [line for line in text.splitlines()
                 if re.search(r'(?i)(error|exception|killed|out of memory|not ready|timed? ?out)', line)]
        failures.append(dict(seed=row['seed'], slot=row['slot'], original_selected=row['original_selected'],
            exit_code=row.get('exit_code'), timed_out=row.get('timed_out'),
            bounded_redacted_error_lines=[safe(line) for line in lines[-4:]],
            cuda_architecture_marker=bool(re.search(r'no kernel image|invalid device function|unsupported.*(?:sm_|compute capability)', text, re.I)),
            kernel_readiness_marker='Kernel did not become ready in time' in text,
            caveat='Bounded exception evidence; no proof of a common cause from a missing marker.'))
    result = dict(summary_sha256=EXPECTED, failures=failures, probabilities=probabilities,
                  no_truth_rows_read=True, no_program_or_result_modified=True)
    encoded = json.dumps(result, indent=2, allow_nan=False)
    if SECRET.search(encoded):
        raise ValueError('redaction failure')
    with (ROOT / 'failure-evidence.redacted.json').open('x') as handle:
        handle.write(encoded)
    print(encoded)


if __name__ == '__main__':
    main()
