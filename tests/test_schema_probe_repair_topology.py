from __future__ import annotations

import pytest

from phase1.build_schema_probe_repair_manifest import validate_topology


def node(
    step: int,
    *,
    code: str,
    is_buggy: bool,
    parents: list[int],
    children: list[int],
    operators: list[str],
) -> dict:
    return {
        "step": step,
        "code": code,
        "is_buggy": is_buggy,
        "parents": parents,
        "children": children,
        "operators_used": operators,
    }


def root(children: list[int]) -> dict:
    return node(0, code="", is_buggy=True, parents=[], children=children, operators=[])


def test_accepts_valid_draft_and_stops() -> None:
    draft = node(1, code="print(1)", is_buggy=False, parents=[0], children=[], operators=["draft", "analysis"])
    mode, code_nodes, selected = validate_topology([root([1]), draft], journal_lines=2, current_step=2)
    assert mode == "draft_valid"
    assert code_nodes == [draft]
    assert selected is draft


@pytest.mark.parametrize("debug_is_buggy", [False, True])
def test_accepts_exactly_one_debug_after_failed_draft(debug_is_buggy: bool) -> None:
    draft = node(1, code="bad", is_buggy=True, parents=[0], children=[2], operators=["draft", "analysis"])
    debug = node(
        2,
        code="fixed",
        is_buggy=debug_is_buggy,
        parents=[1],
        children=[],
        operators=["debug", "analysis"],
    )
    mode, code_nodes, selected = validate_topology(
        [root([1]), draft, debug], journal_lines=3, current_step=3
    )
    assert mode == ("debug_exhausted" if debug_is_buggy else "debug_valid")
    assert code_nodes == [draft, debug]
    assert selected is debug


@pytest.mark.parametrize(
    "nodes,journal_lines,current_step",
    [
        (
            [
                root([1]),
                node(1, code="good", is_buggy=False, parents=[0], children=[2], operators=["draft"]),
                node(2, code="better", is_buggy=False, parents=[1], children=[], operators=["improve"]),
            ],
            3,
            3,
        ),
        (
            [
                root([1]),
                node(1, code="bad", is_buggy=True, parents=[0], children=[2], operators=["draft"]),
                node(2, code="fixed", is_buggy=False, parents=[0], children=[], operators=["debug"]),
            ],
            3,
            3,
        ),
        ([root([1]), node(1, code="bad", is_buggy=True, parents=[0], children=[], operators=["draft"])], 2, 2),
    ],
)
def test_rejects_extra_improve_wrong_parent_or_missing_debug(
    nodes: list[dict], journal_lines: int, current_step: int
) -> None:
    with pytest.raises(RuntimeError):
        validate_topology(nodes, journal_lines=journal_lines, current_step=current_step)
