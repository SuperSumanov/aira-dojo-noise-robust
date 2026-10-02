"""Reproduce partial-output loss in the pinned client, without tasks or sockets."""
import hashlib, json, sys
from collections import deque
from pathlib import Path
from unittest.mock import patch

R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
SOURCE=R/'source/src/dojo/core/interpreters/jupyter/jupyter_client.py'
EXPECTED='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'

def main():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
    sys.path.insert(0,str(R))
    from task_feedback_real_20261001 import m
    m.setup()
    sys.path.insert(0,str(R/'source/src'))
    from dojo.core.interpreters.jupyter import jupyter_client as module
    C=module.JupyterKernelClient
    marker='SYNTHETIC_OBSERVATION=17\n'
    def message(kind,content):
        return {'parent_header':{'msg_id':'synthetic'},'msg_type':kind,'content':content}
    cases={
        'success':[(1,message('stream',{'text':marker})),(2,message('status',{'execution_state':'idle'}))],
        'error':[(1,message('stream',{'text':marker})),(2,message('error',{'ename':'ValueError','evalue':'synthetic','traceback':['synthetic frame']}))],
        'timeout':[(1,message('stream',{'text':marker})),(121,None)]
    }
    rows=[]
    for name,messages in cases.items():
        clock=[0.]; queue=deque(messages); client=object.__new__(C)
        client._time_cycle=300
        client._send_message=lambda **kwargs:'synthetic'
        def receive(seconds):
            when,value=queue.popleft();clock[0]=when;return value
        client._receive_message=receive
        with patch.object(module.time,'monotonic',lambda:clock[0]):
            result=client.execute('not executed',timeout_seconds=120)
        rows.append(dict(case=name,received_stream=True,observation_returned=marker in result.output,
            ok=result.is_ok,timed_out=result.timed_out))
    assert [r['observation_returned'] for r in rows]==[True,False,False]
    report=dict(status='CONFIRMED_PARTIAL_OUTPUT_DISCARDED',pinned_source_sha256=EXPECTED,
        producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),cases=rows,
        sockets_used=False,task_executions=0,task_outcomes_read=False,
        interpretation='A collected stream is dropped on error/timeout. Does not establish that any particular real check had already emitted useful measurements, nor that preserving them improves final scores. Live experiment unchanged.')
    with (R/'output-channel-review.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
    print(json.dumps(report,sort_keys=True))

if __name__=='__main__':main()
