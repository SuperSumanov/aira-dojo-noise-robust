"""Exercise frozen native async GenericLLM and policy hooks, mock transport ONLY."""
import asyncio,contextvars,inspect,json,os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
root=Path(sys.argv[1]);arm=sys.argv[2];sys.path.insert(0,str(root))
os.environ.update(PYTHON_DOTENV_DISABLED='1',PRIMARY_KEY_QWEN3_8_27B='cpu-fixture-not-a-credential')
import feedback_effort_trial_20261012 as trial
import feedback_effort_policy_20261012 as policy
trial.host().setup()
from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
from dojo.config_dataclasses.run import RunConfig
from dojo.solvers.mcts.mcts import MCTS
from dojo.tasks.mlebench.task import MLEBenchTask
from dojo.core.tasks.constants import TASK_DESCRIPTION
from dojo.utils.experiment_deadline import ExperimentDeadline
from dojo.utils.logger import config_logger
from omegaconf import OmegaConf
from lifecycle_pilot import read
plan=read(root/'plan.json');row=next(r for r in plan['schedule'] if r['arm']==arm);warm=read(root/'warm.private.json')
fixture=Path(tempfile.mkdtemp(prefix='cpu-async-'+arm+'-',dir=root));ep=fixture/f"episode-{row['index']}";ep.mkdir()
policy.initialize(fixture/f"generation-{row['block']}",[r for r in plan['schedule'] if r['block']==row['block']],warm)
native=GenericLLM.__call__;assert inspect.iscoroutinefunction(native)
policy.install(row,ep,ExperimentDeadline(60),warm[row['task']])
assert inspect.iscoroutinefunction(GenericLLM.__call__)
cfg=RunConfig.load_from_json(root/f"configs/{row['index']}.json");cfg.solver.checkpoint_path=str(fixture/'checkpoint');cfg.logger.output_dir=str(fixture/'log')
task=MLEBenchTask(cfg.task);config_logger(cfg)
solver=MCTS(OmegaConf.structured(cfg.solver),{TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
solver.create_root_node();seen=[]
for role in ('draft','improve','debug','analyze'):
    llm=getattr(solver,role+'_fn').args[0]
    async def query(messages,role=role,**kwargs):
        assert kwargs['extra_body']['chat_template_kwargs']['enable_thinking'] is policy.thinking(arm,role)
        seen.append(role)
        return 'Fixture plan\n```python\nprint("fixture")\n```',{'total_tokens':2}
    llm.client.query=query
    # Full native request construction -> mocked final transport; no HTTP call.
    events=[];cv=contextvars.ContextVar('native_phase',default=role)
    wrapped=policy.traced_call(native,row,ep,SimpleNamespace(elapsed=lambda:0),cv,lambda p,e:events.append(e))
    result=asyncio.run(wrapped(llm,messages=[{'role':'user','content':'CPU-only test'}]))
    assert result and len(events)==1 and events[0]['success'] and events[0]['usage']['total_tokens']==2
# Additionally execute actual MCTS Improve -> operator -> native async call ->
# code parser through the installed role hook; no substituted operator helper.
node=solver._improve(solver.journal.nodes[1]);assert 'print(' in node.code
calls=[json.loads(x) for x in (ep/'effort.jsonl').read_text().splitlines()]
assert calls and calls[-1]['role']=='improve' and calls[-1]['success']
assert seen.count('improve')>=2 and set(seen)=={'draft','improve','debug','analyze'}
print(json.dumps(dict(arm=arm,native_async=True,native_transport_roles=4,real_mcts_improve=True,http_calls=0,gpu=False)))
