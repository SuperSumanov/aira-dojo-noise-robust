import json
from pathlib import Path
import pytest
from phase1.scripts.check_zero3_private_tools_20260906 import ROOT,environment_gate


def environment():return {'SLURM_JOB_ID':'123','CUDA_HOME':str(ROOT/'prefix'),'CXX':'/usr/bin/g++',
    'NVCC_CCBIN':'/usr/bin/g++','G0_BUDGET_REVISION':'20260905-r5'}


def test_pinned_environment():environment_gate(environment(),'gpu28.cse.cuhk.edu.hk')


@pytest.mark.parametrize('key,value',[('CUDA_HOME','/usr/local/cuda'),('CUDA_HOME','/usr/local/cuda-13.3'),
    ('CXX','g++'),('NVCC_CCBIN','gcc'),('G0_BUDGET_REVISION','r4'),('SLURM_JOB_ID','')])
def test_other_environment_rejected(key,value):
    env=environment();env[key]=value
    with pytest.raises(ValueError):environment_gate(env,'gpu28')


def test_wrong_host_rejected():
    with pytest.raises(ValueError,match='wrong_host'):environment_gate(environment(),'projgpu39')


def test_aggregate_budget_and_original_job_unchanged():
    phase1=Path(__file__).resolve().parents[1]
    a=json.loads((phase1/'manifests/zero3_3090_private_approval_20260906.json').read_text())
    assert a['gpu_seconds_upper_bound']==2*(a['wall_seconds']+a['exit_grace_seconds']+a['safety_margin_seconds'])==2880
    assert a['prior_actual_gpu_seconds']==2*1+1*5==7
    assert a['aggregate_conservative_upper_bound']==2+180+2880==3062<=a['aggregate_cap_gpu_seconds']==3120
    assert a['automatic_retries']==0 and a['existing_12535']=='UNCHANGED_AND_SEPARATELY_ACCOUNTED'


def test_worker_uses_pinned_toolchain_and_shorter_driver_cap():
    script=(Path(__file__).resolve().parents[1]/'scripts/zero3_3090_private_20260906.sbatch').read_text()
    assert '#SBATCH --time=00:18:00' in script and '900s ' in script
    assert '#SBATCH --gres=gpu:rtx3090:2' in script and '#SBATCH --no-requeue' in script
    assert 'CUDA_HOME='+(ROOT/'prefix').as_posix() in script
    assert 'CXX=/usr/bin/g++ NVCC_CCBIN=/usr/bin/g++' in script
    assert 'validate_zero3_3090_20260906' in script
