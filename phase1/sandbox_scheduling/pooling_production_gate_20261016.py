"""CPU-only real production install + task wrapper, with cross-thread SIGALRM.

No manual guard installation in this test. Kernel/model/GPU boundaries fail if
called. State files/flock/signal delivery and the production install are real.
Each case uses a fresh process, as production installs hooks once per worker.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

CASES=('success','queue','admit','cancel','release')
class Expired(BaseException):pass
def expire(*args):raise Expired()
def forbidden(*args,**kwargs):raise AssertionError('Forbidden CPU-test external boundary')

def exercise(root,index,case):
    sys.path.insert(0,str(root))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',SLURM_JOB_ID='111',
        PRIMARY_KEY='offline-fixture',PRIMARY_KEY_QWEN3_8_27B='offline-fixture')
    import pooling_trial_20261015 as trial
    import shared_pool_20261015 as pool
    trial.host().setup()
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from pooling_readout_20261015 import verify_queue
    row=trial.schedule()[index]
    deadline=ExperimentDeadline(100)
    with tempfile.TemporaryDirectory(prefix='pool-production-gate-') as td:
        base=Path(td);ep=base/f'episode-{index}';ep.mkdir()
        queue=base/f"pool-{row['block']}";pool.initialize(queue,row['pool_mode'])
        calls=[]
        def state():return json.loads((queue/'state.json').read_text())
        def fake_step(self,value,action):
            assert f'{index}:0' in state()['active']
            calls.append('execute_with_lease');return value,dict(fixture=True)
        class Interpreter:
            def close(self):calls.append('close')
        MLEBenchTask.step_task=fake_step
        # Exercise the REAL install; the test never wraps pool.locked itself.
        with patch.object(JupyterKernelClient,'__init__',forbidden),patch.object(GenericLLM,'__call__',forbidden):
            trial.install_hooks(row,ep,deadline)
            if case=='cancel':deadline.check=expire
            task=object.__new__(MLEBenchTask)
            original=pool.os.replace;counter=[0];injected=[0]
            ordinal={'queue':1,'admit':2,'cancel':2,'release':3}.get(case)
            def replacing(src,dst):
                counter[0]+=1
                if counter[0]==ordinal:
                    def sender():
                        signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGALRM})
                        signal.raise_signal(signal.SIGALRM)
                    injected[0]+=1
                    thread=threading.Thread(target=sender);thread.start();thread.join()
                return original(src,dst)
            previous=signal.signal(signal.SIGALRM,expire);caught=False
            try:
                with patch.object(pool.os,'replace',replacing):
                    try:task.step_task(dict(solver_interpreter=Interpreter()),'fixture')
                    except Expired:caught=True
            finally:signal.signal(signal.SIGALRM,previous)
        assert caught==(case!='success') and injected[0]==int(case!='success')
        assert calls.count('close')==1
        assert ('execute_with_lease' in calls)==(case in ('success','release'))
        assert not state()['active'] and not state()['queue']
        assert list(queue.glob('.state-*'))==[]
        events=[json.loads(x) for x in (queue/'events.jsonl').read_text().splitlines()]
        assert pool.audit(events,row['pool_mode'])['all_released']
        independent=verify_queue(events,row['pool_mode'])
        return dict(index=index,mode=row['pool_mode'],case=case,passed=True,
            events=[e['event'] for e in events],deadline_propagated=caught,signal_injections=injected[0],
            production_install=True,manual_guard=False,independent_queue_check=independent,
            model_calls=0,kernel_calls=0,gpu_calls=0)

def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--index',type=int)
    p.add_argument('--case',choices=CASES);args=p.parse_args()
    if args.case:
        print(json.dumps(exercise(args.root,args.index,args.case),sort_keys=True));return
    rows=[]
    for index in (0,8):
        for case in CASES:
            cp=subprocess.run([sys.executable,'-B',__file__,str(args.root),'--index',str(index),'--case',case],
                capture_output=True,text=True,timeout=60)
            if cp.returncode:
                # Keep raw traceback private; export no exception message/body.
                with (args.root/f'production-gate-{index}-{case}.private.log').open('x') as f:f.write(cp.stdout+cp.stderr)
                raise RuntimeError(f'Production gate failed index={index},case={case},rc={cp.returncode}')
            row=json.loads(cp.stdout.splitlines()[-1]);assert row['passed'];rows.append(row)
    source=args.root/'pooling_trial_20261015.py'
    receipt=dict(passed=True,cases=rows,production_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        interpretation='CPU production wiring and transaction integrity only, not CUDA, speedup or search benefit.')
    with (args.root/'production-guard.safe.json').open('x') as f:json.dump(receipt,f,indent=2,sort_keys=True)
    print(json.dumps(dict(passed=True,production_cases=len(rows),gpu_calls=0,model_calls=0)))

if __name__=='__main__':main()
