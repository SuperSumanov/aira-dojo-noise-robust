from __future__ import annotations

import hashlib
import itertools
import json
import random
from pathlib import Path

import pytest

from phase1 import audit_historical_train_future_fuzzy_overlap as audit
from phase1 import historical_train_future_overlap_schema as schema
from phase1 import prospective_fuzzy_clone_schema as fuzzy_schema
from phase1 import verify_historical_train_future_fuzzy_overlap as verifier


def producer_record(
    index: int,
    values: set[int],
    *,
    task: str = "task-a",
    run: str | None = None,
) -> audit.Record:
    return audit.Record(
        card_id=f"private-card-{index}",
        run_id=run or f"private-run-{index}",
        task=task,
        shingles=frozenset(values),
    )


def edge_rows(edges: list[audit.Edge]) -> set[tuple[int, int, int, int]]:
    return {
        (edge.historical, edge.prospective, edge.intersection, edge.union)
        for edge in edges
    }


def verifier_record(record: audit.Record) -> verifier.Record:
    return verifier.Record(
        record.card_id, record.run_id, record.task, record.shingles
    )


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preregistered_thresholds_and_reused_dependency_match() -> None:
    assert (schema.SHINGLE_SIZE, schema.SHINGLE_HASH_BITS) == (5, 128)
    assert schema.MIN_DISTINCT_SHINGLES == 20
    assert (schema.PRIMARY_NUMERATOR, schema.PRIMARY_DENOMINATOR) == (17, 20)
    assert (schema.STRICT_NUMERATOR, schema.STRICT_DENOMINATOR) == (19, 20)
    assert fuzzy_schema.SHINGLE_SIZE == schema.SHINGLE_SIZE
    audit.require_dependency_contract()
    verifier.require_dependency_contract()


def test_dependency_contract_fails_closed_on_parameter_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schema, "SHINGLE_SIZE", schema.SHINGLE_SIZE + 1)
    with pytest.raises(audit.OverlapAuditError, match="contract drift"):
        audit.require_dependency_contract()
    with pytest.raises(verifier.VerificationError, match="contract drift"):
        verifier.require_dependency_contract()


def test_integer_threshold_is_inclusive_only_at_exact_boundary() -> None:
    assert audit.fuzzy.threshold_passes(17, 20, 17, 20)
    assert not audit.fuzzy.threshold_passes(16, 20, 17, 20)
    assert audit.fuzzy.threshold_passes(19, 20, 19, 20)


def test_bipartite_prefix_join_matches_exhaustive_small_bruteforce() -> None:
    sets = [
        set(values)
        for size in range(3, 7)
        for values in itertools.combinations(range(7), size)
    ]
    historical = [producer_record(index, values) for index, values in enumerate(sets[::2])]
    prospective = [
        producer_record(1000 + index, values)
        for index, values in enumerate(sets[1::2])
    ]
    joined, candidates = audit.bipartite_join(historical, prospective)
    brute = audit.brute_force(historical, prospective)
    assert edge_rows(joined) == edge_rows(brute)
    assert candidates >= len(joined)


def test_bipartite_prefix_join_matches_seeded_varied_lengths() -> None:
    generator = random.Random(20260826)
    universe = list(range(400))
    historical = [
        producer_record(index, set(generator.sample(universe, generator.randint(20, 160))))
        for index in range(50)
    ]
    prospective = [
        producer_record(100 + index, set(generator.sample(universe, generator.randint(20, 160))))
        for index in range(50)
    ]
    base = set(range(1000, 1100))
    historical.append(producer_record(999, base))
    prospective.extend(
        [
            producer_record(1000, set(range(1000, 1085))),
            producer_record(1001, set(range(1000, 1084))),
            producer_record(1002, set(range(1000, 1050))),
        ]
    )
    joined, _ = audit.bipartite_join(historical, prospective)
    brute = audit.brute_force(historical, prospective)
    assert edge_rows(joined) == edge_rows(brute)
    control = len(historical) - 1
    assert any(edge.historical == control and edge.prospective == 50 for edge in joined)
    assert not any(edge.historical == control and edge.prospective == 51 for edge in joined)
    assert not any(edge.historical == control and edge.prospective == 52 for edge in joined)


def test_independent_join_agrees_with_producer_and_bruteforce() -> None:
    historical = [
        producer_record(0, set(range(100))),
        producer_record(1, set(range(200, 260))),
    ]
    prospective = [
        producer_record(2, set(range(85))),
        producer_record(3, set(range(200, 260))),
        producer_record(4, set(range(500, 560))),
    ]
    producer_edges, producer_candidates = audit.bipartite_join(historical, prospective)
    independent_edges, independent_candidates = verifier.independent_join(
        [verifier_record(row) for row in historical],
        [verifier_record(row) for row in prospective],
    )
    assert producer_candidates == independent_candidates
    assert edge_rows(producer_edges) == {
        (edge.historical, edge.prospective, edge.intersection, edge.union)
        for edge in independent_edges
    }
    assert verifier.edge_signature(independent_edges) == verifier.edge_signature(
        verifier.brute_force(
            [verifier_record(row) for row in historical],
            [verifier_record(row) for row in prospective],
        )
    )


def test_aggregate_separates_same_and_cross_task_and_hides_identities() -> None:
    historical = [
        producer_record(0, set(range(30)), task="secret-task-a"),
        producer_record(1, set(range(30)), task="secret-task-b"),
    ]
    prospective = [
        producer_record(2, set(range(30)), task="secret-task-a"),
        producer_record(3, set(range(30)), task="secret-task-c"),
    ]
    edges = [audit.Edge(0, 0, 30, 30), audit.Edge(1, 1, 30, 30)]
    result = audit.aggregate(historical, prospective, edges)
    assert result["same_task_pairs"] == 1
    assert result["cross_task_pairs"] == 1
    assert result["historical_affected_endpoints"] == 2
    assert result["prospective_affected_endpoints"] == 2
    assert result["components"] == 2
    serialized = json.dumps(result, sort_keys=True)
    assert "secret-task" not in serialized
    assert "private-card" not in serialized
    assert "private-run" not in serialized


def test_independent_aggregate_matches_producer() -> None:
    historical = [
        producer_record(0, set(range(30)), task="a"),
        producer_record(1, set(range(30)), task="b"),
    ]
    prospective = [
        producer_record(2, set(range(30)), task="a"),
        producer_record(3, set(range(30)), task="c"),
    ]
    edges = [audit.Edge(0, 0, 30, 30), audit.Edge(1, 1, 30, 30)]
    independent = [verifier.Edge(0, 0, 30, 30), verifier.Edge(1, 1, 30, 30)]
    assert audit.aggregate(historical, prospective, edges) == verifier.aggregate(
        [verifier_record(row) for row in historical],
        [verifier_record(row) for row in prospective],
        independent,
    )


def test_large_multitask_component_gate_is_detected() -> None:
    historical = [
        producer_record(index, set(range(30)), task=f"task-{index % 3}")
        for index in range(5)
    ]
    prospective = [
        producer_record(100 + index, set(range(30)), task=f"task-{(index + 1) % 3}")
        for index in range(5)
    ]
    edges = [audit.Edge(index, index, 30, 30) for index in range(5)]
    edges.extend(audit.Edge(index, (index + 1) % 5, 30, 30) for index in range(5))
    result = audit.aggregate(historical, prospective, edges)
    assert result["largest_component_endpoints"] == 10
    assert result["largest_component_tasks"] == 3
    assert result["large_multitask_components"] == 1


def historical_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mismatch: bool = False
) -> Path:
    repo = tmp_path / "repo"
    pair_path = repo / "pairs.jsonl"
    pair_rows = [
        {
            "better": "card-a",
            "worse": "card-b",
            "run_id": "run-old",
            "task": "task-old",
            "parent": "parent-old",
            "label": "must-not-be-used",
            "observation": {"private": 1},
        }
    ]
    write_jsonl(pair_path, pair_rows)
    cards_path = repo / "cards.jsonl"
    write_jsonl(
        cards_path,
        [
            {
                "id": "card-a",
                "run_id": "run-wrong" if mismatch else "run-old",
                "task": {"name": "task-old"},
                "code": "\n".join(f"x_{i}={i}" for i in range(30)),
                "value": 0.99,
            },
            {
                "id": "card-b",
                "run_id": "run-old",
                "task": {"name": "task-old"},
                "code": "\n".join(f"y_{i}={i}" for i in range(30)),
                "value": 0.01,
            },
        ],
    )
    monkeypatch.setattr(
        schema,
        "HISTORICAL_PAIR_FILES",
        (("pairs.jsonl", audit.normalized_lf_sha256(pair_path), 1),),
    )
    monkeypatch.setattr(schema, "HISTORICAL_CARDS_PATH", "cards.jsonl")
    monkeypatch.setattr(schema, "HISTORICAL_CARDS_SHA256", sha256(cards_path))
    monkeypatch.setattr(schema, "HISTORICAL_UNION_ROWS", 1)
    monkeypatch.setattr(schema, "HISTORICAL_UNION_ENDPOINTS", 2)
    monkeypatch.setattr(schema, "HISTORICAL_UNION_RUNS", 1)
    monkeypatch.setattr(schema, "HISTORICAL_UNION_TASKS", 1)
    monkeypatch.setattr(schema, "HISTORICAL_UNION_PARENTS", 1)
    return repo


def test_historical_loader_uses_identity_and_code_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = historical_fixture(tmp_path, monkeypatch)
    records, summary = audit.load_historical_train(repo)
    assert len(records) == 2
    assert summary["union_endpoints"] == 2
    assert summary["historical_label_or_observation_fields_used"] is False
    assert "must-not-be-used" not in json.dumps(summary)


def test_historical_loader_rejects_pair_card_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = historical_fixture(tmp_path, monkeypatch, mismatch=True)
    with pytest.raises(audit.OverlapAuditError, match="identity mismatch"):
        audit.load_historical_train(repo)


def test_audit_rejects_empty_fingerprinted_side(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty_code = [audit.fuzzy.CodeRecord("old", "run-old", "task", "", "x=1")]
    future_code = [audit.fuzzy.CodeRecord("new", "run-new", "task", "", "y=2")]
    monkeypatch.setattr(audit, "load_historical_train", lambda _: (empty_code, {}))
    monkeypatch.setattr(audit.fuzzy, "load_cohort", lambda *_: (future_code, {}))
    with pytest.raises(audit.OverlapAuditError, match="empty fingerprinted side"):
        audit.audit(tmp_path, tmp_path, tmp_path / ("a" * 64), "deadbeef")


def test_independent_verifier_does_not_import_new_producer() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "from phase1 import audit_historical_train_future_fuzzy_overlap" not in source
    assert "imports_new_producer_code\": False" in source


def test_atomic_output_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    audit.atomic_json(path, {"first": True})
    with pytest.raises(audit.OverlapAuditError, match="output exists"):
        audit.atomic_json(path, {"second": True})
    assert json.loads(path.read_text(encoding="utf-8")) == {"first": True}
