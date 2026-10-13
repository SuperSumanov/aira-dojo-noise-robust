"""Four fixed conditions, no adaptation of arm/weights to observed outcomes."""
import copy
import hashlib
import json
import long_effort_policy_20261013 as old

ARMS = ('old_fast', 'old_medium', 'new_fast', 'new_medium')
ORDER = ('old_fast', 'new_medium', 'new_fast', 'old_medium')
ROLES = old.ROLES
RUN, SLOT, CAP = 1800, 1960, 9000
BASE_MODEL = 'qwen3.8-27b'
TRAINED_MODEL = 'qwen3.8-27b-score-step30'


def model(arm):
    if arm not in ARMS:
        raise ValueError('unknown condition')
    return TRAINED_MODEL if arm.startswith('new_') else BASE_MODEL


def effort(arm, role):
    if arm not in ARMS or role not in ROLES:
        raise ValueError('unknown condition or role')
    return 'medium' if role == 'analyze' or arm.endswith('_medium') else 'none'


def normalize(cfg):
    cfg = copy.deepcopy(cfg)
    for op in cfg['solver']['operators'].values():
        op['llm']['client']['model_id'] = BASE_MODEL
        kw = op['llm']['generation_kwargs']
        kw.pop('reasoning_effort', None)
        kw['extra_body']['chat_template_kwargs'].pop('enable_thinking', None)
    return cfg


def trace(original, row, ep, deadline, role, append_event):
    async def checked(self, *args, **kwargs):
        assert self.client.model == model(row['arm'])
        output = await original(self, *args, **kwargs)
        if isinstance(output, tuple) and isinstance(output[1], dict):
            messages = output[1].get('prompt_messages')
            if messages is not None:
                append_event(ep/'prompt-hashes.jsonl', dict(role=role.get(), arm=row['arm'],
                    model_id=self.client.model,
                    sha256=hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()))
        return output
    def emit(path, event):
        append_event(path, dict(event, model_id=model(row['arm'])))
    return old.traced_call(checked, row, ep, deadline, role, emit)


def install(row, ep, deadline, warm):
    # Reuse the exact native-role/context handling, not its old three-arm policy.
    old.effort = effort
    native_trace = old.traced_call
    def wrapped(original, row, ep, deadline, role, emit):
        old.traced_call = native_trace
        try:
            return trace(original, row, ep, deadline, role, emit)
        finally:
            old.traced_call = wrapped
    old.traced_call = wrapped
    try:
        old.install(row, ep, deadline, warm)
    finally:
        old.traced_call = native_trace
