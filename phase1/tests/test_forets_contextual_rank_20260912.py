import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_contextual_rank_20260912 as rank
from forets_context_e2e_patch_20260912 import budget_source,batch_source


def test_borda_invariant_to_swapping_the_two_orders():
    assert rank.borda([[0,1,2],[1,0,2]],3)==[2.5,2.5,1.0]
    assert rank.borda([[1,0,2],[0,1,2]],3)==[2.5,2.5,1.0]
    with pytest.raises(ValueError):rank.borda([[0,1,2]],3)
    with pytest.raises(ValueError):rank.borda([[False,1,2],[0,1,2]],3)


def test_order_and_route():
    raw=dict(model=rank.MODEL,provider='Alibaba',choices=[dict(finish_reason='stop',message=dict(content=json.dumps({'ranking':[2,0,1]})))])
    assert rank.decode_rank(raw,[2,1,0])==[0,2,1]
    raw['choices'][0]['finish_reason']='length'
    with pytest.raises(ValueError):rank.decode_rank(raw,[2,1,0])


def source(name):
    return subprocess.check_output(['git','show','35711518b3b7262bccd3bebfdd2b4a4b7c726715:'+name],text=True)


def test_exact_batch_source_and_unchanged_execution_tail():
    old=source('src/dojo/solvers/fore_ts/batch_runtime.py');new=batch_source(old)
    compile(new,'<new-batch>','exec')
    assert 'score = await solver._query_critic(node)' not in new
    assert new.split("        if ledger.data['selected'] is None:")[1]==old.split("        if ledger.data['selected'] is None:")[1]
    with pytest.raises(ValueError):batch_source(new)


def test_variable_liability_and_shared_call_cap(tmp_path):
    ns={};text=budget_source(source('src/dojo/core/solvers/llm_helpers/backends/paid_budget.py'))
    exec(compile(text,'<new-budget>','exec'),ns)
    dbpath=tmp_path/'paid.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.executescript('CREATE TABLE auth(digest TEXT,body TEXT,stopped INTEGER);CREATE TABLE scopes(scope TEXT PRIMARY KEY,cap INTEGER);'
            'CREATE TABLE calls(id TEXT PRIMARY KEY,scope TEXT,held INTEGER,cost INTEGER,state TEXT,created REAL);')
        db.execute('INSERT INTO auth VALUES (?,?,0)',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
        db.execute('INSERT INTO scopes VALUES (?,?)',('run',4000000000))
    ns['reserve'](dbpath,'run','plus',amount=2600000000)
    assert ns['settle'](dbpath,'plus',{'cost':'1.0'})==1.0  # must use 2.60 hold, not Flash 0.70
    assert not ns['snapshot'](dbpath)['stopped']
    ns['reserve'](dbpath,'run','flash')
    ns['settle'](dbpath,'flash',{'cost':0})
    with sqlite3.connect(dbpath) as db:
        db.executemany('INSERT INTO calls VALUES (?,?,?,?,?,?)',[(f'count-{i}','run',0,0,'settled',i) for i in range(98)])
    with pytest.raises(ns['BudgetStopped']):ns['reserve'](dbpath,'run','over-100')
