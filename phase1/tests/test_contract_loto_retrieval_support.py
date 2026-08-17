from __future__ import annotations

from phase1.contract_loto_retrieval_support import fingerprint, mean_type_credit, nearest_graph


def row(task: str, task_type: str, columns: int, rows: int, observed: list[list[str]]) -> dict:
    return {
        "task": task,
        "task_type": task_type,
        "column_count": columns,
        "row_count": rows,
        "observed_types": observed,
        "empty_value_counts": [0] * columns,
    }


def test_fingerprint_ignores_task_and_column_names() -> None:
    first = row("task-a", "nlp", 2, 100, [["string"], ["float"]])
    first["columns"] = ["id", "target"]
    second = row("renamed", "image-cls", 2, 100, [["string"], ["float"]])
    second["columns"] = ["completely", "different"]
    assert fingerprint(first) == fingerprint(second)


def test_nearest_graph_excludes_query_and_preserves_exact_ties() -> None:
    tasks = [
        row("a", "nlp", 2, 100, [["string"], ["float"]]),
        row("b", "nlp", 2, 100, [["string"], ["float"]]),
        row("c", "image-cls", 2, 100, [["string"], ["float"]]),
    ]
    graph = nearest_graph(tasks)
    assert graph[0] == [1, 2]
    assert 0 not in graph[0]
    assert mean_type_credit(graph, [item["task_type"] for item in tasks]) == 1 / 3
