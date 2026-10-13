"""Constant code-effort references; no adaptive routing or training."""
import contextvars
import copy
import inspect
import time

ARMS = ('fast_code', 'medium', 'xhigh')
# Fixed before new outputs. One pool per arm: order/cache effects remain a limit.
ORDER = ('medium', 'xhigh', 'fast_code')
ROLES = ('draft', 'improve', 'debug', 'analyze')
RUN = 1800
SLOT = 1960
CAP = 7500


def effort(arm, role):
    if arm not in ARMS or role not in ROLES:
        raise ValueError('unknown arm or role')
    return 'medium' if role == 'analyze' else ('none' if arm == 'fast_code' else arm)


def normalize(cfg):
    cfg = copy.deepcopy(cfg)
    for op in cfg['solver']['operators'].values():
        kw = op['llm']['generation_kwargs']
        kw.pop('reasoning_effort', None)
        kw['extra_body']['chat_template_kwargs'].pop('enable_thinking', None)
    return cfg


def traced_call(original, row, ep, deadline, role, append_event):
    if not inspect.iscoroutinefunction(original):
        raise TypeError('frozen native GenericLLM must be async')

    async def invoke(self, *args, **kwargs):
        r = role.get()
        expected = effort(row['arm'], r)
        kw = self.generation_kwargs
        assert kw['reasoning_effort'] == expected
        assert kw['extra_body']['chat_template_kwargs']['enable_thinking'] is (expected != 'none')
        assert kw['max_tokens'] == (8192 if r == 'analyze' else 32768)
        assert kw['bounded_request_timeout_seconds'] == (600 if r == 'analyze' else 1500)
        started = time.monotonic()
        ok, output = False, None
        try:
            output = await original(self, *args, **kwargs)
            ok = True
            return output
        finally:
            usage, finish = {}, None
            if isinstance(output, tuple) and len(output) == 2 and isinstance(output[1], dict):
                raw = output[1].get('usage', {})
                if isinstance(raw, dict):
                    usage = {k: v for k, v in raw.items() if type(v) in (int, float)}
                    if raw.get('finish_reason') in ('stop', 'length', 'tool_calls', 'content_filter'):
                        finish = raw['finish_reason']
            append_event(ep/'effort.jsonl', dict(role=r, arm=row['arm'], effort=expected,
                enable_thinking=expected != 'none', success=ok, seconds=time.monotonic()-started,
                elapsed=deadline.elapsed(), usage=usage, finish_reason=finish,
                output_cap=kw['max_tokens'], request_cap=kw['bounded_request_timeout_seconds']))
    return invoke


def install(row, ep, deadline, warm):
    import live_admission
    import feedback_parent_policy_20261012 as parent
    from deferred_alarm_transaction_20261012 import protect
    live_admission.locked = protect(live_admission.locked)
    parent.locked = protect(parent.locked)
    parent.install(dict(row, arm='greedy'), ep, deadline, warm)
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from live_admission import append_event
    role = contextvars.ContextVar('long_effort_role', default=None)
    for name in ('_draft', '_improve', '_debug', '_analyze'):
        old = getattr(MCTS, name)
        def factory(old=old, value=name[1:]):
            def call(self, *args, **kwargs):
                token = role.set(value)
                try:
                    return old(self, *args, **kwargs)
                finally:
                    role.reset(token)
            return call
        setattr(MCTS, name, factory())
    GenericLLM.__call__ = traced_call(GenericLLM.__call__, row, ep, deadline, role, append_event)
