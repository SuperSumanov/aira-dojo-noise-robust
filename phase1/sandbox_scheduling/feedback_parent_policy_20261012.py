"""Shared-parent experiment: greedy, pending-UCB, and feedback reservation.

The third arm differs from pending-UCB ONLY by forbidding another improvement
of a parent code while its previous improvement awaits external feedback.
This is an archive adaptation of pending-count UCB, not a full WU-UCT replica.
All contents remain in the remote private experiment directory.
"""
import contextlib
import hashlib
import json
import math
from pathlib import Path
import time

from joint_generation_policy_20261012 import locked

ARMS = ('greedy', 'pending_ucb', 'feedback_gate')


def key_for(code):
    return hashlib.sha256(code.encode()).hexdigest()


def parent_choice(state, task, arm):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    archive = state['archive'][task]
    sign = state['sign'][task]
    pending = {k: 0 for k in archive}
    for r in state['pending'].values():
        if r['task'] == task:
            pending[r['parent']] += 1
    eligible = [k for k in archive if arm != 'feedback_gate' or pending[k] == 0]
    if not eligible:
        return None
    if arm == 'greedy':
        return max(eligible, key=lambda k: (sign * archive[k]['metric'], -archive[k]['order']))
    # WU-UCT Eq4's pending-count principle applied to a shared parent archive.
    # Each evaluated parent starts with one observation: its own observed score.
    # Child feedback updates that parent's mean; no failed future score is imputed.
    means = {k: archive[k]['total'] / archive[k]['visits'] for k in archive}
    lo, hi = min(means.values()), max(means.values())
    total = sum(v['visits'] + pending[k] for k, v in archive.items())
    def value(k):
        q = (means[k] - lo) / (hi - lo) if hi > lo else 0.5
        bonus = 0.5 * math.sqrt(2 * math.log(max(2, total)) / (archive[k]['visits'] + pending[k]))
        return q + bonus, -archive[k]['order']
    return max(eligible, key=value)


def select_request(state, task, arm):
    waiting = [r for r in state['waiting'] if r['task'] == task]
    if not waiting or sum(r['task'] == task for r in state['active']) >= 2:
        return None, None
    # Same completion-first, FIFO admission in every arm. No learned wait penalty.
    waiting.sort(key=lambda r: (-int(r['role'] == 'analyze'), r['requested'], r['run']))
    for r in waiting:
        parent = parent_choice(state, task, arm) if r['role'] == 'improve' else None
        if r['role'] != 'improve' or parent is not None:
            return r['key'], parent
    return None, None


def record(warm, order):
    score = float(warm['metric'])
    sign = 1 if warm['metric_maximize'] else -1
    result = {k: warm[k] for k in ('code', 'plan', 'analysis', '_term_out', 'exec_time', 'metric', 'metric_maximize')}
    result.update(order=order, visits=1, total=sign * score)
    return result


def initialize(directory, rows, warm):
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    tasks = sorted({r['task'] for r in rows})
    state = dict(waiting=[], active=[], pending={}, archive={}, sign={}, next_order=0)
    for task in tasks:
        state['archive'][task] = {key_for(warm[task]['code']): record(warm[task], 0)}
        state['sign'][task] = 1 if warm[task]['metric_maximize'] else -1
    (directory / 'state.json').write_text(json.dumps(state, allow_nan=False))
    (directory / 'mutex').touch()


def install(row, ep, deadline, warm):
    from live_admission import append_event
    from dojo.solvers.mcts.mcts import MCTS, MCTSNode
    from dojo.core.solvers.utils.metric import MetricValue
    directory = ep.parent / f'generation-{row["block"]}'
    counter = [0]
    node_reservation = {}

    def event(kind, **values):
        append_event(directory / 'events.jsonl', dict(event=kind, time=time.time(), run=row['index'], **values))

    @contextlib.contextmanager
    def permit(role):
        n = counter[0]
        counter[0] += 1
        request = dict(key=f'{row["index"]}:{n}', run=row['index'], task=row['task'], role=role,
                       requested=time.time())
        reservation = None
        try:
            with locked(directory) as state:
                state['waiting'].append(request)
                event('queued', request=request)
            withheld = False
            while True:
                deadline.check()
                with locked(directory) as state:
                    selected, parent = select_request(state, row['task'], row['arm'])
                    baseline_selected, baseline_parent = select_request(state, row['task'], 'pending_ucb')
                    if role == 'improve' and parent_choice(state, row['task'], row['arm']) is None and not withheld and baseline_selected == request['key']:
                        event('feedback_wait', key=request['key'], reference_parent=baseline_parent,
                              task=row['task'], active_generation=sum(r['task']==row['task'] for r in state['active']))
                        withheld = True
                    if selected == request['key']:
                        alternatives = {a: parent_choice(state, row['task'], a) for a in ARMS} if role == 'improve' else {}
                        payload = dict(state['archive'][row['task']][parent]) if parent else None
                        # Numeric identities only in this event; candidate payload stays in private state.
                        snapshot = dict(archive={t:{k:{f:v[f] for f in ('metric','order','visits','total')} for k,v in arc.items()} for t,arc in state['archive'].items()},
                                        sign=state['sign'], pending=dict(state['pending']))
                        if parent:
                            reservation = request['key']
                            state['pending'][reservation] = dict(task=row['task'], parent=parent, run=row['index'])
                        state['waiting'].remove(request)
                        state['active'].append(request)
                        event('admitted', key=request['key'], role=role, parent=parent,
                              alternatives=alternatives, snapshot=snapshot, withheld=withheld)
                        break
                time.sleep(0.05)
            yield payload, reservation
        except BaseException:
            if reservation:
                with locked(directory) as state:
                    state['pending'].pop(reservation, None)
                    event('abandoned', key=reservation)
            raise
        finally:
            with locked(directory) as state:
                for name, kind in (('active', 'released'), ('waiting', 'cancelled')):
                    found = [r for r in state[name] if r['key'] == request['key']]
                    if found:
                        state[name].remove(found[0])
                        event(kind, key=request['key'])

    old_root = MCTS.create_root_node
    def root(self):
        old_root(self)
        node = MCTSNode(code=warm['code'], plan=warm['plan'], parents=[self.root_node],
                        analysis=warm['analysis'], is_buggy=False, exit_code=0, exec_time=warm['exec_time'],
                        _term_out=warm['_term_out'], metric=MetricValue(warm['metric'], maximize=warm['metric_maximize']),
                        operators_used=['warm_start'])
        node.explore_count = 1
        node.node_value = warm['metric']
        self.journal.append(node)
        self.global_max_q_val = self.global_min_q_val = node.q_value(self.lower_is_better)
        self.root_node.increment_explore_count()
        self.log_journal()
        self.state.current_step += 1
        event('warm_start', code_sha256=key_for(warm['code']))
    MCTS.create_root_node = root

    old_improve = MCTS._improve
    def improve(self, unused_parent):
        with permit('improve') as (payload, reservation):
            h = key_for(payload['code'])
            existing = [n for n in self.journal.nodes if n.code and key_for(n.code) == h and not n.is_buggy]
            if existing:
                parent = existing[0]
            else:
                parent = MCTSNode(code=payload['code'], plan=payload['plan'], parents=[self.root_node],
                                  analysis=payload['analysis'], is_buggy=False, exit_code=0,
                                  exec_time=payload['exec_time'], _term_out=payload['_term_out'],
                                  metric=MetricValue(payload['metric'], maximize=payload['metric_maximize']),
                                  operators_used=['shared_parent'])
                parent.explore_count = 1
                parent.node_value = payload['metric']
                self.journal.append(parent)
                self.log_journal()
                self.state.current_step += 1
            node = old_improve(self, parent)
            node_reservation[node.id] = reservation
            event('parent_used', key=reservation, parent=h, child=key_for(node.code))
            return node
    MCTS._improve = improve

    for name in ('_debug', '_analyze'):
        original = getattr(MCTS, name)
        def wrap(original=original, role=name[1:]):
            def call(self, *args, **kwargs):
                with permit(role):
                    return original(self, *args, **kwargs)
            return call
        setattr(MCTS, name, wrap())

    original_parse = MCTS.parse_eval_result
    def parse(self, node, eval_result):
        original_parse(self, node, eval_result)
        with locked(directory) as state:
            reservation = node_reservation.pop(node.id, None)
            pending = state['pending'].pop(reservation, None) if reservation else None
            valid = not node.is_buggy and node.metric.value is not None and math.isfinite(node.metric.value)
            archive = state['archive'][row['task']]
            if pending:
                parent = archive[pending['parent']]
                retained = state['sign'][row['task']] * parent['metric']
                if valid:
                    retained = max(retained, state['sign'][row['task']] * float(node.metric.value))
                # Failure consumes a visit but retains the already evaluated parent;
                # this is retained-solution utility, not an invented failure score.
                parent['visits'] += 1
                parent['total'] += retained
            if valid:
                score = float(node.metric.value)
                h = key_for(node.code)
                if h not in archive:
                    state['next_order'] += 1
                    payload = dict(code=node.code, plan=node.plan, analysis=node.analysis,
                                   _term_out=node._term_out, exec_time=node.exec_time,
                                   metric=score, metric_maximize=warm['metric_maximize'])
                    archive[h] = record(payload, state['next_order'])
            event('round_complete', key=reservation, valid=bool(valid), code_sha256=key_for(node.code))
    MCTS.parse_eval_result = parse

    # A timed-out execution may never reach parse_eval_result. Clear only this
    # worker's reservations on solve exit; do not invent a score for it.
    original_solve = MCTS.__call__
    def solve(self, *args, **kwargs):
        try:
            return original_solve(self, *args, **kwargs)
        finally:
            with locked(directory) as state:
                own = [k for k,v in state['pending'].items() if v['run'] == row['index']]
                for k in own:
                    state['pending'].pop(k)
                    event('abandoned', key=k)
    MCTS.__call__ = solve
