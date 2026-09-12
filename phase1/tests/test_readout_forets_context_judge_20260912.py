import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_context_judge_20260912 import compare


def rows(valid):
    return [dict(status='valid' if i in valid else 'program_error',official_score=.8 if i in valid else None) for i in range(4)]


def test_different_orders_are_reported_not_selected():
    result=compare(rows({0}),[[0,1,2,3],[1,2,3,0]])
    assert result['forward_top2']['valid_probability']==.5
    assert result['reverse_top2']['valid_probability']==0
    assert result['reverse_top2']['conditional_mean_score'] is None
    assert not result['top2_order_invariant']


def test_same_set_different_full_order_and_all_invalid():
    result=compare(rows(set()),[[0,1,2,3],[1,0,3,2]])
    assert result['top2_order_invariant'] and not result['full_order_invariant']
    assert result['uniform4']['conditional_mean_score'] is None


def test_complete_pool_and_invalid_score_not_zero():
    with pytest.raises(ValueError):compare(rows({0})[:3],[[0,1,2,3]]*2)
    with pytest.raises(ValueError):compare(rows({0}),[[0,1,2,3]])
    bad=rows(set());bad[0]['official_score']=0
    with pytest.raises(ValueError):compare(bad,[[0,1,2,3]]*2)
