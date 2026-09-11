"""Synthetic diagnostic boundary tests, not GPU acceptance or positive evidence."""
import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_current_pool_20260912 as current


def data():
    rows=[];programs=[]
    for task in current.TASKS:
        for slot in range(4):
            i=len(rows)
            rows.append(dict(index=i,slot=i,repeat=0,task=task,status='valid',valid=True,score=(slot+1)/10))
            programs.append(dict(index=i,task=task,pool_slot=slot,fixed_score=slot))
    return rows,programs


def test_full_scope_and_metric_directions():
    rows,p=data();out=current.summarize(rows,p)
    assert [t['lower_is_better'] for t in out['tasks']]==[True,False]
    for t in out['tasks']:
        assert t['uniform4']['executions']==4 and t['top2']['executions']==2
        assert t['top2']['conditional_mean_score']==pytest.approx(.35)


def test_failure_kept_without_zero_score():
    rows,p=data();rows[3].update(status='program_timeout',valid=False,score=None)
    out=current.summarize(rows,p)['tasks'][0]
    assert out['uniform4']['valid_probability']==.75
    assert out['top2']['valid_probability']==.5
    assert out['top2']['conditional_mean_score']==.3


@pytest.mark.parametrize('change', ['subset','repeat','infra','status','zero_imputation','wrong_task'])
def test_invalid_results_rejected(change):
    rows,p=data()
    if change=='subset':rows.pop()
    if change=='repeat':rows[-1]=copy.deepcopy(rows[0])
    if change=='infra':rows[0]['status']='infrastructure_error'
    if change=='status':rows[0]['valid']=False
    if change=='zero_imputation':rows[0].update(status='program_error',valid=False,score=0)
    if change=='wrong_task':rows[0]['task']=current.TASKS[1]
    with pytest.raises(ValueError):current.summarize(rows,p)


def test_protected_or_arbitrary_roots_fail_before_open(tmp_path):
    with pytest.raises(ValueError):current.checked_root(tmp_path)
