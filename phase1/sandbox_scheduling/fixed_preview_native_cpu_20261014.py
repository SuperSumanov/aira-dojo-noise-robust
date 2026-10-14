"""Native first-Improve CPU test with REAL frozen public preview, no HTTP/GPU.

Uses a separate temporary root; never writes into a closed experiment. Runs one
config per process because native instrumentation is process-global.
"""
import argparse
import asyncio
import hashlib
import inspect
import importlib
import json
import os
from pathlib import Path
import random
import socket
import sys
import tempfile
from types import SimpleNamespace

from fixed_public_preview_20261014 import FirstRequestGuard, digest, load_text, sha, install


def main(root, bundle, index, output):
    root, bundle, output = Path(root), Path(bundle), Path(output)
    if output.exists(): raise FileExistsError('immutable CPU receipt')
    sys.path.insert(0, str(root))
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        PRIMARY_KEY='cpu-fixture-not-a-credential', PRIMARY_KEY_QWEN3_8_27B='cpu-fixture-not-a-credential',
        HARDWARE='one shared NVIDIA RTX3090, two dedicated CPU cores',
        TIME_LIMIT='30 minutes', TIME_LIMIT_SECS='1800', STEP_LIMIT='10000')
    def deny(*args, **kwargs): raise AssertionError('network forbidden in CPU fixture')
    socket.socket.connect=deny; socket.create_connection=deny
    plan_path = root/'plan.json'
    if not plan_path.exists(): plan_path = root/'preparation-plan.json'
    plan=json.loads(plan_path.read_text())
    trial=importlib.import_module(plan.get('native_trial_module','weight_effort_trial_20261014'))
    import weight_effort_policy_20261014 as policy
    trial.host().setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.core.solvers.llm_helpers.backends import lite_llm as backend
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.core.tasks.constants import TASK_DESCRIPTION
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.utils.logger import config_logger
    from omegaconf import OmegaConf
    import feedback_parent_policy_20261012 as parent
    row=plan['schedule'][index]
    assert row['index']==index
    warm=json.loads((root/'warm.private.json').read_text())
    random.seed(row['seed'])
    preview=load_text(bundle,sha(bundle),row['task'])
    with tempfile.TemporaryDirectory(prefix='native-real-preview-') as folder:
        fixture=Path(folder);ep=fixture/f'episode-{index}';ep.mkdir()
        parent.initialize(fixture/f"generation-{row['block']}",
                          [r for r in plan['schedule'] if r['block']==row['block']],warm)
        policy.install(row,ep,ExperimentDeadline(120),warm[row['task']])
        cfg=RunConfig.load_from_json(root/f'configs/{index}.json')
        cfg.solver.checkpoint_path=str(fixture/'checkpoint');cfg.logger.output_dir=str(fixture/'log')
        task=MLEBenchTask(cfg.task);config_logger(cfg)
        solver=MCTS(OmegaConf.structured(cfg.solver),
                    {TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
        solver.create_root_node()
        # This is the real public-data function output, not a generic mock string.
        solver.data_preview=preview
        seen=[]
        class Completion:
            def __init__(self):
                self.choices=[SimpleNamespace(message=SimpleNamespace(content='Fixture\n```python\nprint("fixture")\n```'),finish_reason='stop')]
            def to_dict(self):return {'usage':{'prompt_tokens':2,'completion_tokens':3}}
        async def transport(**kwargs):
            assert kwargs['model']=='openai/'+policy.model(row['arm'])
            seen.append(kwargs['messages'])
            return Completion()
        backend.completion_fn=transport
        node=solver._improve(solver.journal.nodes[1])
        assert len(seen)==1 and 'print(' in node.code
        messages=seen[0];expected=digest(messages)
        # Exercise the actual native client.query boundary with the guard.
        client=solver.improve_fn.args[0].client
        assert inspect.iscoroutinefunction(client.query)
        records=[];guard=FirstRequestGuard(expected,records.append)
        wrapped=guard.wrap(client.query)
        generation=dict(solver.improve_fn.args[0].generation_kwargs)
        asyncio.run(wrapped(messages,**generation))
        assert len(seen)==2 and records[0]['passed']
        rejected=[];bad=FirstRequestGuard('0'*64,rejected.append)
        try:asyncio.run(bad.wrap(client.query)(messages,**generation))
        except ValueError:pass
        else:raise AssertionError('bad first input reached transport')
        assert len(seen)==2 and rejected[0]['passed'] is False
        # Now test the production installation, not only the isolated guard.
        installed=[]
        install(MCTS,GenericLLM,preview,expected,installed.append)
        random.seed(row['seed'])
        solver2=MCTS(OmegaConf.structured(cfg.solver),
                     {TASK_DESCRIPTION:task.task_description,'lower_is_better':task._search_only_lower_is_better})
        solver2.create_root_node()
        solver2.update_data_preview({})  # Must never access an interpreter.
        solver2._improve(solver2.journal.nodes[1])
        assert len(seen)==3 and digest(seen[-1])==expected
        assert [e['event'] for e in installed]==['fixed_public_preview_loaded','first_request_input_gate']
        assert installed[-1]['passed']
        result=dict(index=index,arm=row['arm'],task=row['task'],seed=row['seed'],
            first_prompt_sha256=expected,preview_sha256=hashlib.sha256(preview.encode()).hexdigest(),
            bundle_sha256=sha(bundle),warm_sha256=sha(root/'warm.private.json'),
            native_client_sha256=sha(inspect.getfile(type(client))),actual_native_mcts=True,
            actual_native_transport=True,installed_native_hook=True,bad_prompt_transport_calls=0,
            helper_source_sha256=sha(Path(__file__).with_name('fixed_public_preview_20261014.py')),
            http_calls=0,model_calls=0,gpu_calls=0,
            limitation='CPU transport replaced by a fake response; this does not validate a live model or physical sandbox.')
        with output.open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
        print(json.dumps(result))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('bundle');ap.add_argument('index',type=int);ap.add_argument('output')
    a=ap.parse_args();main(a.root,a.bundle,a.index,a.output)
