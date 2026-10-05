"""Independent closed-readout arithmetic, repeatability and missingness check.

No new executions, altered candidates, per-case rescue rules or outcome selection.
Same-code repetitions diagnose this batch only, not task-level generalization.
"""
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys

ROOT = Path('/research/d7/spc/yzyang4/collateral-factorial-20261006-v1')
PLAN_SHA = '57dbaec816abda184f99abe0f8738e0350d0d0cb18602f5c8822eea50aeabcce'


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_bytes())


def save(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def contrast(values):
    if any(values[k] is None for k in ('P', 'C', 'CP', 'PC')):
        return None
    p, c, cp, pc = (Decimal(str(values[k])) for k in ('P', 'C', 'CP', 'PC'))
    return dict(CP_minus_P=float(cp-p), C_minus_P=float(c-p),
                CP_minus_C=float(cp-c), PC_minus_P=float(pc-p),
                interaction=float((c-p)-(cp-p)-(pc-p)), rescue=cp>p and c<=p)


def main():
    assert digest(ROOT/'plan.json') == PLAN_SHA
    assert read(ROOT/'closed.json')['assigned'] == 32
    result = ROOT/'readout-v1'
    for name, expected in read(result/'export-receipt.json').items():
        assert digest(result/name) == expected
    summary = read(result/'summary.json')
    assert summary['assigned'] == 32 and summary['plan_sha256'] == PLAN_SHA
    with (result/'runs.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 32 and {int(r['index']) for r in rows} == set(range(32))
    by_case = {i: {r['arm']: r for r in rows if int(r['case']) == i} for i in range(8)}
    checks, feasibility = [], []
    for i, group in by_case.items():
        assert set(group) == {'P', 'C', 'CP', 'PC'}
        values = {a: float(r['dev_metric']) if r['dev_metric'] else None for a, r in group.items()}
        independent = contrast(values)
        reported = next(c for c in summary['contrasts'] if c['case'] == i)
        assert reported['complete'] == (independent is not None)
        if independent is not None:
            for k, value in independent.items():
                if isinstance(value, bool):
                    assert reported[k] == value
                else:
                    assert abs(reported[k]-value) < 1e-12
        checks.append(dict(case=i, values=values, independent=independent))
        feasibility.append(dict(case=i, task=group['P']['task'],
            C_valid=values['C'] is not None, CP_valid=values['CP'] is not None))
    parent_groups = {}
    for r in rows:
        if r['arm'] == 'P':
            parent_groups.setdefault(r['code_sha256'], []).append(r)
    repeats=[]
    for code_sha, group in parent_groups.items():
        valid = [r for r in group if r['dev_metric']]
        vals = [float(r['dev_metric']) for r in valid]
        repeats.append(dict(code_sha256=code_sha, cases=[int(r['case']) for r in group],
            valid=len(valid), unique_prediction_hashes=len({r['prediction_sha256'] for r in valid}),
            observed_range=max(vals)-min(vals) if vals else None,
            sample_variance=statistics.variance(vals) if len(vals)>1 else None,
            limitation='Potentially repeated internal seeds; not independent task replicates.'))
    failures=[]
    for r in rows:
        if r['valid'] == 'True':
            continue
        ep=ROOT/f"episode-{r['index']}"
        terminal=ep/'action-0/terminal.private.json'
        categories=[]
        if terminal.exists():
            raw=read(terminal)['terminal']
            categories=re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception))\s*:', raw)
        failures.append(dict(index=int(r['index']), case=int(r['case']), arm=r['arm'],
            completed=r['completed'], error_type=r['error_type'], timed_out=r['timed_out'],
            step_returncode=r['step_returncode'], terminal_exception_types=sorted(set(categories))))
    costs=[]
    for arm in ('P','C','CP','PC'):
        group=[r for r in rows if r['arm']==arm]
        times=[float(r['seconds']) for r in group if r['seconds']]
        costs.append(dict(arm=arm, assigned=len(group), valid=sum(r['valid']=='True' for r in group),
            recorded_worker_seconds=sum(times), median_worker_seconds=statistics.median(times) if times else None))
    output=dict(status='PASS', plan_sha256=PLAN_SHA, summary_sha256=digest(result/'summary.json'),
        script_sha256=digest(__file__), arithmetic_implementation='decimal direct independent expressions',
        assigned=32, distinct_parent_code=len(parent_groups), contrasts=checks,
        feasibility=feasibility, parent_repeats=repeats, failures=failures, costs=costs,
        actual_allocated_gpu_hours=summary['allocated_gpu_hours'],
        boundary='Descriptive old-development mechanism test. No data-dependent rule, oracle policy, E2E win, independent confirmation or automatic expansion.')
    out=ROOT/'audit-v1';out.mkdir(mode=0o700,exist_ok=False)
    save(out/'summary.json',output)
    print(json.dumps(output))


def tests():
    assert contrast(dict(P=.5,C=.4,CP=.6,PC=.3)) == dict(CP_minus_P=.1,C_minus_P=-.1,CP_minus_C=.2,PC_minus_P=-.2,interaction=0.0,rescue=True)
    assert contrast(dict(P=.5,C=None,CP=.6,PC=.3)) is None
    assert not contrast(dict(P=.5,C=.4,CP=.5,PC=.3))['rescue']
    print(json.dumps(dict(status='PASS',fixtures=3)))


if __name__ == '__main__':
    os.umask(0o077)
    tests() if sys.argv[1:]==['--tests'] else main()
