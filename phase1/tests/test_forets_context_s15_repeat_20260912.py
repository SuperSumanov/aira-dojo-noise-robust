import copy
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_context_s15_repeat_20260912 import load_builder,order,check_gate,derive,BASE,patch_budget,AUTH


def test_binding_and_manifest_seed():
    ns=load_builder()
    assert ns['BASE']==BASE and 12 not in ns['build'].__code__.co_consts
    assert order()==[('leaf-classification','critic_topk_random'),('leaf-classification','uniform_random'),
        ('spaceship-titanic','uniform_random'),('spaceship-titanic','critic_topk_random')]
    assert derive('forets_e2e_package.py','unchanged')=='unchanged'
    assert derive('forets_block_runtime_20260911.py','unchanged')=='unchanged'


def test_gate_does_not_select_positive_scores():
    # Entirely artificial evidence, never a production experiment claim.
    verified=dict(job='13124',source_tree=BASE,seed=14,verification='passed',valid_finals=3,
        numerical_final_regrades=3,pools=[dict(completed=True,context_ranked=True)])
    diagnostic=dict(comparable_pairs=1,valid_final_solutions=3)
    for sign in (-1,0,1):
        value=dict(verified,arbitrary_score_difference=sign)
        check_gate(value,diagnostic)
    for change in (dict(verification='failed'),dict(numerical_final_regrades=2),
                   dict(pools=[dict(completed=False,context_ranked=True)])):
        with pytest.raises(ValueError):check_gate(dict(verified,**change),diagnostic)
    with pytest.raises(ValueError):check_gate(verified,dict(diagnostic,comparable_pairs=0))


def test_budget_keeps_unknown_and_global_limit():
    source='AUTH={}\nAUTH_RAW = json.dumps(AUTH, sort_keys=True)\ndef reserve(): return 1\n'
    facts=dict(accounted=3000000000,settled=1600000000,calls=300,unknown=2,authorization=AUTH,seed=15)
    changed,auth=patch_budget(source,'qwen/qwen3-coder-flash',**facts)
    assert auth['total']==6500000000 and auth['predecessor_unresolved']==2
    assert changed.split('def reserve',1)[1]==source.split('def reserve',1)[1]
    for bad in (dict(facts,accounted=9900000000),dict(facts,unknown=3),dict(facts,seed=14)):
        with pytest.raises(ValueError):patch_budget(source,'qwen/qwen3-coder-flash',**bad)
