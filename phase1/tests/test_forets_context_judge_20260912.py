import copy
import sqlite3
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_context_judge_20260912 as judge


def test_reverse_remapping():
    assert judge.remap({'ranking':[3,1,0,2]},[3,2,1,0])==[0,2,3,1]


@pytest.mark.parametrize('rank',[[0,0,1,2],[0,1,2],[0,1,2,4],[False,1,2,3],['0',1,2,3]])
def test_invalid_rank(rank):
    with pytest.raises(ValueError):judge.remap({'ranking':rank},[0,1,2,3])


def catalog():
    return {'data':{'endpoints':[dict(tag='alibaba',context_length=1000000,max_completion_tokens=65536,
        supported_parameters=['structured_outputs'],pricing=dict(prompt='0.00000195',completion='0.00000975',
            input_cache_write='0.0000024375',discount=0))]}}


def test_price_and_capabilities():
    assert judge.checked_catalog(catalog())['reservation_nano']==2600000000
    for key,value in [('completion','0.00001'),('request','0.01'),('prompt','NaN')]:
        c=catalog();c['data']['endpoints'][0]['pricing'][key]=value
        with pytest.raises(ValueError):judge.checked_catalog(c)
    c=catalog();c['data']['endpoints'][0]['supported_parameters']=[]
    with pytest.raises(ValueError):judge.checked_catalog(c)


def test_handover_preserves_unknown_and_stops_on_new_unknown(tmp_path,monkeypatch):
    parent=tmp_path/'parent';parent.mkdir();root=tmp_path/'child';root.mkdir()
    monkeypatch.setattr(judge,'PARENT',parent)
    with sqlite3.connect(parent/'paid.sqlite') as db:
        db.executescript('CREATE TABLE auth(digest TEXT,body TEXT,stopped INTEGER);'
            'CREATE TABLE scopes(scope TEXT PRIMARY KEY,cap INTEGER);'
            'CREATE TABLE calls(id TEXT PRIMARY KEY,scope TEXT,held INTEGER,cost INTEGER,state TEXT,created REAL);')
        db.execute('INSERT INTO auth VALUES (?,?,0)',(judge.PARENT_AUTH,'synthetic-parent'))
        db.execute('INSERT INTO scopes VALUES (?,?)',('old',2000000000))
        db.executemany('INSERT INTO calls VALUES (?,?,?,?,?,?)',[
            ('settled','old',718421106,718421106,'settled',1),('unknown','old',700000000,None,'unresolved',2)])
    budget=judge.budget_module(root,{})
    initial=budget.snapshot(root/'paid.sqlite')
    assert initial['accounted_usd']==1.418421106 and initial['unresolved']==1
    with sqlite3.connect(parent/'paid.sqlite') as db:
        assert db.execute('SELECT stopped FROM auth').fetchone()==(1,)
        assert db.execute('SELECT COUNT(*) FROM calls').fetchone()==(2,)
    budget.reserve(root/'paid.sqlite','context-judge-0','test-request')
    with pytest.raises(budget.BudgetStopped):budget.settle(root/'paid.sqlite','test-request',{})
    final=budget.snapshot(root/'paid.sqlite')
    assert final['accounted_usd']==4.018421106 and final['unresolved']==2 and final['stopped']
    with pytest.raises(budget.BudgetStopped):budget.reserve(root/'paid.sqlite','context-judge-1','cannot-send')
    assert budget.snapshot(root/'paid.sqlite')['calls']==3
