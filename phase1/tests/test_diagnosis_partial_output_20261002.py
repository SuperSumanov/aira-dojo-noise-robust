"""Check only the actual execute method; no socket, model, task or outcome."""
import argparse, ast, hashlib, json, sys, textwrap
from collections import deque
from pathlib import Path
from unittest.mock import patch

R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
ORIGINAL=R/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py'

def main(patched):
    old=ORIGINAL.read_text(); new=patched.read_text()
    expected=old.replace('output=["ERROR: Timeout waiting for output from code block."],\n                    data_items=[],',
        'output=[*text_output, "ERROR: Timeout waiting for output from code block."],\n                    data_items=data_output,')
    expected=expected.replace('output=["ERROR:", f"{content[\'ename\']}: {content[\'evalue\']}\\n", *content["traceback"]],\n                    data_items=[],',
        'output=[*text_output, "ERROR:", f"{content[\'ename\']}: {content[\'evalue\']}\\n", *content["traceback"]],\n                    data_items=data_output,')
    assert new==expected and new!=old,'Unexpected source difference; test stopped'
    sys.path.insert(0,str(R));from task_feedback_real_20261001 import m;m.setup()
    from dojo.core.interpreters.jupyter import jupyter_client as module
    C=module.JupyterKernelClient; original_method=C.execute
    cls=next(n for n in ast.parse(new).body if isinstance(n,ast.ClassDef) and n.name=='JupyterKernelClient')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
    method.decorator_list=[]; method.returns=None
    for arg in method.args.args:arg.annotation=None
    ns=dict(module.__dict__);exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(patched),'exec'),ns)
    rows=[]
    for version,fn in [('original',original_method),('fixed',ns['execute'])]:
        for outcome in ['success','error','timeout']:
            clock=[0.]; marker='SYNTHETIC_OBSERVATION=17\n'
            def msg(kind,content):return {'parent_header':{'msg_id':'synthetic'},'msg_type':kind,'content':content}
            messages=[(1,msg('stream',{'text':marker})),(2,msg('display_data',{'data':{'application/json':{'synthetic':True}}}))]
            messages.append((121,None) if outcome=='timeout' else (3,msg('error',{'ename':'ValueError','evalue':'synthetic','traceback':['synthetic']}) if outcome=='error' else msg('status',{'execution_state':'idle'})))
            queue=deque(messages);client=object.__new__(C);client._time_cycle=300
            client._send_message=lambda **kwargs:'synthetic'
            def receive(seconds):when,value=queue.popleft();clock[0]=when;return value
            client._receive_message=receive
            with patch.object(module.time,'monotonic',lambda:clock[0]):result=fn(client,'not executed',timeout_seconds=120)
            retain=version=='fixed' or outcome=='success'
            assert (marker in result.output)==retain and bool(result.data_items)==retain
            assert result.is_ok==(outcome=='success') and result.timed_out==(outcome=='timeout')
            rows.append(dict(version=version,outcome=outcome,partial_text_preserved=retain,data_items_preserved=retain,ok=result.is_ok,timed_out=result.timed_out))
    report=dict(status='PASS',cases=rows,original_sha256=hashlib.sha256(ORIGINAL.read_bytes()).hexdigest(),
        patched_sha256=hashlib.sha256(patched.read_bytes()).hexdigest(),test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Method-level synthetic streams on pinned real class. Two output-preservation edits only. Live batch unmodified, no task execution, no efficacy claim.')
    with (R/'output-channel-fix-test.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('patched',type=Path);a=p.parse_args();main(a.patched)
