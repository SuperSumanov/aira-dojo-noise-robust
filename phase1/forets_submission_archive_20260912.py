"""Passive, host-only grading evidence for a FUTURE ForeTS release.

Not installed into job 13115. This helper never grades, launches, selects, or
returns new feedback to an agent. Preserve the exact bytes read by the original
grader, and its original report, for post-closeout numerical verification.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile

LIMIT = 64 * 1024 * 1024


def snapshot_submission(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('submission must be a regular file')
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('submission evidence exceeds size limit')
    return raw


def archive_submission(path, before, report, output):
    """Call after grading and before the framework deletes the submission.

The release must bind output to a host-only directory outside the sandbox.
No overwrite or score repair. Any interrupted directory remains as evidence.
"""
    if type(before) is not bytes or len(before) > LIMIT:
        raise ValueError('bounded original submission bytes required')
    if snapshot_submission(path) != before:
        raise ValueError('submission changed during grading')
    report_raw = (json.dumps(report, sort_keys=True, allow_nan=False) + '\n').encode()
    output = Path(output)
    if output.is_symlink():
        raise ValueError('archive root is a symlink')
    output.mkdir(mode=0o700, parents=False, exist_ok=True)
    leaf = Path(tempfile.mkdtemp(prefix='grade-', dir=output))
    os.chmod(leaf, 0o700)
    for name, raw in (('submission.csv', before), ('report.json', report_raw)):
        with (leaf/name).open('xb') as stream:
            stream.write(raw)
        os.chmod(leaf/name, 0o600)
    receipt = dict(schema=1, submission_sha256=hashlib.sha256(before).hexdigest(),
                   report_sha256=hashlib.sha256(report_raw).hexdigest(),
                   submission_bytes=len(before))
    with (leaf/'complete.json').open('x') as stream:
        json.dump(receipt, stream, sort_keys=True, allow_nan=False)
    os.chmod(leaf/'complete.json', 0o600)
    return receipt


def patch_evaluator(source):
    """Exact anchors only; the caller pins the actual source tree separately."""
    changes = (
        ('import pandas as pd\n', 'import pandas as pd\nfrom .submission_archive import snapshot_submission, archive_submission\n'),
        ('    if submission_exists:\n        submission_df = read_csv(submission_path)',
         '    if submission_exists:\n        submission_raw = snapshot_submission(submission_path)\n        submission_df = read_csv(submission_path)'),
        ('    results_output_dir.mkdir(exist_ok=True)\n',
         '    results_output_dir.mkdir(exist_ok=True)\n'
         '    if submission_exists:\n'
         '        archive_submission(submission_path, submission_raw, report.to_dict(),\n'
         '                           results_output_dir / "submission-escrow")\n'),
    )
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError('unexpected evaluator source anchor')
        source = source.replace(old, new)
    return source
