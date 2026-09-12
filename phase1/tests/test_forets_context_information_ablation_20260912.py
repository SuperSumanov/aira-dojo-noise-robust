import json
from pathlib import Path
import sys
import pytest
import sqlite3

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_context_information_ablation_20260912 import payloads,top2,TASKS,remap
import forets_context_information_ablation_20260912 as ablation


def test_only_information_fields_differ_and_order_alternates():
    for task,expected in zip(TASKS,[['full','full','omitted','omitted'],['omitted','omitted','full','full']]):
        out=payloads(task,'description',['a','b','c','d'])
        assert [i['condition'] for i,p in out]==expected
        for forward in (0,1):
            first=json.loads(json.dumps(out[forward][1]));second=json.loads(json.dumps(out[forward+2][1]))
            full,control=(first,second) if task==TASKS[0] else (second,first)
            context=json.loads(full['messages'][1]['content'])
            assert context.pop('verified_shared_environment')
            assert context.pop('resources')['program_wall_limit_seconds']==300
            assert context==json.loads(control['messages'][1]['content'])
            full['messages'][1]=control['messages'][1]
            assert full==control
        assert [c['code'] for c in json.loads(out[1][1]['messages'][1]['content'])['candidates']]==['d','c','b','a']


def test_borda_and_strict_order_translation():
    assert top2([[3,2,1,0],[0,1,2,3]])==[0,1]
    assert top2([[2,1,3,0],[2,3,1,0]])==[2,1]
    assert remap({'ranking':[0,2,1,3]},[3,2,1,0])==[3,1,2,0]
    for bad in ([[0,0,2,3],[0,1,2,3]],[[0,1,2,3]]):
        with pytest.raises(ValueError):top2(bad)


def test_input_envelope_is_checked_without_truncation():
    with pytest.raises(ValueError):payloads(TASKS[0],'x'*600000,['a','b','c','d'])
    with pytest.raises(ValueError):payloads(TASKS[0],'x',['a'])


def parent_ledger(tmp_path,monkeypatch,held=1500000000,settled=100000000):
    parent=tmp_path/'parent';parent.mkdir();child=tmp_path/'child';child.mkdir()
    monkeypatch.setattr(ablation,'PARENT',parent)
    rows=[('paid','old',settled,settled,'settled',1.0),
          ('unknown1','old',700000000,None,'unresolved',2.0),
          ('unknown2','old',held-settled-700000000,None,'unresolved',3.0)]
    with sqlite3.connect(parent/'paid.sqlite') as db:
        db.executescript('CREATE TABLE auth (digest TEXT,body TEXT,stopped INTEGER);'
            'CREATE TABLE scopes (scope TEXT PRIMARY KEY,cap INTEGER);'
            'CREATE TABLE calls (id TEXT PRIMARY KEY,scope TEXT,held INTEGER,cost INTEGER,state TEXT,created REAL);')
        db.execute('INSERT INTO auth VALUES (?,?,0)',(ablation.PARENT_AUTH,'{}'))
        db.execute('INSERT INTO scopes VALUES (?,?)',('old',10000000000))
        db.executemany('INSERT INTO calls VALUES (?,?,?,?,?,?)',rows)
    (parent/'independent-context-verification.json').write_text(json.dumps(dict(verification='passed',job='13128',seed=15,
        cumulative_settled_usd=settled/1e9,cumulative_accounted_usd=held/1e9)))
    return parent,child,rows


def test_handover_preserves_every_liability_and_cannot_repeat(tmp_path,monkeypatch):
    parent,child,rows=parent_ledger(tmp_path,monkeypatch)
    budget=ablation.transfer_budget(child)
    assert budget.AUTH['total']==4500000000 and budget.AUTH['predecessor_unresolved']==2
    with sqlite3.connect(parent/'paid.sqlite') as db:assert db.execute('SELECT stopped FROM auth').fetchone()==(1,)
    with sqlite3.connect(child/'paid.sqlite') as db:
        assert db.execute('SELECT * FROM calls ORDER BY id').fetchall()==rows
        assert db.execute('SELECT cap FROM scopes WHERE scope="old"').fetchone()==(1500000000,)
        assert db.execute('SELECT COUNT(*) FROM scopes').fetchone()==(9,)
    with pytest.raises(ValueError):ablation.transfer_budget(child)


@pytest.mark.parametrize('reason',['cap','proof','unknown'])
def test_handover_rejects_before_sealing(tmp_path,monkeypatch,reason):
    parent,child,rows=parent_ledger(tmp_path,monkeypatch,held=8000000000 if reason=='cap' else 1500000000)
    if reason=='proof':
        p=parent/'independent-context-verification.json';obj=json.loads(p.read_text());obj['cumulative_settled_usd']=.5;p.write_text(json.dumps(obj))
    if reason=='unknown':
        with sqlite3.connect(parent/'paid.sqlite') as db:db.execute('UPDATE calls SET state="settled" WHERE id="unknown2"')
    with pytest.raises(ValueError):ablation.transfer_budget(child)
    with sqlite3.connect(parent/'paid.sqlite') as db:assert db.execute('SELECT stopped FROM auth').fetchone()==(0,)
    assert not (child/'paid.sqlite').exists()
