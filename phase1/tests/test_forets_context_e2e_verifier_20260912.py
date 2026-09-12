import copy
import itertools
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_context_e2e_20260912 import independent_borda,independent_rank,match_archive,parsed_report
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
