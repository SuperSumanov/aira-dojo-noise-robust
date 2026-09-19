"""Check whether fresh original-choice failures also occurred in production.

Only the four already executed original choices are read. Candidate code stays
remote and is only hashed. Matching an error message is not matching hardware.
"""
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath
from discover_comparison_20260919 import SECRET, safe_text

BASE = Path('/research/d7/spc/yzyang4')
ROOT = BASE / 'comparison-spooky-pool-20260919-04qsl2xc'
SUMMARY = '721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1'


def strings(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return '\n'.join(strings(v) for v in (value.values() if isinstance(value, dict) else value))
    return ''


def main():
    raw = (ROOT / 'summary.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != SUMMARY:
        raise ValueError('summary changed')
    wanted = {r['node']: r for r in json.loads(raw)['rows']
              if r['original_selected'] and r['valid'] is False}
    fresh = json.loads((ROOT / 'failure-evidence.redacted.json').read_bytes())
    if fresh['summary_sha256'] != SUMMARY:
        raise ValueError('fresh evidence identity')
    messages = {(r['seed'], r['slot']): r['bounded_redacted_error_lines'][-1]
                for r in fresh['failures'] if r['original_selected']}
    rows = []
    archive_path = BASE / 'comparison-quarantine-20260919-_tda9fh6/archives/spooky-author-identification.tar.gz'
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            if not member.isfile() or PurePosixPath(member.name).name != 'journal.jsonl':
                continue
            for line in archive.extractfile(member):
                node = json.loads(SECRET.sub('[REDACTED]', line.decode()))
                if node.get('id') not in wanted:
                    continue
                row = wanted[node['id']]
                if hashlib.sha256((node.get('code') or '').encode()).hexdigest() != row['raw_code_sha256']:
                    raise ValueError('candidate identity')
                text = strings(node.get('term_out')) + '\n' + strings(node.get('_term_out'))
                text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
                final = messages[(row['seed'], row['slot'])]
                matches = [line.strip() for line in text.splitlines() if line.strip() == final]
                rows.append(dict(seed=row['seed'], slot=row['slot'], node=node['id'],
                    same_code_sha256=row['raw_code_sha256'], historical_buggy=node.get('is_buggy'),
                    historical_execution_seconds=node.get('exec_time'),
                    fresh_terminal_error=safe_text(final),
                    exact_error_line_in_historical_output=bool(matches),
                    historical_kernel_readiness_marker='Kernel did not become ready in time' in text))
    if len(rows) != len(wanted) or len({r['node'] for r in rows}) != len(wanted):
        raise ValueError('scope incomplete')
    result = dict(summary_sha256=SUMMARY, rows=rows,
                  all_same_error_line=all(r['exact_error_line_in_historical_output'] for r in rows),
                  caveat='Exact bounded error-line recurrence, not a controlled runtime-version attribution or repair.')
    encoded = json.dumps(result, indent=2, allow_nan=False)
    if SECRET.search(encoded):
        raise ValueError('unsafe evidence')
    with (ROOT / 'historical-errors.redacted.json').open('x') as handle:
        handle.write(encoded)
    print(encoded)


if __name__ == '__main__':
    main()
