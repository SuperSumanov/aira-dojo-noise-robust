"""Real frozen MCTS/GenericLLM/backend; synthetic last transport, no model calls."""
import asyncio
import contextvars
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace

root, arm = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root))
os.environ.update(PYTHON_DOTENV_DISABLED='1', PRIMARY_KEY_QWEN3_8_27B='cpu-fixture-not-a-credential')
def deny(*args, **kwargs):
    raise AssertionError('network forbidden in CPU fixture')
socket.socket.connect = deny
socket.create_connection = deny
import long_effort_trial_20261013 as trial
import long_effort_policy_20261013 as policy
trial.host().setup()
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.core.solvers.llm_helpers.backends import lite_llm as backend
from dojo.config_dataclasses.run import RunConfig
from dojo.solvers.mcts.mcts import MCTS
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.tasks.constants import TASK_DESCRIPTION
from dojo.utils.experiment_deadline import ExperimentDeadline
from dojo.utils.logger import config_logger
from omegaconf import OmegaConf
from lifecycle_pilot import read
import feedback_parent_policy_20261012 as parent

p = read(root/'plan.json')
row = next(r for r in p['schedule'] if r['arm'] == arm)
warm = read(root/'warm.private.json')
fixture = Path(tempfile.mkdtemp(prefix='cpu-long-'+arm+'-', dir=root))
ep = fixture/f"episode-{row['index']}"
ep.mkdir()
parent.initialize(fixture/f"generation-{row['block']}", [r for r in p['schedule'] if r['block'] == row['block']], warm)
native = GenericLLM.__call__
assert inspect.iscoroutinefunction(native)
policy.install(row, ep, ExperimentDeadline(60), warm[row['task']])
cfg = RunConfig.load_from_json(root/f"configs/{row['index']}.json")
cfg.solver.checkpoint_path = str(fixture/'checkpoint')
cfg.logger.output_dir = str(fixture/'log')
task = MLEBenchTask(cfg.task)
config_logger(cfg)
solver = MCTS(OmegaConf.structured(cfg.solver), {TASK_DESCRIPTION: task.task_description, 'lower_is_better': task._search_only_lower_is_better})
solver.create_root_node()
seen = []
class Completion:
    def __init__(self):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content='Fixture plan\n```python\nprint("fixture")\n```'), finish_reason='stop')]
    def to_dict(self):
        return {'usage': {'prompt_tokens': 2, 'completion_tokens': 3}}
async def transport(**kwargs):
    seen.append({k: kwargs[k] for k in ('reasoning_effort', 'max_tokens')})
    assert kwargs['extra_body']['chat_template_kwargs']['enable_thinking'] is (kwargs['reasoning_effort'] != 'none')
    return Completion()
backend.completion_fn = transport
for role in policy.ROLES:
    llm = getattr(solver, role+'_fn').args[0]
    events = []
    wrapped = policy.traced_call(native, row, ep, SimpleNamespace(elapsed=lambda: 0),
        contextvars.ContextVar('fixture_role', default=role), lambda p, e: events.append(e))
    result = asyncio.run(wrapped(llm, messages=[{'role': 'user', 'content': 'CPU fixture only'}]))
    assert result and len(events) == 1 and events[0]['success']
    assert events[0]['finish_reason'] == 'stop' and events[0]['usage']['completion_tokens'] == 3
    assert seen[-1] == {'reasoning_effort': policy.effort(arm, role), 'max_tokens': 8192 if role == 'analyze' else 32768}
node = solver._improve(solver.journal.nodes[1])
assert 'print(' in node.code
events = [json.loads(x) for x in (ep/'effort.jsonl').read_text().splitlines()]
assert events[-1]['role'] == 'improve' and events[-1]['finish_reason'] == 'stop'
# The extended upper bound is still strict; no retry occurs after rejection.
llm = solver.improve_fn.args[0]
try:
    asyncio.run(llm.client.query(messages=[{'role': 'user', 'content': 'CPU fixture'}],
        bounded_transport=True, bounded_request_timeout_seconds=1501))
except ValueError:
    pass
else:
    raise AssertionError('request beyond approved cap was not rejected')
assert len(seen) == 5
print(json.dumps(dict(arm=arm, native_async=True, native_backend_roles=4,
    real_mcts_improve=True, finish_reason_preserved=True, timeout1500_accepted1501_rejected=True,
    http_calls=0, model_calls=0, gpu=False)))
