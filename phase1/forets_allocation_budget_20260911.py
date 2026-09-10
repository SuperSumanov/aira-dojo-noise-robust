"""Outer allocation correction only; the verified eight RunConfigs stay unchanged."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
TREE = '3aae90ae26b5ae7b65e6efed14fb49f2907c9c42'


def correction():
    # Use the actual pinned launch gate, with a synthetic remaining-time clock.
    raw = subprocess.check_output(['git','show',TREE+':src/dojo/core/runners/slurm/srun_pool.py'],cwd=ROOT)
    klass = next(n for n in ast.parse(raw).body if isinstance(n,ast.ClassDef) and n.name=='SrunPoolLauncher')
    fn = next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='_can_launch')
    env={}; exec(compile(ast.Module(body=[fn],type_ignores=[]),'<pinned launch gate>','exec'),env)
    startup, step, termination, poll, cleanup, count = 900, 3600, 330, 5, 30, 4
    minimum = math.ceil((startup+count*(step+termination+poll)+cleanup)/60)
    proposed = math.ceil(minimum/5)*5
    def trace(minutes):
        elapsed=startup; values=[]
        for index in range(count):
            remaining=minutes*60-elapsed
            launcher=NS(cfg=NS(step_time_limit_minutes=60,min_remaining_seconds_to_launch=step+termination),
                        _remaining_seconds=lambda:remaining)
            values.append(dict(run_index=index,remaining_seconds=remaining,can_launch=env['_can_launch'](launcher)))
            elapsed+=step+termination+poll
        return values
    old,new=trace(255),trace(proposed)
    assert [r['can_launch'] for r in old]==[True,True,True,False]
    assert all(r['can_launch'] for r in new)
    return dict(status='OUTER_BUDGET_CORRECTION_NOT_AUTHORIZATION_OR_RUNTIME',source_tree=TREE,
        source_sha256=hashlib.sha256(raw).hexdigest(),old_block_minutes=255,
        startup_allowance_seconds=startup,per_step_seconds=step,per_step_termination_allowance_seconds=termination,
        poll_allowance_seconds=poll,final_cleanup_allowance_seconds=cleanup,runs_per_block=count,
        computed_minimum_minutes=minimum,proposed_block_minutes=proposed,blocks=2,gpus=2,
        proposed_block_nominal_gpu_hours=2*proposed/60,proposed_all_blocks_nominal_gpu_hours=4*proposed/60,
        proposed_all_blocks_including_observed_300s_allocation_killwait_gpu_hours=4*(proposed+5)/60,
        old_bound_trace=old,corrected_bound_trace=new,run_config_bytes_changed=False,
        prepared_receipt_sha256='d6fcf987924bf696c8a6ea7fb252a6a634ad3fdac9de192a24eb07ec63fee76d',
        original_plan_sha256='39ac7b7c185f052b4d82508a3c41a019789d54ca1327dff420e599c50b07b915',
        gpu_submissions=0,api_requests=0,readiness=False,
        limits=['arithmetic under stated bounded timings, not a completion guarantee',
                'controller must explicitly enforce preparation/step/cleanup bounds before any actual launch',
                'retains all old proposal records; never overwrite actual usage or claim new experimental results'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True); args=p.parse_args()
    raw=json.dumps(correction(),indent=2,sort_keys=True)+'\n'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as f: f.write(raw)
    print(raw)
