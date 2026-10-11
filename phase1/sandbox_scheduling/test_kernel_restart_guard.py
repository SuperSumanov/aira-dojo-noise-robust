import ast,dataclasses,logging,os,subprocess,time,types,unittest
from pathlib import Path
from textwrap import indent
from kernel_restart_guard import overlay

def source():
    if os.environ.get('R14_CLIENT_SOURCE'):return Path(os.environ['R14_CLIENT_SOURCE']).read_text()
    return subprocess.check_output(['git','show','f7ccd79323112b10ccc82d8e9ec9d6cf089df607:src/dojo/core/interpreters/jupyter/jupyter_client.py']).decode()

def build(fixed=True):
    text=overlay(source()) if fixed else source()
    cls=next(x for x in ast.parse(text).body if isinstance(x,ast.ClassDef) and x.name=='JupyterKernelClient')
    fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='execute');fn.decorator_list=[]
    @dataclasses.dataclass
    class Result:
        is_ok:bool;output:list;data_items:list;timed_out:bool=False
    class Fake:ExecutionResult=Result
    clock=types.SimpleNamespace(now=0.)
    scope=dict(time=types.SimpleNamespace(monotonic=lambda:clock.now),log=logging.getLogger('test'),JupyterKernelClient=Fake,ExecutionResult=Result,indent=indent)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'pinned-f7-execute','exec'),scope)
    Fake.execute=scope['execute'];obj=Fake();obj._time_cycle=300
    obj._send_message=lambda **kw:'active'
    obj.messages=[]
    def receive(timeout):
        clock.now+=1 if obj.messages else timeout
        return obj.messages.pop(0) if obj.messages else None
    obj._receive_message=receive
    return obj,clock

def msg(state,parent=None,channel='iopub'):
    return dict(msg_type='status',channel=channel,parent_header={} if parent is None else {'msg_id':parent},content={'execution_state':state})

class Tests(unittest.TestCase):
    def test_old_client_ignores_real_parentless_lifecycle(self):
        obj,clock=build(False);obj.messages=[msg('restarting')]
        result=obj.execute('unchanged',12)
        self.assertTrue(result.timed_out);self.assertGreater(clock.now,12)
    def test_restart_and_dead_are_failures_not_timeout_or_success(self):
        for state in ('restarting','dead'):
            obj,clock=build();obj.messages=[msg(state)]
            result=obj.execute('unchanged',12)
            self.assertFalse(result.is_ok);self.assertFalse(result.timed_out);self.assertEqual(clock.now,1)
    def test_normal_parent_filter_retained(self):
        obj,clock=build();obj.messages=[msg('idle','other'),msg('busy','active'),msg('idle','active')]
        self.assertTrue(obj.execute('unchanged',12).is_ok);self.assertEqual(clock.now,3)
    def test_starting_is_not_death(self):
        obj,_=build();obj.messages=[msg('starting'),msg('idle','active')]
        self.assertTrue(obj.execute('unchanged',12).is_ok)
    def test_wrong_channel_does_not_trip_guard(self):
        obj,_=build();obj.messages=[msg('restarting',channel='shell'),msg('idle','active')]
        self.assertTrue(obj.execute('unchanged',12).is_ok)
    def test_normal_error_semantics_unchanged(self):
        for fixed in (False,True):
            obj,_=build(fixed);obj.messages=[dict(msg_type='error',parent_header={'msg_id':'active'},content=dict(ename='ValueError',evalue='test',traceback=[]))]
            result=obj.execute('unchanged',12)
            self.assertFalse(result.is_ok);self.assertFalse(result.timed_out)
            self.assertEqual(result.output,['ERROR:','ValueError: test\n'])

if __name__=='__main__':unittest.main()
