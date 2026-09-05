import pytest
from phase1.tests.test_zero3_final_readout_12535 import accepted_fixture
from phase1.scripts.verify_zero3_final_readout_12573_20260906 import acceptance_gate


def socket_fixture():
    obj=accepted_fixture();obj['job_id']='12573';obj['code_commit']='b84e8baea4de65a16038b4136cee094d29716964'
    return obj


def test_socket_actual_job_binding():acceptance_gate(socket_fixture())


def test_original_job_cannot_substitute_socket_job():
    with pytest.raises(ValueError):acceptance_gate(accepted_fixture())


@pytest.mark.parametrize('field,value',[('job_id','12572'),('code_commit','11ff14a7f6fe9a4a2ab9b830a9829f07b0249b2c'),('gpu_initialized',True)])
def test_failed_or_different_job_rejected(field,value):
    obj=socket_fixture();obj[field]=value
    with pytest.raises(ValueError):acceptance_gate(obj)
