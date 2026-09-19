"""Opt-in first-failure cached continuation for a pinned ForeTS class.

Development adapter only: not installed into a production run. Callers must use
the same outer wall/step budget enforcement for both arms. No external grades or
critic re-ranking are read. A cache attempt is a normal full task execution and
normal result analysis, charged against current_step and wall time.
"""
import random
from time import monotonic


def make_cached_continuation(base_class, *, enabled, seed):
    """Off returns the exact original class; on changes only debug continuation.

    Per-pool RNG is separate from the agent/generator RNG. Normal checkpoints are
    at expansion boundaries. Mid-expansion checkpoint/resume is unsupported and
    must not be advertised as supported by this adapter.
    """
    if type(enabled) is not bool or type(seed) is not int:
        raise TypeError('explicit boolean and integer seed required')
    if not enabled:
        return base_class

    class CachedContinuation(base_class):
        def _expand_leaf_and_backprop(self, path, state, task):
            if getattr(self, '_cached_continuation_context', None) is not None:
                raise RuntimeError('nested/resumed active expansion is unsupported')
            self._cached_continuation_context = {
                'before': frozenset(n.id for n in self.journal_for_unselected.nodes),
                'start_step': self.state.current_step,
                'parent': path[-1],
                'used': False,
                'started_monotonic': monotonic(),
                'prior_running_time': self.state.running_time,
            }
            try:
                return super()._expand_leaf_and_backprop(path, state, task)
            finally:
                self._cached_continuation_context = None

        def debug_cycle(self, state, task, buggy_node):
            context = getattr(self, '_cached_continuation_context', None)
            if context is None or context['used']:
                return super().debug_cycle(state, task, buggy_node)
            context['used'] = True
            # Reserve a step for the original debug fallback; never exceed the
            # budget just to obtain an extra opportunity for the experimental arm.
            def out_of_time():
                # Production updates running_time only after a whole expansion.
                return context['prior_running_time'] + monotonic() - context['started_monotonic'] >= self.cfg.time_limit_secs
            if self.remaining_steps < 2 or out_of_time():
                return super().debug_cycle(state, task, buggy_node)
            if len(buggy_node.parents) != 1 or buggy_node.parents[0] is not context['parent']:
                raise ValueError('failed node is not a sibling in the current pool')
            candidates = [n for n in self.journal_for_unselected.nodes if n.id not in context['before']]
            executed_ids = {n.id for n in self.journal.nodes}
            if any(n.id in executed_ids or len(n.parents) != 1 or n.parents[0] is not context['parent']
                   or n.is_buggy is not None or n.children for n in candidates):
                raise ValueError('cache must contain only unexecuted current-pool siblings')
            if not candidates:
                return super().debug_cycle(state, task, buggy_node)
            rng = random.Random(f'cached-continuation-v1:{seed}:{context["start_step"]}')
            candidate = candidates[rng.randrange(len(candidates))]
            from dojo.core.solvers.utils.response import extract_code
            state, eval_result = task.step_task(state, extract_code(candidate.code))
            self.parse_eval_result(node=candidate, eval_result=eval_result)
            # Move the node rather than copying it into both journals. Preserve
            # its original parent and operators; this is not a repaired descendant.
            self.journal_for_unselected.nodes = [n for n in self.journal_for_unselected.nodes if n is not candidate]
            for index,node in enumerate(self.journal_for_unselected.nodes):
                node.step = index
            self.journal.append(candidate)
            self.log_journal()
            self.state.current_step += 1
            self.logger.info('Cached continuation: one uniformly selected current-pool sibling executed')
            if not candidate.is_buggy and candidate.metric.value is not None:
                # The production caller backpropagates path + debug_path. A
                # successful sibling must not give credit to the failed child.
                return state, [candidate], candidate.metric.value
            if self.remaining_steps <= 0 or out_of_time():
                return state, [], None
            return super().debug_cycle(state, task, buggy_node)

    return CachedContinuation
