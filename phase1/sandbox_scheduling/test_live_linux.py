"""CPU-only Linux lock/signal tests and pinned native-interface mocks."""
import asyncio
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from live_admission import Lease, initialize, audit_events


def use_lease(directory,key):
    lease=Lease(directory,key,lambda:None,lambda *a,**kw:None)
    lease.acquire();time.sleep(.02);lease.release(cleanup_verified=True)


@unittest.skipUnless(sys.platform=='linux','POSIX runtime required')
class LinuxTests(unittest.TestCase):
    def test_process_concurrency(self):
        for width in (1,2):
            with tempfile.TemporaryDirectory(prefix='r14-lock-') as temp:
                q=Path(temp)/'queue';initialize(q,width)
                workers=[mp.Process(target=use_lease,args=(q,str(i))) for i in range(8)]
                for p in workers:p.start()
                for p in workers:p.join(10);self.assertEqual(p.exitcode,0)
                events=[json.loads(v) for v in (q/'events.jsonl').read_text().splitlines()]
                result=audit_events(events,width)
                self.assertEqual(result['admissions'],8);self.assertTrue(result['all_released'])
                self.assertLessEqual(result['peak_active'],width)

    def test_deadline_cancels_wait_not_owner(self):
        class Expired(BaseException):pass
        def expire(*args):raise Expired()
        with tempfile.TemporaryDirectory(prefix='r14-alarm-') as temp:
            q=Path(temp)/'queue';initialize(q,1)
            owner=Lease(q,'owner',lambda:None,lambda *a,**kw:None);owner.acquire()
            waiter=Lease(q,'waiter',lambda:None,lambda *a,**kw:None)
            old=signal.signal(signal.SIGALRM,expire)
            try:
                signal.setitimer(signal.ITIMER_REAL,.04)
                with self.assertRaises(Expired):waiter.acquire()
            finally:
                signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
            state=json.loads((q/'state.json').read_text())
            self.assertEqual(state['queue'],[]);self.assertEqual(state['active'],['owner'])
            owner.release(cleanup_verified=True)
            events=[json.loads(v) for v in (q/'events.jsonl').read_text().splitlines()]
            self.assertEqual(audit_events(events,1)['cancelled_waits'],1)

    @unittest.skipUnless(os.environ.get('R14_NATIVE_CPU_TEST')=='1','explicit pinned native source only')
    def test_native_hooks_without_execution(self):
        donor=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
        sys.path.insert(0,str(donor/'source/src'))
        os.environ.update(PYTHON_DOTENV_DISABLED='1',
            SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
            LOGGING_DIR='/tmp',MLE_BENCH_DATA_DIR='/tmp/r14-no-official-data',
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_DISABLED='true')
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
        from dojo.solvers.mcts.mcts import MCTS
        from dojo.tasks.mlebench.task import MLEBenchTask
        import live_runtime_hooks as hooks

        kernel=object.__new__(JupyterKernelClient)
        executor=SimpleNamespace(_jupyter_kernel_client=kernel,_wait_timeout=1,_timeout=1)
        result=SimpleNamespace(timed_out=False,is_ok=True,output=['fixture'],data_items=[])
        class Interpreter:
            closes=0
            bad_close=False
            def run(self):return JupyterCodeExecutor.execute_code(executor,'not executed')
            def close(self):
                if self.bad_close:raise RuntimeError('injected cleanup failure')
                self.closes+=1
        interp=Interpreter();state={'solver_interpreter':interp}
        def step(_,state,action):
            state['solver_interpreter'].run()
            if action=='raise':raise RuntimeError('injected candidate failure')
            state['solver_interpreter'].run() # file fetch reuses same lease
            return state,{}
        def preview(_,state):state['solver_interpreter'].run()
        async def llm(*a,**kw):return 'fixture',{}
        clock_start=time.monotonic()
        deadline=SimpleNamespace(check=lambda:None,elapsed=lambda:time.monotonic()-clock_start)
        with tempfile.TemporaryDirectory(prefix='r14-native-') as temp:
            root=Path(temp);ep=root/'episode-0';ep.mkdir();initialize(root/'queue-0',1)
            with patch.object(MLEBenchTask,'step_task',step),patch.object(MCTS,'update_data_preview',preview), \
                 patch.object(JupyterKernelClient,'execute',lambda *a,**kw:result), \
                 patch.object(JupyterKernelClient,'wait_for_ready'), \
                 patch.object(JupyterCodeExecutor,'execute_code',JupyterCodeExecutor.execute_code), \
                 patch.object(GenericLLM,'__call__',llm),patch.object(hooks,'wait_for_ready',lambda *a:True):
                hooks.install({'index':0,'block':0},ep,deadline)
                MCTS.update_data_preview(None,state)
                self.assertEqual(asyncio.run(GenericLLM.__call__(None)),('fixture',{}))
                MLEBenchTask.step_task(None,state,'ok')
                with self.assertRaises(RuntimeError):MLEBenchTask.step_task(None,state,'raise')
                events=[json.loads(v) for v in (root/'queue-0/events.jsonl').read_text().splitlines()]
                audit=audit_events(events,1)
                self.assertEqual(audit['admissions'],3);self.assertTrue(audit['all_released'])
                self.assertEqual(interp.closes,3)
                with self.assertRaises(ValueError):kernel.execute('unscoped')
                interp.bad_close=True
                with self.assertRaises(RuntimeError):MLEBenchTask.step_task(None,state,'ok')
                events=[json.loads(v) for v in (root/'queue-0/events.jsonl').read_text().splitlines()]
                self.assertFalse(audit_events(events,1)['all_released'])

if __name__=='__main__':unittest.main()
