from __future__ import annotations

import json

from phase1.audit_archive_task_identity import identity_cardinality


def blob(identities: list[str | None]) -> bytes:
    rows = []
    for step, identity in enumerate(identities):
        metric = {} if identity is None else {"competition_id": identity}
        rows.append(json.dumps({"step": step, "metric_info": metric}))
    return ("\n".join(rows) + "\n").encode("utf-8")


def test_identity_cardinality_does_not_emit_values() -> None:
    assert identity_cardinality(blob([None, None])) == (2, 0)
    assert identity_cardinality(blob(["task-a", "task-a"])) == (2, 1)
    assert identity_cardinality(blob(["task-a", "task-b"])) == (2, 2)
