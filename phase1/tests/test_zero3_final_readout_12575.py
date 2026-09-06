import pytest
from phase1.tests.test_zero3_final_readout_12535 import accepted_fixture
from phase1.scripts.verify_zero3_final_readout_12575_20260906 import acceptance_gate


def native_fixture():
    obj=accepted_fixture();obj['job_id']='12575';obj['code_commit']='1c211b87880a1110e3a67cc1dc7d277e5db18441'
    return obj


def test_native_actual_job_binding():acceptance_gate(native_fixture())


def test_original_job_cannot_substitute_native_job():
    with pytest.raises(ValueError):acceptance_gate(accepted_fixture())


@pytest.mark.parametrize('field,value',[('job_id','12572'),('code_commit','11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c'),('gpu_initialized',True)])
def test_failed_or_different_job_rejected(field,value):
    obj=native_fixture();obj[field]=value
    with pytest.raises(ValueError):acceptance_gate(obj)


def test_synthetic_forward_rejects_signed_zero_difference():
    torch=pytest.importorskip('torch')
    from phase1.scripts.verify_zero3_final_readout_12575_20260906 import compare_models
    class Model(torch.nn.Module):
        def __init__(self,negative):
            super().__init__()
            self.weight=torch.nn.Parameter(torch.ones(1,dtype=torch.bfloat16))
            self.output=torch.full((3,),-0.0 if negative else 0.0)
        def forward(self,**kwargs):return {'logits':self.output}
    models=[Model(negative).eval() for negative in (False,True,False)]
    assert torch.equal(models[0].output,models[1].output)
    with pytest.raises(ValueError,match='synthetic_forward_mismatch'):compare_models(models)
