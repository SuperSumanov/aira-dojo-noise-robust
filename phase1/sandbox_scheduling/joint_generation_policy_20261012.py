"""Online pre-generation admission. No future journal or outcome access.

All policies share two generation permits/task and one execution permit/lane.
The joint ablation alone adds the predicted lane wait after generation. This
is an explicit small baseline adaptation, NOT a CostAda/MARS reproduction.
"""
import contextlib
import json
import math
import os
from pathlib import Path
import signal
import time

ARMS = ('continuation', 'cost', 'joint')


def rank_request(request, state, now, arm, occupancy):
    if arm not in ARMS:
        raise ValueError('unknown policy')
    stats = state['stats'][str(request['run'])]
    # Analysis completes an already-executed round; common precedence.
    phase = int(request['role'] == 'analyze')
    age = max(0., now-request['requested'])
    if arm == 'continuation':
        value = stats['completed'] + int(request['role'] == 'debug')
        return (phase, value, age, -request['run'])
    generation = stats['generation_mean']
    execution = stats['execution_mean']
    extra = 0.
    if arm == 'joint' and request['role'] != 'analyze':
        # Non-preemptive, one candidate per lane. Work expected to finish
        # during generation is NOT counted a second time as queue delay.
        busy = occupancy.get(str(request['lane']))
        if busy:
            extra = max(0., busy['expected_seconds']-(now-busy['start'])-generation)
    cycle = max(1., generation+execution+stats['analysis_mean']+extra)
    remaining = request['deadline']-now
    fit = remaining >= cycle if request['role'] != 'analyze' else True
    probability = (stats['improvements']+1.)/(stats['completed']+2.)
    value = probability*(1.+age/300.)/cycle
    return (phase, int(fit), value, age, -request['run'])


def choose(state, task, now, arm, occupancy):
    waiting = [r for r in state['waiting'] if r['task'] == task]
    if not waiting or sum(r['task'] == task for r in state['active']) >= 2:
        return None
    return max(waiting, key=lambda r:rank_request(r, state, now, arm, occupancy))['key']


def initialize(directory, rows, warm):
    directory = Path(directory); directory.mkdir(mode=0o700)
    state = dict(waiting=[], active=[], stats={})
    for row in rows:
        w = warm[row['task']]
        state['stats'][str(row['index'])] = dict(completed=0, improvements=0,
            generation_mean=120., generation_n=0, analysis_mean=30., analysis_n=0,
            execution_mean=max(1., min(300., w['exec_time'])), execution_n=0,
            best=float(w['metric']))
    (directory/'state.json').write_text(json.dumps(state, allow_nan=False))
    (directory/'mutex').touch()


@contextlib.contextmanager
def locked(directory):
    import fcntl
    directory = Path(directory)
    with (directory/'mutex').open('r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
        try:
            state = json.loads((directory/'state.json').read_text())
            yield state
            tmp = directory/f'state-{os.getpid()}.tmp'
            tmp.write_text(json.dumps(state, allow_nan=False))
            os.replace(tmp, directory/'state.json')
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)


def observe_occupancy(root, block, state):
    """Only currently active execution leases and their admission timestamps."""
    from live_admission import locked as execution_locked
    result = {}
    for lane in range(4):
        directory = root/f'queue-{block}-{lane}'
        if not (directory/'mutex').exists():
            continue  # A lane not initialized yet has no execution occupancy.
        with execution_locked(directory) as lease:
            active = list(lease.active)
        if not active:
            continue
        if len(active) != 1:
            raise ValueError('execution capacity drift')
        events = [json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
        matches = [e for e in events if e['event'] == 'admitted' and e['key'] == active[0]]
        if len(matches) != 1:
            raise ValueError('active lease missing admission')
        run = active[0].split(':')[0]
        result[str(lane)] = dict(start=matches[0]['time'], expected_seconds=state['stats'][run]['execution_mean'])
    return result


def mean_update(stats, prefix, value):
    if not math.isfinite(value) or value < 0:
        raise ValueError('invalid observed duration')
    n = stats[prefix+'_n']; old = stats[prefix+'_mean']
    stats[prefix+'_mean'] = (old*n+value)/(n+1)
    stats[prefix+'_n'] = n+1


def install(row, ep, deadline, warm):
    from live_admission import append_event
    from dojo.solvers.mcts.mcts import MCTS, MCTSNode
    from dojo.core.solvers.utils.metric import MetricValue
    directory = ep.parent/f'generation-{row["block"]}'
    counter = [0]
    def event(kind, **values):
        append_event(directory/'events.jsonl', dict(event=kind, time=time.time(), run=row['index'], **values))

    @contextlib.contextmanager
    def permit(role):
        n = counter[0]; counter[0] += 1
        request = dict(key=f'{row["index"]}:{n}', run=row['index'], task=row['task'],
            lane=row['lane'], role=role, requested=time.time(),
            deadline=time.time()+max(0., deadline.seconds-deadline.elapsed()))
        held = False; start = None
        try:
            with locked(directory) as state:
                state['waiting'].append(request); event('queued', request=request)
            while True:
                deadline.check()
                with locked(directory) as state:
                    now = time.time(); occupancy = observe_occupancy(ep.parent, row['block'], state)
                    selected = choose(state, row['task'], now, row['arm'], occupancy)
                    if selected == request['key']:
                        alternatives = {a:choose(state, row['task'], now, a, occupancy) for a in ARMS}
                        waiting = [r for r in state['waiting'] if r['task'] == row['task']]
                        free = 2-sum(r['task'] == row['task'] for r in state['active'])
                        event('admitted', key=request['key'], role=role, decision_time=now, alternatives=alternatives,
                            scarce=len(waiting)>free, occupancy=occupancy,
                            snapshot=dict(waiting=state['waiting'], active=state['active'], stats=state['stats']))
                        state['waiting'].remove(request); state['active'].append(request)
                        held = True; start = time.monotonic(); break
                time.sleep(.05)
            yield
        finally:
            with locked(directory) as state:
                # Persisted identity is authoritative across signal boundaries.
                active = [r for r in state['active'] if r['key'] == request['key']]
                queued = [r for r in state['waiting'] if r['key'] == request['key']]
                if active:
                    state['active'].remove(active[0])
                    if held and start is not None:
                        mean_update(state['stats'][str(row['index'])],
                            'analysis' if role == 'analyze' else 'generation', time.monotonic()-start)
                    event('released', key=request['key'])
                elif queued:
                    state['waiting'].remove(queued[0]); event('cancelled', key=request['key'])

    for name in ('_improve', '_debug', '_analyze'):
        original = getattr(MCTS, name)
        def wrap(original=original, role=name[1:]):
            def call(self, *args, **kwargs):
                with permit(role):
                    return original(self, *args, **kwargs)
            return call
        setattr(MCTS, name, wrap())

    original_root = MCTS.create_root_node
    def root(self):
        original_root(self)
        node = MCTSNode(code=warm['code'], plan=warm['plan'], parents=[self.root_node],
            analysis=warm['analysis'], is_buggy=False, exit_code=0,
            exec_time=warm['exec_time'], _term_out=warm['_term_out'],
            metric=MetricValue(warm['metric'], maximize=warm['metric_maximize']),
            operators_used=['warm_start'])
        node.explore_count = 1; node.node_value = warm['metric']
        self.journal.append(node); self.state.current_step += 1
        self.global_max_q_val = self.global_min_q_val = node.q_value(self.lower_is_better)
        self.root_node.increment_explore_count()
        self.log_journal()
        event('warm_start', metric=warm['metric'], code_sha256=warm['code_sha256'])
    MCTS.create_root_node = root

    original_parse = MCTS.parse_eval_result
    def parse(self, node, evaluation):
        original_parse(self, node, evaluation)
        with locked(directory) as state:
            stats = state['stats'][str(row['index'])]; stats['completed'] += 1
            mean_update(stats, 'execution', max(0., node.exec_time))
            score = node.metric.value
            improvement = not node.is_buggy and score is not None and (score-stats['best'])*(1 if warm['metric_maximize'] else -1) > 0
            if improvement:
                stats['improvements'] += 1; stats['best'] = score
            event('round_complete', improved=bool(improvement), completed=stats['completed'])
    MCTS.parse_eval_result = parse
