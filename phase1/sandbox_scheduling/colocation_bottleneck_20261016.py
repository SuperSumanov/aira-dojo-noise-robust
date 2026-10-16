"""Closed18807 descriptive capacity/coverage screen; no policy simulation.

All search histories remain observed histories. A two-executor lower bound
holds only if every observed lease and duration is retained, not after changing
generation, timing, feedback or resource interference. No causal mediation.
"""
import hashlib
import json
from pathlib import Path
import sys

R = Path('/research/d7/spc/yzyang4/scheduling-colocation-20261016-v1')
PIN = '36ce5852b26de2299755c19a8b9711a1f4161d68abd25a3de6cc7687cdde8560'
RESULT = 'c8c2f71009a39e9932ec59e388f9b052ce190730179119aed5d73e4fa38576a4'


def read(p):
    return json.loads(p.read_text())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    assert sha(R/'plan.json') == PIN
    rp = R/'readout-20261016-v1'
    assert sha(rp/'summary.json') == RESULT and read(rp/'summary.json')['complete'] == 32
    sys.path.insert(0, str(R))
    from effort_pressure_diagnostic_20261012 import structural_events, state_changes
    runs = read(rp/'runs.json')
    result = []
    for b in range(4):
        window = read(R/f'block-{b}/budget-slot.json')
        changes, generation = state_changes(structural_events(R/f'generation-{b}/events.jsonl', True), 4)
        # The frozen readout uses a JSON array, while the original queue is JSONL.
        _, execution = state_changes(structural_events(R/f'pool-{b}/events.jsonl', False), 8 if b in (1, 2) else 4)
        full = 0.0
        for (t, _, active), (end, _, _) in zip(changes, changes[1:]):
            if active == 4:
                full += end-t
        tasks = []
        for task in sorted({r['task'] for r in runs}):
            rows = [r for r in runs if r['block'] == b and r['task'] == task]
            codes, predictions = set(), set()
            count = timed_out = unsuccessful = 0
            for row in rows:
                for path in (R/f"episode-{row['index']}").glob('candidate-*.json'):
                    if '.private.' in path.name:
                        continue
                    c = read(path)
                    if c['elapsed_seconds'] > 1020:
                        continue
                    count += 1
                    timed_out += bool(c['timed_out'])
                    valid = c['valid'] is True and c['exit_code'] == 0 and not c['timed_out']
                    unsuccessful += not valid
                    if valid:
                        codes.add(c['code_sha256'])
                        predictions.add(c['aux']['submission_sha256'])
            assert count == sum(r['candidate_returns'] for r in rows)
            tasks.append(dict(task=task, returns=count, valid=sum(r['valid_returns'] for r in rows),
                valid_by_run=[r['valid_returns'] for r in sorted(rows, key=lambda r:r['lane'])],
                unique_valid_code=len(codes), unique_valid_prediction=len(predictions),
                timed_out_returns=timed_out, unsuccessful_returns=unsuccessful))
        result.append(dict(block=b, mode=runs[8*b]['pool_mode'], generation=generation, execution=execution,
            generation_four_permits_full_seconds=full, reserved_seconds=window['actual_seconds'],
            unchanged_trace_two_executor_minimum_seconds=execution['holding_seconds']/2,
            tasks=tasks))
    out = dict(plan_sha256=PIN, primary_summary_sha256=RESULT, reader_sha256=sha(Path(__file__)), pools=result,
        boundary='Posthoc closed histories only. Host permits include non-kernel work; generation queue is not a measured model hardware bottleneck. Capacity lower bound retains existing durations/leases and is NOT a 4service+2executor quality prediction. Unique hashes are not semantic diversity. No new GPU/model/scoring and no altered primary gate.')
    target = R/'bottleneck-20261016-v1.safe.json'
    with target.open('x') as f:
        json.dump(out, f, indent=2, allow_nan=False)
    print(json.dumps(out))


if __name__ == '__main__':
    main()
