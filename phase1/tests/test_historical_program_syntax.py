import pytest
from phase1.historical_program_syntax import inspect_syntax


@pytest.mark.parametrize('code', [None, '', 'print(1)', 'raise RuntimeError("never executed")', 'x="中文"'])
def test_parse_compile_without_execution(code):
    v=inspect_syntax(code)
    assert v['ast_parse_ok'] and v['compile_ok'] and not v['program_executed']
    assert v['code_is_none'] == (code is None)


def test_ast_is_not_executability():
    v=inspect_syntax('return 3')
    assert v['ast_parse_ok'] and not v['compile_ok']
    assert len(v['compile_error_sha256']) == 64


def test_invalid_syntax_retained_as_status():
    v=inspect_syntax('if :')
    assert not v['ast_parse_ok'] and not v['compile_ok']


@pytest.mark.parametrize('value', [12, b'print(1)'])
def test_bad_type_fails(value):
    with pytest.raises(ValueError): inspect_syntax(value)


def test_size_cap():
    with pytest.raises(ValueError): inspect_syntax('x'*(2**20+1))
