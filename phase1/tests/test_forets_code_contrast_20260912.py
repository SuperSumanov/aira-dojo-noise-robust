"""Artificial strings only. No task data, GPU, network or model."""
import pytest
from phase1.verify_forets_review_selection_20260912 import code_contrast, replay


def test_changed_slot_with_identical_code_is_not_changed_program():
    r=code_contrast(['x=1','x=1','x=2'],0,1)
    assert r['unique_raw_programs']==r['unique_ast_programs']==2
    assert not r['selected_raw_differs_from_same_pool_uniform']
    assert not r['selected_ast_differs_from_same_pool_uniform']


def test_ast_equivalence_does_not_conflate_value_change():
    r=code_contrast(['x=1','# comment\nx = 1\n','x=2'],0,1)
    assert r['unique_raw_programs']==3 and r['unique_ast_programs']==2
    assert r['selected_raw_differs_from_same_pool_uniform']
    assert not r['selected_ast_differs_from_same_pool_uniform']
    assert code_contrast(['x=1','x=2'],0,1)['selected_ast_differs_from_same_pool_uniform']


def test_syntax_failure_is_unknown_not_false_equivalence():
    r=code_contrast(['invalid(', 'invalid('],0,1)
    assert r['ast_parse_failures']==2 and r['unique_ast_programs'] is None
    assert r['selected_ast_differs_from_same_pool_uniform'] is None


@pytest.mark.parametrize('codes,a,b',[([],0,0),(['x=1'],True,0),(['x=1'],0,1),([None],0,0)])
def test_invalid_scope(codes,a,b):
    with pytest.raises(ValueError):code_contrast(codes,a,b)


def test_seed_is_forwarded_not_frozen_to_old_seed():
    found=False
    for step in range(6):
        a=replay(4,[.4,.3,.2,.1],'critic_topk_random','common_priority_v1',11,'artificial',step)
        b=replay(4,[.4,.3,.2,.1],'critic_topk_random','common_priority_v1',12,'artificial',step)
        found=found or a!=b
    assert found
