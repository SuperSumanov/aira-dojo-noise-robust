import ast
from pathlib import Path
import sys
import tarfile
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_context_repeat_20260912 import load_builder,order,derive,patch_budget,AUTH

CAPSULE=Path(__file__).resolve().parents[1]/'releases/forets-context-20260912/release-code-capsule-v3.tar.gz'


def test_checked_legacy_binding_and_entire_matrix():
    ns=load_builder()
    assert ns['BASE']=='5950c7d3acf1e03173ba2ea7081d8ba6593279d9'
    assert order()==[('leaf-classification','uniform_random'),('leaf-classification','critic_topk_random'),
        ('spaceship-titanic','critic_topk_random'),('spaceship-titanic','uniform_random')]


def test_actual_single_gpu_controllers_only_seed_changes():
    names={'forets_block_controller_20260911.py':'enumerate((14,), 1)',
        'forets_block_readout_20260911.py':'for seed in (14,):',
        'forets_paid_route_20260911.py':"FORETS_PAID_SCOPE='route_s14'"}
    with tarfile.open(CAPSULE) as t:
        for name,marker in names.items():
            text=t.extractfile('code/'+name).read().decode();changed=derive(name,text)
            ast.parse(changed);assert marker in changed
            with pytest.raises(ValueError):derive(name,changed)
        for name in ('forets_block_runtime_20260911.py','forets_block_collect_20260911.py'):
            text=t.extractfile('code/'+name).read().decode();assert derive(name,text)==text
        text=t.extractfile('code/forets_e2e_package.py').read().decode()
        changed=derive('forets_e2e_package.py',text);ast.parse(changed)
        assert 'or not config.solver.skip_redundant_critic:' in changed
        with pytest.raises(ValueError):derive('forets_e2e_package.py',changed)


def test_carryover_preserves_all_live_reservation_and_model_logic():
    with tarfile.open(CAPSULE) as t:source=t.extractfile('code/forets_paid_budget_20260911.py').read().decode()
    facts=dict(accounted=2214760245,settled=814760245,calls=214,unknown=2,authorization=AUTH,seed=14)
    changed,auth=patch_budget(source,'qwen/qwen3-coder-flash',**facts)
    original={};new={};exec(compile(source,'<original>','exec'),original);exec(compile(changed,'<repeat>','exec'),new)
    assert new['AUTH']['total']==5714760245
    assert new['AUTH']['judge_reservation']==2600000000
    assert new['AUTH']['logical_request_cap']==100
    assert new['AUTH']['run_limit']==4000000000
    assert (original['MODEL'],original['RESERVE'],original['PROVIDER'])==(new['MODEL'],new['RESERVE'],new['PROVIDER'])
    assert source.split('def reserve(',1)[1]==changed.split('def reserve(',1)[1]
    for bad in (dict(facts,unknown=3),dict(facts,accounted=9800000000),dict(facts,seed=15)):
        with pytest.raises(ValueError):patch_budget(source,'qwen/qwen3-coder-flash',**bad)
