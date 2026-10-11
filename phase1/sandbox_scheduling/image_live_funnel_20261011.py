"""Read-only, post-hoc execution funnel; never replaces the frozen quality gate.

Only the current development experiment's numeric receipts are exported.
No code, labels, prediction values, credentials, or arbitrary log text.
Partial observations are labelled; pooled generation time is not GPU time.
"""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v3')
PIN = '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66'


def read(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None  # A live file can be between creation and write completion.


def events(path):
    if not path.exists():
        return []
    output = []
    for line in path.read_text().splitlines():
        try:
            output.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return output


def summarize():
    assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest() == PIN
    plan = read(ROOT/'plan.json')
    rows = []
    for assignment in plan['schedule']:
        ep = ROOT / ('episode-' + str(assignment['index']))
        es = events(ep/'events.jsonl')
        returned = [e for e in es if e['event'] == 'generation_returned']
        failed = [e['seconds'] for e in returned if not e['success']]
        candidates = [read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name]
        candidates = [c for c in candidates if c is not None]
        timely = [c for c in candidates if c['elapsed_seconds'] <= plan['run_seconds']]
        f = read(ep/'finished.json') or {}
        closure = read(ep/'closed.json') or {}
        failure = read(ep/'failure.json') or {}
        phase = f.get('status')
        assert phase in (None, 'completed', 'budget_exhausted', 'failed', 'starting', 'running')
        rows.append(dict(index=assignment['index'], block=assignment['block'],
            arm=assignment['arm'], task=assignment['task'], seed=assignment['seed'],
            started=(ep/'deadline.json').exists(), finished=bool(f), status=phase,
            worker_returncode=closure.get('returncode'),
            runtime_error=failure.get('error_type') == 'RuntimeError',
            generation_started=sum(e['event']=='generation_started' for e in es),
            generation_returned=len(returned), generation_failed=len(failed),
            generation_seconds=sum(e['seconds'] for e in returned),
            failed_generation_seconds=failed,
            generation_latency_median=statistics.median(e['seconds'] for e in returned) if returned else None,
            candidate_started=sum(e['event']=='operation_ready' and e['kind']=='candidate' for e in es),
            candidate_returns=len(candidates), timely_returns=len(timely),
            valid_timely_returns=sum(c['valid'] is True for c in timely),
            candidate_timeouts=sum(c['timed_out'] is True for c in candidates),
            candidate_nonzero=sum(c['exit_code'] != 0 for c in candidates),
            candidate_execution_seconds=sum(c['exec_seconds'] for c in candidates),
            candidate_queue_seconds=sum(e.get('wait_seconds',0) for e in es
                if e['event'] in ('admitted','admission_interrupted') and e.get('kind')=='candidate'),
            cleanup_failed=sum(e['event']=='cleanup' and not e['verified'] for e in es)))
    print(json.dumps(dict(observed_unix_seconds=time.time(), plan_sha256=PIN,
        assigned=len(rows), rows=rows,
        warning='Post-hoc partial funnel, not a replacement endpoint, quality gain, GPU-time accounting or causal attribution.'),
        allow_nan=False, sort_keys=True))


def verify_available_scores():
    """Recompute development scores without exporting predictions or labels."""
    assert hashlib.sha256((ROOT/'plan.json').read_bytes()).hexdigest() == PIN
    plan = read(ROOT/'plan.json')
    for name in ('image_dev_data_20261011.py', 'lifecycle_pilot.py'):
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == plan['files'][name]
    sys.path.insert(0, str(ROOT))
    from image_dev_data_20261011 import score_at
    spec = read(ROOT/'dev-views/spec.json')
    checked = []
    for assignment in plan['schedule']:
        ep = ROOT / ('episode-' + str(assignment['index']))
        for file in sorted(ep.glob('scored-*.json')):
            saved = read(file)
            if saved is None:
                continue
            metric = spec[assignment['task']]['metric_name']
            actual = score_at(ROOT, spec, assignment['task'], ep/(file.stem+'.private.csv'))
            receipt = saved['receipt']
            assert actual['submission_sha256'] == receipt['submission_sha256']
            assert abs(actual[metric] - receipt[metric]) <= 1e-12
            training = read(ep/('gpu-training-'+file.stem.split('-')[-1]+'.json')) or {}
            checked.append(dict(index=assignment['index'], task=assignment['task'],
                elapsed_seconds=saved['elapsed_seconds'], timely=saved['elapsed_seconds']<=plan['run_seconds'],
                score_recomputed=True, cuda_gradient_steps=training.get('cuda_gradient_steps')))
    print(json.dumps(dict(plan_sha256=PIN, checked=checked,
        limitation='Scoring receipts only; native-selected endpoints and paired treatment effect require the completed frozen readout.'), allow_nan=False))


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify-scores']:
        verify_available_scores()
    else:
        assert not sys.argv[1:]
        summarize()
