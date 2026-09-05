import pytest
from phase1.scripts.validate_zero3_session_gpu_20260905 import allocation_gate


def env():
    return {'SLURM_JOB_ID':'12345','ZERO3_GPU_APPROVAL_RECEIPT_SHA':'a'*64,'ZERO3_CODE_COMMIT':'b'*40,
        'CUDA_VISIBLE_DEVICES':'0,1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'1',
        'MAX_JOBS':'2','CUBLAS_WORKSPACE_CONFIG':':4096:8','PYTHONHASHSEED':'6'}


def test_bound_call_configuration():allocation_gate(env())


@pytest.mark.parametrize('key',list(env()))
def test_missing_field_cannot_start(key):
    e=env();del e[key]
    with pytest.raises(ValueError):allocation_gate(e)


@pytest.mark.parametrize('devices',['','0','0,1,2','0,1,2,3','0,0','0,','a,b','0, 1'])
def test_wrong_world_cannot_start(devices):
    e=env();e['CUDA_VISIBLE_DEVICES']=devices
    with pytest.raises(ValueError):allocation_gate(e)
