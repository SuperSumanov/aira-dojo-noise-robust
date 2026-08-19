from __future__ import annotations

from phase1.diagnose_prospective_ast_failures import (
    classify_syntax_error,
    combined_surface_cleanup,
    diagnose,
    parses_as_python,
)


def test_fixed_error_categories_and_surface_cleanup() -> None:
    assert classify_syntax_error(SyntaxError("invalid decimal literal")) == "invalid_numeric_literal"
    assert classify_syntax_error(IndentationError("unexpected indent")) == "unexpected_indent"
    code = "```python\n%matplotlib inline\n    value = 1\n```"
    assert not parses_as_python(code)
    assert parses_as_python(combined_surface_cleanup(code))


def test_diagnostic_never_emits_identities_or_code() -> None:
    records = [
        {"run_id": "r1", "task": "t1", "parent": "p1", "code": "value = 1"},
        {"run_id": "r2", "task": "t2", "parent": "p2", "code": "%time value = 1"},
    ]
    receipt = diagnose(records)
    assert receipt["direct_ast"]["failure_endpoints"] == 1
    assert receipt["fixed_surface_recoveries"]["remove_cell_command_lines_only"][
        "recovered_endpoints"
    ] == 1
    serialized = str(receipt)
    assert "r1" not in serialized
    assert "r2" not in serialized
    assert "t1" not in serialized
    assert "t2" not in serialized
    assert "%time value = 1" not in serialized

