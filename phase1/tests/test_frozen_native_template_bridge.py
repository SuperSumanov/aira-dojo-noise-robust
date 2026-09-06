"""Real Dojo operator/Jinja/GenericLLM call path; synthetic state, fake client.

Run in the existing Dojo environment. No native client constructor, API, data
reader, model, interpreter or MCTS loop is invoked. This is a wire-compatibility
test, not complete Dojo rollout or provider-compatibility qualification.
"""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
from types import ModuleType

import pytest

from phase1.frozen_candidate_requests import GenerationOnlyBatch, capture_improve_batch


@pytest.mark.parametrize('complexity', ['simple', 'normal', 'complex'])
def test_native_template_and_generic_llm_wire_match(complexity, monkeypatch):
    from omegaconf import OmegaConf
    import yaml
    # The test owns the client boundary, including factory import. Do not import
    # optional provider SDKs merely to substitute the client immediately after.
    def forbidden_client(*args, **kwargs):
        raise AssertionError('native provider construction forbidden')
    backend = ModuleType('dojo.core.solvers.llm_helpers.backends.utils')
    backend.get_client = forbidden_client
    monkeypatch.setitem(sys.modules, backend.__name__, backend)
    # Telemetry is outside this no-network wire test. Keep Dojo's real logger,
    # but reject every attempted W&B operation rather than importing its SDK.
    # This does not qualify W&B, a provider SDK, or a complete agent rollout.
    telemetry = ModuleType('wandb')
    for name in ('init', 'log', 'save', 'finish'):
        setattr(telemetry, name, forbidden_client)
    monkeypatch.setitem(sys.modules, 'wandb', telemetry)
    from dojo.core.solvers.operators import improve
    from dojo.core.solvers.llm_helpers import generic_llm
    from dojo.core.solvers.llm_helpers.prompt_template import JinjaPrompt
    from dojo.core.solvers.utils.journal import Node, Journal
    from dojo.solvers.utils import Complexity

    root = Path(__file__).resolve().parents[2]
    template_file = root / 'src/dojo/configs/solver/operators/mlebench/aira_operators/improve.yaml'
    template_dict = yaml.safe_load(template_file.read_text())['improve']['system_message_prompt_template']
    # Real JinjaPrompt and Hydra instantiate, without a client configuration.
    # The template string/input list are unmodified. The omitted dataclass target
    # affects only construction, not Jinja's rendering arguments/environment.
    cfg = OmegaConf.create({k:v for k,v in template_dict.items() if k != '_target_'} | {'partial_variables':{}})
    renderer = JinjaPrompt(cfg)
    parent = Node(code='print("synthetic parent")', id='synthetic-parent', ctime=0)
    parent._term_out = ['synthetic past stdout']
    journal = Journal()
    journal.append(parent)
    state = {'cfg':OmegaConf.create({'available_packages':['numpy','torch','pandas'],
                 'execution_timeout':1200,'step_limit':20,'data_preview':True}),
        'memory_op':lambda j,n:';'.join(x.plan or 'synthetic past plan' for x in j.nodes),
        'task_description':'SYNTHETIC_TASK_ONLY', 'journal':journal, 'input_node':parent,
        'step_count':5,'remaining_time':3600, 'complexity':Complexity(complexity),
        'data_preview':'SYNTHETIC_SCHEMA_ONLY'}
    settings = {'temperature':0.7, 'max_tokens':2048}
    seeds = [6,7,8]
    before = random.getstate()
    batch = capture_improve_batch(operator=improve.improve_op, operator_kwargs=state,
        render_system=renderer.format,generation_kwargs=settings,slot_seeds=seeds,
        state_sha256='a'*64,operator_sha256='b'*64,generator_contract_sha256='c'*64)
    assert random.getstate() == before
    assert list(state['cfg'].available_packages) == ['numpy','torch','pandas']

    class FakeClient:
        client_content_key = 'content'
        def __init__(self): self.calls=[]
        def query(self, messages, **kwargs):
            self.calls.append(deepcopy((messages,kwargs)))
            return 'SYNTHETIC_OUTPUT_ONLY', {'prompt_tokens':1, 'completion_tokens':1}

    monkeypatch.setattr(generic_llm, 'get_client', forbidden_client)
    # Execute the actual __call__, deliberately bypassing the network constructor.
    llm = object.__new__(generic_llm.GenericLLM)
    llm.client = FakeClient()
    llm.generation_kwargs = deepcopy(settings)
    llm.system_message_prompt_template = renderer
    llm.call_tracker = 0
    reference=[]
    try:
        for seed in seeds:
            random.seed(seed)
            reference.append(improve.improve_op(improve_llm=llm, **deepcopy(state)))
    finally:
        random.setstate(before)
    client = FakeClient()
    events=[]
    outputs=GenerationOnlyBatch(batch,durable_event=events.append).generate(query=client.query)
    assert client.calls == llm.client.calls
    assert llm.call_tracker == 3
    assert [r[1]['usage']['cumulative_num_llm_calls'] for r in reference] == [1,2,3]
    # Explicitly document that this layer is not GenericLLM's usage adapter.
    assert all('cumulative_num_llm_calls' not in usage for _,usage in outputs)
    assert all('1 NVIDIA GeForce RTX 3090' in call[0][0]['content'] for call in client.calls)
    assert all('6 CPUs' in call[0][0]['content'] for call in client.calls)
    assert 'SYNTHETIC_TASK_ONLY' not in json.dumps(batch.receipt())
