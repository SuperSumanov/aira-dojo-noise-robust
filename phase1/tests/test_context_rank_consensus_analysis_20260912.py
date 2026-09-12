import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from context_rank_consensus_analysis_20260912 import choose,analyze


def test_unanimous_top2_can_be_lost_by_average_tie_break():
    ranks=[(0,2,1,3),(1,2,0,3)]
    assert set(ranks[0][:2])&set(ranks[1][:2])=={2}
    assert choose(ranks,4,'mean_rank')=={0,1}
    assert 2 in choose(ranks,4,'worst_rank')
    assert 2 in choose(ranks,4,'mean_then_worst')


def test_exhaustive_unanimity_property_is_not_an_outcome_claim():
    for n in (3,4):
        result=analyze(n)
        assert result['worst_rank_drops_consensus']==0
        assert result['mean_rank_drops_consensus']>0
        assert result['policies_differ']>0
        assert result['tie_rule_drops_consensus']==0
        assert result['tie_rule_maximum_mean_position_cost']==0
