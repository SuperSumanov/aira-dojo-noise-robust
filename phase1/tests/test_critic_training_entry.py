from pathlib import Path
import subprocess
import sys

import pytest

from phase1.critic_training_entry import ADMITTED_RELEASES, registered_contract
from phase1.critic_training_run import connect_training
from phase1.global_local_execution_plan import EncoderBinding, PlanError
from phase1.tests.test_critic_train_projection import inputs
from phase1.tests.test_g_reuse_development_screen_plan import Tokenizer


def test_no_effect_release_self_attested():
    assert ADMITTED_RELEASES == {}
    with pytest.raises(PlanError, match='no_qualified_production_release_registered'):
        registered_contract('arbitrary-user-json', Path('/does/not/exist'))


def test_entry_rejects_before_any_cuda_or_file_access(tmp_path):
    code = """
import sys
from phase1.critic_training_entry import registered_contract
from phase1.global_local_execution_plan import PlanError
from pathlib import Path
def forbidden(*a,**k): raise AssertionError('file_open_before_admission')
Path.open=forbidden
try: registered_contract('not-admitted', Path('/forbidden'))
except PlanError: pass
else: raise AssertionError('admitted')
assert 'torch' not in sys.modules and 'transformers' not in sys.modules
print('CLOSED_BEFORE_DATA_AND_MODEL_IMPORT')
"""
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == 'CLOSED_BEFORE_DATA_AND_MODEL_IMPORT'


def test_invalid_training_input_never_calls_model_factory(tmp_path):
    spec = inputs(tmp_path, role='dev')
    def forbidden(*a, **k):
        raise AssertionError('model_factory_called_for_invalid_data')
    with pytest.raises(PlanError, match='projection_not_training_role'):
        connect_training(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384),
                         protocol_sha256='f'*64, sequence=1, setup=forbidden, training_contract_sha256='1'*64)


def test_connection_supplies_baseline_only_local_labels(tmp_path):
    from types import SimpleNamespace
    spec, _ = inputs(tmp_path)
    (tmp_path/'global.json').unlink()
    def setup(plan, pools, encode, truth, **kwargs):
        for row in pools[1]:
            assert truth(row.key) == 1
            assert encode(row.context_sha256, row.a.card_id)
        for row in pools[0]:
            with pytest.raises(PlanError): truth(row.key)
        return SimpleNamespace(consumer=SimpleNamespace(plan=plan))
    fit, session = connect_training(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384),
        protocol_sha256='f'*64, sequence=1, setup=setup, training_contract_sha256='1'*64)
    assert fit.plan == session.consumer.plan and fit.reported_arm == 'Lbudget'


@pytest.mark.parametrize('binding', [{'expected_plan_sha256': '0'*64}, {'expected_shape': {}},
                                   {'expected_totals': {'total_steps': 999, 'valid_tokens': 1}}])
def test_wrong_launch_plan_rejected_before_targets_and_model(tmp_path, binding):
    spec, _ = inputs(tmp_path)
    (tmp_path/'local.json').unlink()
    def forbidden(*a, **k):
        raise AssertionError('model_loaded_before_plan_check')
    with pytest.raises(PlanError, match='production_(encoded_|definition_plan_totals)'):
        connect_training(tmp_path, spec, Tokenizer(), encoder=EncoderBinding('d'*64, 'e'*64, 16384),
            protocol_sha256='f'*64, sequence=1, setup=forbidden, training_contract_sha256='1'*64, **binding)
