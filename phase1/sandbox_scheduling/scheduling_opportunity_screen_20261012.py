"""Descriptive actionability screen of three CLOSED development batches.

No replayed treatment effects, future-aware policy, rescoring, or production
mutation. Queue alternatives refer only to already queued work in the actual
lane. Final-journal roles are retrospective exposure, never online features.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

from live_admission import audit_events
from live_feedback_progress import progress, recorded_roles
from live_phase_analysis import phases
from live_queue_efficiency import account


BASE = Path('/research/d7/spc/yzyang4')
BATCHES = (
    ('17592', 'scheduling-image-live-2plus4-20261011-v3', 32,
     '95825b54b256eb69f7a2a372db66c4f63b4c0d9840d3253f5ade5685f448fe66',
     '7918c85f5257a82d66e28d52c9a557e7c924ed2e0dc5a5f4ef7b0131f6a84a9c'),
    ('17656', 'scheduling-image-generation-deadline-20261011-v1', 16,
     'd153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7',
     'ef4a2d9ea398488370dcbd750f6706105a825d1c6ed6b3188653e8e88bec4f99'),
    ('17670', 'scheduling-image-deadline-replication-20261012-v1', 32,
     '23f368399f6c735ef81142ec46831ae4e9f45d58d80edf5d2559b4cbb7a22ea6',
     '99ae98964305d29a444d7d5ba86c347395f70ef96280e2cf53b47491c5ae569c'),
)
TASK_SIGN = {'aerial-cactus-identification': 1, 'denoising-dirty-documents': -1}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    # Missing or malformed closed inputs are errors, not silently empty data.
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def choice_points(events, limit, kinds):
    """Count admissions with a genuine subset choice, not just multiple slots.

    E.g. two waiting operations and two free permits need no priority decision.
    This is not an estimate for preemption, deliberate idling, migration, or
    generation-side admission; those would change the experiment's action set.
    """
    checked = audit_events(events, limit)
    if not checked['all_released']:
        raise ValueError('open queue')
    waiting = []; active = set(); counts = Counter()
    for event in events:
        key = event['key']; action = event['event']
        if key not in kinds:
            raise ValueError('queue operation lacks ready receipt')
        if action == 'queued':
            waiting.append(key)
        elif action == 'admitted':
            free = limit - len(active)
            candidates = [k for k in waiting if kinds[k] == 'candidate']
            counts['admissions'] += 1
            counts['candidate_admissions'] += kinds[key] == 'candidate'
            counts['multiple_waiters_at_admission'] += len(waiting) >= 2
            counts['scarce_subset_choices'] += len(waiting) > free
            counts['candidate_subset_choices'] += len(candidates) > free
            waiting.remove(key); active.add(key)
        elif action == 'released':
            active.remove(key)
        elif action == 'queue_cancelled':
            waiting.remove(key)
    return {k: counts[k] for k in ('admissions', 'candidate_admissions',
        'multiple_waiters_at_admission', 'scarce_subset_choices', 'candidate_subset_choices')}


def journal_exposure(nodes, sign):
    """Retrospective native journal counts; not externally re-grounded effects."""
    nodes = [n for n in nodes if n.get('operators_used')]
    steps = [n['step'] for n in nodes]
    if steps != sorted(steps) or len(set(steps)) != len(steps):
        raise ValueError('journal step order')
    count = Counter(); best = None
    for node in nodes:
        role = node['operators_used'][0]
        if role not in ('draft', 'debug', 'improve'):
            raise ValueError('unknown node role')
        count[role] += 1
        accepted = node.get('is_buggy') is False and node.get('metric') is not None
        if accepted:
            value = node['metric']
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('nonfinite accepted node')
            if node.get('metric_maximize') != (sign == 1):
                raise ValueError('metric orientation')
            score = sign * Decimal(str(value))
            count['accepted'] += 1
            count['accepted_' + role] += 1
            if best is not None and score > best:
                count['strict_record_updates'] += 1
                count['strict_record_' + role] += 1
            best = score if best is None else max(best, score)
    keys = ('draft', 'debug', 'improve', 'accepted', 'accepted_improve',
            'strict_record_updates', 'strict_record_draft', 'strict_record_debug', 'strict_record_improve')
    return {k: count[k] for k in keys}


def screen(batch):
    job, name, size, plan_pin, summary_pin = batch
    root = BASE / name
    if sha(root/'plan.json') != plan_pin or sha(root/'readout-v1/summary.json') != summary_pin:
        raise ValueError('frozen input pin mismatch')
    closed = read(root/'completion-closed.json')
    summary_key = 'readout_sha256' if job == '17592' else 'summary_sha256'
    if closed[summary_key] != summary_pin:
        raise ValueError('completion receipt mismatch')
    plan = read(root/'plan.json'); schedule = plan['schedule']; horizon = plan['run_seconds']
    if len(schedule) != size or {s['index'] for s in schedule} != set(range(size)):
        raise ValueError('assigned denominator')
    rows = []; kinds = {}; input_hashes = {}
    for s in schedule:
        ep = root / f"episode-{s['index']}"
        files = [ep/'events.jsonl', ep/'finished.json', ep/'checkpoint/journal.jsonl']
        files += sorted(p for p in ep.glob('candidate-*.json') if '.private.' not in p.name)
        for path in files:
            input_hashes[str(path.relative_to(root))] = sha(path)
        events = lines(files[0]); finished = read(files[1]); nodes = lines(files[2])
        candidates = [read(p) for p in files[3:]]
        for e in events:
            if e['event'] == 'operation_ready':
                key = f"{s['index']}:{e['operation']}"
                if e['run'] != s['index'] or key in kinds or e['kind'] not in ('candidate', 'preview'):
                    raise ValueError('operation identity/kind')
                kinds[key] = e['kind']
        follow = progress(events, candidates, horizon)
        phase = phases(events, horizon)
        roles = recorded_roles(nodes)
        row = {k: s[k] for k in ('index', 'block', 'lane', 'task', 'seed', 'arm')}
        row.update(status=finished['status'], candidate_returns=len(candidates),
            valid_returns=sum(c['valid'] is True for c in candidates),
            valid_return_followed_by_candidate_return=sum(p['valid'] and p['subsequent_candidate_returned'] for p in follow),
            generation_calls=sum(e['event'] == 'generation_started' for e in events),
            failed_generation_calls=sum(e['event'] == 'generation_returned' and not e['success'] for e in events),
            native_exposure=journal_exposure(nodes, TASK_SIGN[s['task']]),
            recorded_role_calls={k: v['calls'] for k, v in roles.items()},
            phase=phase)
        rows.append(row)
    queues = []
    for block, lane in sorted({(s['block'], s['lane']) for s in schedule}):
        directory = root / f'queue-{block}-{lane}'
        state = read(directory/'state.json')
        path = directory/'events.jsonl'
        # initialize() creates state before the first event; a truly empty
        # failed-before-execution lane may legitimately have no event file.
        if path.exists():
            es = lines(path); input_hashes[str(path.relative_to(root))] = sha(path)
        elif state['queue'] or state['active'] or state['finished']:
            raise ValueError('nonempty queue missing events')
        else:
            es = []
        if state['queue'] or state['active']:
            raise ValueError('open persisted queue')
        input_hashes[str((directory/'state.json').relative_to(root))] = sha(directory/'state.json')
        width = state['limit']
        arm = next(s['arm'] for s in schedule if s['block'] == block)
        queues.append(dict(block=block, lane=lane, arm=arm, width=width,
            **choice_points(es, width, kinds), **account(es, width)))
    # Closed inputs must remain unchanged throughout this one read-only pass.
    if any(sha(root / name) != digest for name, digest in input_hashes.items()):
        raise ValueError('closed receipt changed during analysis')
    aggregates = []
    for arm in sorted({r['arm'] for r in rows}):
        rs = [r for r in rows if r['arm'] == arm]; qs = [q for q in queues if q['arm'] == arm]
        aggregates.append(dict(arm=arm, assigned=len(rs),
            **{k: sum(r[k] for r in rs) for k in ('candidate_returns', 'valid_returns',
                'valid_return_followed_by_candidate_return', 'generation_calls', 'failed_generation_calls')},
            native_exposure={k: sum(r['native_exposure'][k] for r in rs) for k in rs[0]['native_exposure']},
            recorded_role_calls={k: sum(r['recorded_role_calls'][k] for r in rs) for k in roles},
            phase_task_slot_seconds={k: sum(r['phase']['seconds'][k] for r in rs) for k in phase['seconds']},
            incomplete_phase_rows=sum(not r['phase']['complete'] for r in rs),
            **{k: sum(q[k] for q in qs) for k in ('admissions', 'candidate_admissions',
                'multiple_waiters_at_admission', 'scarce_subset_choices', 'candidate_subset_choices',
                'waiting_task_seconds_including_cancelled', 'waiting_with_spare_permit_slot_seconds')}))
    return dict(job=job, source_commit=plan['source_commit'], plan_sha256=plan_pin,
        original_summary_sha256=summary_pin, run_seconds=horizon, assigned=size,
        rows=rows, queues=queues, aggregates=aggregates, input_sha256=input_hashes)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(analysis_sha256=sha(__file__), batches=[screen(b) for b in BATCHES],
        boundary='Post-hoc descriptive actionability, not a method comparison or counterfactual savings. '
        'Three batches stay separate: budgets/knobs differ. Recorded roles omit unfinished calls. '
        'Final-journal counts are not pre-decision features or newly recomputed quality effects. '
        'Phase task-slot seconds are not GPU seconds/utilization. No rescoring, raw program, label or prediction export.',
        dependency_sha256={name: sha(Path(__file__).with_name(name)) for name in
            ('live_admission.py', 'live_feedback_progress.py', 'live_phase_analysis.py',
             'live_queue_efficiency.py', 'lifecycle_pilot.py')})
    with args.output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(output_sha256=sha(args.output),
        batches=[{k: b[k] for k in ('job', 'assigned', 'aggregates')} for b in result['batches']]), allow_nan=False))


if __name__ == '__main__':
    main()
