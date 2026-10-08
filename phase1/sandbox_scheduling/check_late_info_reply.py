"""CPU fault injection on exact frozen execute method; not a live-kernel test."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from textwrap import indent
from lifecycle_pilot import sha, SECRET

PATH = Path('/research/d7/spc/yzyang4/scheduling-neural-qualified-overlap-20261008-evening-v1/source/src/dojo/core/interpreters/jupyter/jupyter_client.py')
PIN = 'a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'


class Result:
    DataItem = SimpleNamespace
    def __init__(self, **kw):
        self.__dict__.update(kw)
        self.timed_out = kw.get('timed_out',False)


class Transport:
    def __init__(self, messages):
        self._time_cycle = 300
        self.messages = list(messages)
        self.requests = []
        self.now = 0.0
    def _send_message(self, **kwargs):
        self.requests.append(kwargs)
        return 'execution'
    def _receive_message(self, _timeout):
        self.now += .01
        return self.messages.pop(0)


def message(parent, kind, content):
    return dict(parent_header={'msg_id':parent}, msg_type=kind, content=content)


def main():
    if sha(PATH) != PIN or SECRET.search(PATH.read_bytes()):
        raise ValueError('frozen client source refused')
    cls = next(v for v in ast.parse(PATH.read_text()).body if isinstance(v,ast.ClassDef) and v.name=='JupyterKernelClient')
    method = next(v for v in cls.body if isinstance(v,ast.FunctionDef) and v.name=='execute')
    results = []
    for fail in (False,True):
        stale = [message('old-info','status',{'execution_state':'idle'}),
                 message('old-info','kernel_info_reply',{}),
                 message('old-info','error',{'ename':'Stale','evalue':'ignored','traceback':[]})]
        own = ([message('execution','error',{'ename':'Expected','evalue':'retained','traceback':[]})] if fail else
               [message('execution','stream',{'text':'actual-execution'}),message('execution','status',{'execution_state':'idle'})])
        client = Transport(stale+own)
        namespace = dict(ExecutionResult=Result, JupyterKernelClient=SimpleNamespace(ExecutionResult=Result),
            time=SimpleNamespace(monotonic=lambda:client.now),log=SimpleNamespace(info=lambda *_:None),indent=indent)
        exec(compile(ast.Module(body=[method],type_ignores=[]),'<frozen-execute>','exec'),namespace)
        result = namespace['execute'](client,'synthetic-no-execution',30)
        if len(client.requests)!=1 or client.requests[0]['message_type']!='execute_request':
            raise ValueError('execution resent')
        if result.is_ok == fail or result.timed_out or client.messages:
            raise ValueError('stale reply changed completion')
        if not fail and result.output != ['actual-execution']:
            raise ValueError('stale content included')
        if fail and not any('Expected' in v for v in result.output):
            raise ValueError('current execution error hidden')
        results.append(dict(current_execution_error=fail, passed=True, execution_requests=1))
    print(json.dumps(dict(client_source_sha256=PIN,cases=results,
        boundary='CPU injected transport using frozen execute AST; does not prove real websocket health or live timeout root cause.'),sort_keys=True))


if __name__ == '__main__':
    main()
