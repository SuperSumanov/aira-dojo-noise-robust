import numpy as np

from phase1.wl_code_graph_features import (
    aggregate_diagnostics,
    hashed_l2_matrix,
    wl_feature_dict,
)


def test_ast_features_ignore_literal_values_but_preserve_structure() -> None:
    first, first_diag = wl_feature_dict("x = 1\nprint(x)\n")
    second, second_diag = wl_feature_dict("x = 999\nprint(x)\n")
    changed, _ = wl_feature_dict("x = 1\nprint([x])\n")
    assert first_diag.mode == second_diag.mode == "python_ast"
    assert first == second
    assert first != changed


def test_identifier_semantics_are_retained_inside_hashed_labels() -> None:
    first, _ = wl_feature_dict("lightgbm = 1\nprint(lightgbm)\n")
    second, _ = wl_feature_dict("catboost = 1\nprint(catboost)\n")
    assert first != second


def test_invalid_python_uses_token_graph_before_raw_lines() -> None:
    features, diagnostics = wl_feature_dict("if True print(1)\n")
    assert diagnostics.mode == "python_token_sequence_graph"
    assert features


def test_tokenizer_failure_uses_raw_line_graph() -> None:
    features, diagnostics = wl_feature_dict("x = '''unterminated\n")
    assert diagnostics.mode == "raw_line_sequence_graph"
    assert features


def test_node_cap_is_deterministic_and_reported() -> None:
    code = "\n".join(f"x_{index} = {index}" for index in range(50))
    first, first_diag = wl_feature_dict(code, maximum_nodes=8)
    second, second_diag = wl_feature_dict(code, maximum_nodes=8)
    assert first == second
    assert first_diag == second_diag
    assert first_diag.nodes == 8
    assert first_diag.truncated is True


def test_hashed_matrix_is_deterministic_l2_normalized() -> None:
    rows = [wl_feature_dict("x = 1")[0], wl_feature_dict("y = [1]")[0]]
    first = hashed_l2_matrix(rows, n_features=128)
    second = hashed_l2_matrix(rows, n_features=128)
    np.testing.assert_array_equal(first.toarray(), second.toarray())
    np.testing.assert_allclose(np.sqrt(first.multiply(first).sum(axis=1)).A1, [1.0, 1.0])


def test_aggregate_diagnostics_emits_no_code_or_identity() -> None:
    _, first = wl_feature_dict("secret_variable = 1")
    _, second = wl_feature_dict("x = )")
    aggregate = aggregate_diagnostics([first, second])
    assert aggregate["endpoints"] == 2
    assert "secret_variable" not in str(aggregate)
