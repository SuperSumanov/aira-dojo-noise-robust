import ast
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from derive_forets_context_pool_s14_20260912 import derive,freeze,TREE


def source():return (Path(__file__).resolve().parents[1]/'forets_current_pool_20260912.py').read_text(encoding='utf8')


def test_execution_and_reduction_functions_unchanged_except_run_seed():
    raw=source();changed=derive(raw);before=ast.parse(raw);after=ast.parse(changed)
    def get(tree,name):return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    for name in ['summarize','readout','binding_context','checked_root','check_frozen_code']:
        assert ast.dump(get(before,name))==ast.dump(get(after,name))
    assert TREE in changed and 'seed=14' in changed and 'seed15 allocation still active' in changed
    assert 'seed=11' not in changed and "selector_seed']!=11" not in changed


def test_freeze_is_exact_and_not_reusable():
    derived=derive(source());frozen=freeze(derived,'a'*64);ast.parse(frozen)
    assert "FIXED_PLAN_SHA='"+'a'*64+"'" in frozen
    with pytest.raises(ValueError):freeze(frozen,'b'*64)
    with pytest.raises(ValueError):freeze(derived,'short')
    with pytest.raises(ValueError):derive(derived)
