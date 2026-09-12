import copy
import itertools
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_context_e2e_20260912 import independent_borda,independent_rank,match_archive,parsed_report,complete_pair_outcomes
from forets_contextual_rank_20260912 import borda


def test_independent_borda_all_four_slot_pairs():
    for n in (3,4):
        permutations=list(itertools.permutations(range(n)))
        for left in permutations:
            for right in permutations:
                assert independent_borda([left,right],n)==borda([left,right],n)


def test_original_report_match_not_same_score_or_latest():
    a=dict(score=.5,valid_submission=True,created_at='a',competition_id='task')
    b=dict(a,created_at='b')
    assert match_archive(parsed_report(a),[('first',a),('last',b)])[0]=='first'
    with pytest.raises(ValueError):match_archive(parsed_report(a),[('other',b)])
    with pytest.raises(ValueError):match_archive(parsed_report(a),[('first',a),('duplicate',a)])


def test_response_reverse_mapping_and_incomplete_rejection():
    raw=dict(model='qwen/qwen3-coder-plus',provider='Alibaba',choices=[dict(finish_reason='stop',message=dict(content=json.dumps({'ranking':[1,2,0]})))])
    assert independent_rank(raw,[2,1,0])==[1,0,2]
    bad=copy.deepcopy(raw);bad['choices'][0]['finish_reason']='length'
    with pytest.raises(ValueError):independent_rank(bad,[2,1,0])
    for rank in ([True,1,2],[0,0,2],[0,1],['0',1,2]):
        bad=copy.deepcopy(raw);bad['choices'][0]['message']['content']=json.dumps({'ranking':rank})
        with pytest.raises(ValueError):independent_rank(bad,[2,1,0])


def test_proven_solver_feedback_is_not_a_missing_grader_field():
    report=dict(score=.4,valid_submission=True,created_at='t',submission_path='/x')
    metric=dict(parsed_report(report),validity_feedback='Submission is valid.')
    assert match_archive(metric,[('original',report)])[0]=='original'
    for altered in (dict(metric,unknown_extra=True),dict(metric,created_at='u'),
                    dict(metric,validity_feedback='Submission is invalid.'),dict(metric,submission_path='/y')):
        with pytest.raises(ValueError):match_archive(altered,[('original',report)])


def test_all_planned_pairs_keep_missingness_outside_score_arithmetic():
    def row(arm,score,task='leaf-classification'):
        return dict(task=task,seed=13,arm=arm,comparable_final=score is not None,official_final_score=score)
    a='uniform_random';b='critic_topk_random'
    for left,right,availability in [(None,None,'both_missing_not_a_score_tie'),(0,None,'random_only_valid'),(None,0,'critic_only_valid')]:
        pair=complete_pair_outcomes([row(a,left),row(b,right)])[0]
        assert pair['availability']==availability and pair['conditional_benefit_delta'] is None
    pair=complete_pair_outcomes([row(a,.4),row(b,.3)])[0]
    assert pair['conditional_benefit_delta']=='0.1' and pair['conditional_score_outcome']=='critic_better'
    pair=complete_pair_outcomes([row(a,.4,'spaceship-titanic'),row(b,.3,'spaceship-titanic')])[0]
    assert pair['conditional_benefit_delta']=='-0.1' and pair['conditional_score_outcome']=='random_better'
    with pytest.raises(ValueError):complete_pair_outcomes([row(a,1)])
    with pytest.raises(ValueError):complete_pair_outcomes([row(a,1),row(a,1),row(b,2)])
