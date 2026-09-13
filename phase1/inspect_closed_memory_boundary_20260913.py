"""Explain closed run failure and endpoint disagreement without changing either."""
import json
from pathlib import Path
import re
from forets_environment_build_20260912 import read, write, encode, sha
from audit_closed_error_families_20260913 import SECRET, ANSI
from read_forets_action_delivery_20260913 import read_latest

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb')
FINISH = 'bfb9ac89ce29b1c03553b28ce2314592e39afef9d66a44af1d8b143a4a4ab13a'


def main():
    finish = read(ROOT/'readout-finished.json', FINISH)
    for name, digest in finish['files'].items():
        if sha((ROOT/name).read_bytes()) != digest: raise ValueError('closed export drift')
    core = read(ROOT/'wallclock-summary.json')
    rows = read(ROOT/'memory-summary.json')['rows']
    failures = []
    for row in core['rows']:
        if row['technical_eligible']: continue
        block = 1 if row['seed'] == 40 else 2
        start = read(ROOT/f'block-{block}.runtime/started.json')
        task = read(ROOT/start['pool_manifest'])['tasks'][row['run_id']]
        if len(task['attempts']) != 1: raise ValueError('one original attempt only')
        identity = Path(task['attempts'][0]['identity_path'])
        if not identity.resolve().is_relative_to(ROOT/'runs/srun_pool'): raise ValueError('scope')
        path = identity.with_suffix('.bounded')/'execution/stderr.private.log'
        raw = path.read_bytes()
        safe = ANSI.sub('', SECRET.sub('[REDACTED]', raw.decode(errors='replace')))
        messages = re.findall(r'^\s*((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Expired|Timeout):[^\n]*)', safe, re.M)
        failures.append(dict(run_id=row['run_id'], log_sha256=sha(raw),
            exception_tail=[s[:500] for s in messages[-4:]],
            source_termination_reason=row['termination_reason'], eligibility_unchanged=True))
    differences = []
    for row in rows:
        if row['iteration_code_sha256'] == row['action_code_sha256']: continue
        source = next(r for r in core['rows'] if r['run_id'] == row['run_id'])
        data = read_latest(ROOT/'incumbents'/row['run_id'], start_ns=source['search_start_ns'], seconds=600)
        if data is None: raise ValueError('known action disappeared')
        matches = {}
        for endpoint in ('action', 'iteration'):
            found = [n for n in data['observed_nodes'] if n['code_sha256'] == row[endpoint+'_code_sha256']]
            matches[endpoint] = [{k:n[k] for k in ('node_id','search_value','maximize','is_buggy','code_sha256')} for n in found]
        differences.append(dict(run_id=row['run_id'], original_action_node=data['node_id'],
            observation_elapsed_seconds=(data['observation_ns']-data['start_ns'])/1e9,
            matching_observed_search_nodes=matches))
    result = dict(role='closed_memory_boundary_diagnosis_not_new_readout_or_reselection',
        source_finish_sha256=FINISH, failures=failures, endpoint_differences=differences,
        script_sha256=sha(Path(__file__).read_bytes()),
        limitations='Original frozen exclusions/endpoints unchanged; no retry or new score-based selection; redacted exception messages only.')
    digest = write(ROOT/'closed-memory-boundary.json', encode(result))
    print(json.dumps(dict(sha256=digest,**result)))


if __name__ == '__main__': main()
