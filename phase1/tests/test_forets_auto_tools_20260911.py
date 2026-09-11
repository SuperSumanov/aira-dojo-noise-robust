"""Exercise real patched transport methods with an in-memory fake provider."""
import ast
import asyncio
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace as NS, ModuleType
from typing import Any, Dict, List, Optional, Tuple

import pytest
from phase1.forets_auto_tools_patch_20260911 import BACKEND, TREE, revised
from phase1.forets_transport_resilience import BoundedAttemptError, query_with_retries, safe_failure


@pytest.fixture
def backend(monkeypatch):
    raw = subprocess.check_output(['git','show',TREE+':'+BACKEND],cwd=Path(__file__).resolve().parents[2])
    tree = ast.parse(revised(raw))
    klass = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LiteLLMClient')
    selected = {'_query_once_bounded','_query_client','_parse_structured_output','_message_tool_call','_field'}
    klass.body = [n for n in klass.body if getattr(n,'name',None) in selected]
    spec = NS(name='emit', json_schema={'type':'object'}, as_openai_tool_dict={'type':'function'},
              openai_tool_choice_dict={'type':'function','function':{'name':'emit'}})
    def validate(value):
        if set(value) != {'code'} or not isinstance(value['code'],str): raise ValueError('wrong schema')
    ns = dict(asyncio=asyncio,json=json,math=math,os=os,time=time,Any=Any,Dict=Dict,List=List,
        Optional=Optional,Tuple=Tuple,FunctionCallType=dict,OutputType=object,logger=logging.getLogger('fixture'),
        httpx=NS(Timeout=lambda x:x),jsonschema=NS(Draft7Validator=lambda _:NS(validate=validate)),
        FunctionSpec=lambda *_:spec,STRUCTURED_OUTPUT_RETRIES=2,parse_json_output=json.loads)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[])),'actual-patched-transport','exec'),ns)
    fake = ModuleType('dojo.core.solvers.llm_helpers.backends.bounded_retry')
    fake.BoundedAttemptError=BoundedAttemptError;fake.safe_failure=safe_failure;fake.query_with_retries=query_with_retries
    monkeypatch.setitem(sys.modules,fake.__name__,fake)
    monkeypatch.delenv('FORETS_RUN_BUDGET_PATH',raising=False)
    client=ns['LiteLLMClient']();client.model='public-fixture';client.base_url='https://invalid.example';client.api_key=''
    calls=[]
    async def completion(**kwargs):
        calls.append(kwargs)
        message=ns.get('fixture_message',NS(tool_calls=[NS(function=NS(name='emit',arguments='{"code":"print(1)"}'))]))
        return NS(choices=[NS(message=message)],to_dict=lambda:{'usage':{}})
    ns['completion_fn']=completion
    return client,ns,calls


def query(client, **extra):
    kwargs=dict(bounded_transport=True,bounded_request_timeout_seconds=120,max_tokens=8192,structured_output_mode='tools')
    kwargs.update(extra)
    return asyncio.run(client._query_client([dict(role='user',content='public fixture')],kwargs,'{}','emit','test'))


@pytest.mark.parametrize('mode',[None,'auto'])
def test_default_preserved_and_optin_only_changes_tool_choice(backend,mode):
    client,ns,calls=backend
    assert query(client,**({} if mode is None else dict(bounded_tool_choice_mode=mode)))[0]=={'code':'print(1)'}
    assert len(calls)==1 and calls[0]['max_tokens']==8192 and calls[0]['max_retries']==0
    assert calls[0]['tool_choice']==('auto' if mode else {'type':'function','function':{'name':'emit'}})
    assert 'bounded_tool_choice_mode' not in calls[0]


@pytest.mark.parametrize('kwargs',[{'bounded_tool_choice_mode':'bad'},
    {'bounded_tool_choice_mode':'auto','bounded_transport':False},
    {'bounded_tool_choice_mode':'auto','structured_output_mode':'json'}])
def test_invalid_modes_stop_before_request(backend,kwargs):
    client,ns,calls=backend
    with pytest.raises(ValueError):query(client,**kwargs)
    assert calls==[]


@pytest.mark.parametrize('message',[NS(tool_calls=None,content='plain text'),
    NS(tool_calls=[NS(function=NS(name='wrong',arguments='{"code":"print(1)"}'))]),
    NS(tool_calls=[NS(function=NS(name='emit',arguments='{"other":"print(1)"}'))])])
def test_auto_does_not_weaken_output_validation(backend,message):
    client,ns,calls=backend;ns['fixture_message']=message
    with pytest.raises(BoundedAttemptError):query(client,bounded_tool_choice_mode='auto')
    assert len(calls)==1
