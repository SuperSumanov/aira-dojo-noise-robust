import json
import pytest
from phase1.historical_program_projection import project,merge
def row(step,parents,code='print(1)',**extra):
    return dict(step=step,parents=parents,code=code,**extra)
def raw(*rows):return b'\n'.join(json.dumps(r).encode() for r in rows)+b'\n'
def test_outcomes_never_affect_projection():
    a=row(1,[0],metric=-999,is_buggy=True,exit_code=1,current_best_node=10)
    b=row(1,[0],metric=999,is_buggy=False,exit_code=0,current_best_node=1)
    assert project(raw(a))['nodes']==project(raw(b))['nodes']
def test_wrapped_and_direct_rows_agree():
    a=row(1,[0],id='opaque')
    assert project(raw(a))['nodes']==project(raw(dict(step=1,data=a)))['nodes']
def test_duplicates_are_not_extra_programs_or_pairs():
    p=project(raw(row(0,[]),row(1,[0]),row(2,[0],code='print(2)')))
    v=merge([p,p]);assert v['unique_steps']==3 and v['duplicate_log_rows']==3
    assert v['same_parent_nonempty_pairs']==v['same_parent_distinct_program_pairs']==1
    assert v['missing_parent_steps']==0 and not v['executability_verified'] and not v['source_admitted']
def test_same_code_children_remain_but_not_distinct_code_pairs():
    v=merge([project(raw(row(1,[0]),row(2,[0])))])
    assert v['unique_steps']==2 and v['same_parent_nonempty_pairs']==1 and v['same_parent_distinct_program_pairs']==0
    assert v['missing_parent_steps']==1
def test_empty_and_unknown_rows_are_explicit_not_silently_admitted():
    v=merge([project(raw(row(0,[],code=None),{'data':{'unknown':'schema'}}))])
    assert v['unique_steps']==1 and v['nonempty_programs']==0 and v['unsupported_lines']==1 and not v['all_lines_supported']
@pytest.mark.parametrize('bad',[row(-1,[]),row(True,[]),row(1,[1]),row(1,[0,0]),row(1,['0']),row(1,[],code=3)])
def test_bad_structure_rejected(bad):
    with pytest.raises(ValueError):project(raw(bad))
def test_conflicting_duplicate_refused():
    with pytest.raises(ValueError,match='conflicting'):merge([project(raw(row(1,[0]),row(1,[0],code='x=2')))])
def test_wrapper_step_mismatch():
    with pytest.raises(ValueError,match='wrapper_step'):project(raw({'step':2,'data':row(1,[0])}))
def test_duplicate_keys_rejected():
    with pytest.raises(ValueError,match='duplicate_json_key'):project(b'{"step":1,"step":2}\n')
def test_credential_shape_blocked_before_json_parse():
    with pytest.raises(ValueError,match='credential'):project(('sk-'+'x'*24).encode())
def test_blank_and_empty_member_rejected():
    for b in (b'',b'\n'):
        with pytest.raises(ValueError):project(b)
