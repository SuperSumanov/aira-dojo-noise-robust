"""Cancel only the identified unallocated v2, preserving a migration receipt."""
import os
import subprocess
from live_node_precheck import ROOT
from lifecycle_pilot import read, write, sha

def main():
    launch=read(ROOT/'launch.json')
    if launch['job']!='17229' or launch['plan_sha256']!=sha(ROOT/'plan.json'):
        raise ValueError('wrong original job/plan')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    before=subprocess.check_output(['squeue','-j','17229','-h','-o','%i,%u,%T,%S'],env=env,text=True,timeout=15).strip()
    fields=before.split(',')
    if len(fields)!=4 or fields[:3]!=['17229','yzyang4','PENDING'] or fields[3]!='N/A':
        # Slurm versions may report a projected start rather than N/A. Only
        # PENDING is decisive; confirm zero allocated TRES with scontrol.
        if len(fields)!=4 or fields[:3]!=['17229','yzyang4','PENDING']:
            raise ValueError('not the expected pending own job; no cancellation')
    write(ROOT/'migration-intent.json',dict(job='17229',queue_before=before,
        reason='pre-execution unique worker gateway-port correction and same-model gpu24 placement qualification; no outcome read'))
    subprocess.run(['scancel','17229'],env=env,check=True,timeout=15)
    write(ROOT/'cancel-request.json',dict(job='17229',requested=True,allocation_final_not_yet_verified=True))
    print('PENDING_17229_CANCEL_REQUESTED_VERIFY_ACCOUNTING_BEFORE_MIGRATION')

if __name__=='__main__':main()
