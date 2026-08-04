import pytest

from dojo.core.solvers.operators.core import execute_op_plan_code
from dojo.core.solvers.utils.response import parse_thinking_tags


def test_execute_op_plan_code_retries_none_response():
    responses = iter(
        [
            (None, {"attempt": 1}),
            ("Plan\n```python\nprint('ok')\n```", {"attempt": 2}),
        ]
    )

    plan, code, metrics = execute_op_plan_code(lambda: next(responses), max_operator_tries=2)

    assert plan == "Plan"
    assert code == 'print("ok")\n'
    assert metrics == {"attempt": 2}


def test_execute_op_plan_code_exhausts_empty_responses():
    calls = 0

    def operator():
        nonlocal calls
        calls += 1
        return None, {"attempt": calls}

    plan, code, metrics = execute_op_plan_code(operator, max_operator_tries=3)

    assert calls == 3
    assert plan == ""
    assert code == ""
    assert metrics == {"attempt": 3}


def test_parse_thinking_tags_rejects_non_text_response():
    with pytest.raises(TypeError, match="Expected LLM response text, got NoneType"):
        parse_thinking_tags(None)
