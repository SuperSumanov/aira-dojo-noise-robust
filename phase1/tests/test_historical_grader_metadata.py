import json
import pytest
from phase1.historical_grader_metadata import project,aggregate

def raw(x):return json.dumps(x).encode()
def test_nested_metadata_not_grades():
    v=project(raw({'score':.9,'nested':[{'evaluator_commit':'a'*40,'accuracy':.2}]}))
    assert v['possible_provenance_field_counts']=={'evaluator_commit':1}
    assert not v['evaluator_identity_attested']
    assert 'a'*40 not in json.dumps(v) and 'score' not in v

def test_grade_changes_do_not_change_metadata_decisions():
    a=project(raw({'score':.1,'metrics':{'accuracy':0}}));b=project(raw({'score':.9,'metrics':{'accuracy':1}}))
    assert a['possible_provenance_field_counts']==b['possible_provenance_field_counts']=={}
    assert a['record_sha256']!=b['record_sha256']

@pytest.mark.parametrize('payload',[b'{"score":1,"score":2}',b'null',b'1',b'"text"',b'',b' '*((1<<20)+1)],
                         ids=['duplicate','null','number','text','empty','oversize'])
def test_bad_container(payload):
    with pytest.raises(ValueError):project(payload)

def test_credential_rejected_before_projection():
    with pytest.raises(ValueError,match='credential'):
        project(raw({'comment':'sk-'+'x'*30}))

def test_presence_not_identity_or_truth():
    r=project(raw({'evaluator_commit':None,'SCORE':.5}))
    assert r['has_possible_provenance_fields'] and not r['evaluator_identity_attested']

def test_aggregate_independent_counts():
    r=[project(raw({'grader_commit':'a'})),project(raw({'nested':{'grader_commit':'b'}})),project(raw({'grade':1}))]
    a=aggregate(r)
    assert a['records']==3 and a['records_with_possible_provenance']==2
    assert a['possible_provenance_field_counts']=={'grader_commit':2}

def test_aggregate_forbids_claim_escalation():
    r=project(raw({}));r['evaluator_identity_attested']=True
    with pytest.raises(ValueError,match='claim'):aggregate([r])

def test_complexity_guard():
    r={}
    for i in range(42):r={'child':r}
    with pytest.raises(ValueError,match='complexity'):project(raw(r))
