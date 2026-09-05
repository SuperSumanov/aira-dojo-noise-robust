import pytest
from phase1.verify_critic_component_g0 import ContractError, validate_scheduler_allocation
from phase1.tests.test_g0_r4_budget import allocation


def test_r5_cumulative_budget():
    result = validate_scheduler_allocation(*allocation(time='01:45:00', revision='20260905-r5'))
    assert result['time_limit'] == '01:45:00'
    used = 2*(156+4+131+191)+1
    assert used == 965
    assert ((14400-used)//2-300-60)//60*60 == 6300
    assert used+2*(6300+300+60) == 14285 < 14400


@pytest.mark.parametrize('time',['01:49:00','01:45:01','01:46:00','01:57:00','02:00:00'])
def test_r5_rejects_over_budget_times(time):
    with pytest.raises(ContractError,match='time limit'):
        validate_scheduler_allocation(*allocation(time=time,revision='20260905-r5'))


def test_r5_requires_final_only():
    with pytest.raises(ContractError,match='requires final-only'):
        validate_scheduler_allocation(*allocation(time='01:45:00',revision='20260905-r5',recovery='0'))


def test_r4_and_legacy_still_unchanged():
    assert validate_scheduler_allocation(*allocation())['time_limit'] == '01:49:00'
    assert validate_scheduler_allocation(*allocation(time='01:57:00',revision='legacy'))['time_limit'] == '01:57:00'
