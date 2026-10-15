"""Exercise production lease-before-startup/close ordering, no kernel or model."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def main(root,index):
    sys.path.insert(0,str(root))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',SLURM_JOB_ID='111',
        PRIMARY_KEY='offline-fixture',PRIMARY_KEY_QWEN3_8_27B='offline-fixture')
    import pooling_trial_20261015 as trial
    import shared_pool_20261015 as pool
    trial.host().setup()
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    from live_runtime_hooks import corrected_seconds
    row=trial.schedule()[index]
    with tempfile.TemporaryDirectory(prefix='pool-hook-cpu-') as folder:
        base=Path(folder);ep=base/f'episode-{index}';ep.mkdir()
        pool.initialize(base/f"pool-{row['block']}",row['pool_mode'])
        calls=[]
        def fake_step(self,state,action):
            key,assigned=pool.assigned(base,row['block'],index)
            assert key==f'{index}:0'
            calls.append('execute_with_lease');return state,dict(fixture=True)
        MLEBenchTask.step_task=fake_step
        class Interpreter:
            def close(self):
                pool.assigned(base,row['block'],index);calls.append('close_while_held')
        trial.install_hooks(row,ep,ExperimentDeadline(100))
        task=object.__new__(MLEBenchTask)
        state,result=task.step_task(dict(solver_interpreter=Interpreter()),'fixture')
        assert result==dict(fixture=True) and calls==['execute_with_lease','close_while_held']
        events=[json.loads(x) for x in (base/f"pool-{row['block']}/events.jsonl").read_text().splitlines()]
        audit=pool.audit(events,row['pool_mode'])
        assert audit['admissions']==1 and audit['all_released']
        assert corrected_seconds(1,0)==1
        receipt=dict(index=index,mode=row['pool_mode'],passed=True,events=[e['event'] for e in events],
                     kernel_calls=0,model_calls=0,gpu_calls=0,plan_sha256=trial.sha(root/'plan.json'))
        trial.write(root/f'hook-cpu-{index}.safe.json',receipt)
        print(json.dumps(receipt))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('index',type=int)
    a=p.parse_args();main(a.root,a.index)
