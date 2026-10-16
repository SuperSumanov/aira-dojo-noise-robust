"""Classify sealed18845 failures, not a new readout or rerun.

Read raw logs only remotely; export enumerated events, hashes and counts, never
candidate code, log text, metric values, predictions or credentials. The
controller's complete flag means wrapper closure, not successful execution.
"""
import hashlib
import json
from pathlib import Path
import re
from closed_clock_screen_20261016 import SECRET

ROOT = Path('/research/d7/spc/yzyang4/clock-rank-confirmation-20261016-v2')
PIN = 'd9834749a7d1add6ba10168372ea2c947adaa5f00273fb8719491591a2d0d146'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
READY = re.compile(r'^\[[^\n]+\] \[jupyter_code_executor\.py:\d+\] Ready\s*$', re.M)
NOT_READY = re.compile(r'^\[[^\n]+\] \[jupyter_code_executor\.py:\d+\] Kernel did not become ready in time\.\s*$', re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def classify(text, finished):
    assert not SECRET.search(text), 'credential-shape hit: withhold raw log'
    text = ANSI.sub('', text)
    ready = list(READY.finditer(text))
    not_ready = list(NOT_READY.finditer(text))
    assert len(ready) <= 1 and len(not_ready) <= 1 and not (ready and not_ready)
    # The logger prints the source before Ready. Never count source literals as
    # events. Phase markers are only recognized in the subsequent output.
    output = text[ready[0].end():] if ready else ''
    phases = []
    for line in output.splitlines():
        if re.search(r'\.\.\.\s+Running test inference\.\.\.', line):
            phases.append('inference_announced')
        if re.search(r'\.\.\.\s+Total CV time:\s*\d', line):
            phases.append('cv_finished_announced')
    if finished.get('valid'):
        assert ready and not finished.get('timed_out') and finished.get('exit_code') == 0
        category = 'valid_output'
    elif not_ready:
        assert finished.get('timed_out') and not ready
        category = 'infrastructure_kernel_not_ready'
    elif ready and finished.get('timed_out'):
        assert 'Timeout waiting for output from code block.' in output
        category = 'candidate_execution_timeout'
    else:
        category = 'unclassified_failure'
    return dict(category=category, kernel_ready=bool(ready),
                phase_announcements=phases,
                last_explicit_phase=phases[-1] if phases else None,
                executed_duration_seconds=finished.get('exec_seconds'),
                reported_timed_out=finished.get('timed_out'),
                worker_exception_present=finished.get('error') is not None)


def main():
    assert (ROOT/'closed.json').exists() and sha(ROOT/'plan.json') == PIN
    plan, closed = read(ROOT/'plan.json'), read(ROOT/'closed.json')
    assert len(plan['schedule']) == len(closed['records']) == 16
    rows = []
    for item in plan['schedule']:
        ep = ROOT/f"episode-{item['index']}"
        log, finished = ep/'worker.private.log', read(ep/'finished.json')
        rows.append(dict(index=item['index'], program=item['program'],
                         mode=item['mode'], block=item['block'],
                         log_sha256=sha(log), finished_sha256=sha(ep/'finished.json'),
                         training_receipt_present=(ep/'gpu-training.json').exists(),
                         **classify(log.read_text(errors='replace'), finished)))
    execution_order = [x['index'] for x in closed['records']]
    infrastructure = [r['index'] for r in rows if r['category'].startswith('infrastructure_')]
    after = []
    if infrastructure:
        first = min(execution_order.index(i) for i in infrastructure)
        after = execution_order[first+1:]
    result = dict(posthoc=True, job=18845, plan_sha256=PIN,
                  analysis_sha256=sha(Path(__file__)), rows=rows,
                  counts={k:sum(r['category'] == k for r in rows) for k in sorted({r['category'] for r in rows})},
                  execution_order=execution_order, infrastructure_indices=infrastructure,
                  indices_executed_after_first_infrastructure_failure=after,
                  declared_infrastructure_stop_satisfied=not after,
                  confirmation_gate_passed=False,
                  conclusions=[
                      'Kernel-not-ready is infrastructure failure, not a candidate-quality outcome.',
                      'An execution timeout after Ready is distinct from a startup failure; no hidden score imputed.',
                      'Phase announcements do not give exact GPU time or guarantee inference completion.',
                      'Missing terminal training receipts do not mean zero training work.',
                      'Summary complete/structure describe wrapper closure and isolation, not the semantic infrastructure-stop contract.',
                      'Rows after infrastructure failure remain in the full denominator and cost, but cannot confirm an effect under the original stop rule.',
                      'The sealed batch is not retried, repaired in place, reselected or used to confirm rank reversal.'
                  ])
    dest = ROOT/'failure-audit-20261016.safe.json'
    with dest.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
