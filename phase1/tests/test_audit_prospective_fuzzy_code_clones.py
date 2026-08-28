from __future__ import annotations

import itertools
import hashlib
import json
import random
from pathlib import Path

from phase1 import audit_prospective_fuzzy_code_clones as audit
from phase1 import prospective_fuzzy_clone_schema as schema
from phase1 import verify_prospective_fuzzy_code_clones as verifier


def record(
    index: int,
    values: set[int],
    *,
    run: str | None = None,
    task: str = "task-a",
    parent: str | None = None,
) -> audit.FingerprintedRecord:
    return audit.FingerprintedRecord(
        card_id=f"card-{index}",
        run_id=run or f"run-{index}",
        task=task,
        parent=parent if parent is not None else f"parent-{index}",
        shingles=frozenset(values),
    )


def signatures(edges: list[audit.NearEdge]) -> set[tuple[int, int, int, int]]:
    return {
        (edge.left, edge.right, edge.intersection, edge.union) for edge in edges
    }


def test_frozen_thresholds_match_preregistered_literature_scale() -> None:
    assert schema.SHINGLE_SIZE == 5
    assert (
        schema.PRIMARY_JACCARD_NUMERATOR,
        schema.PRIMARY_JACCARD_DENOMINATOR,
    ) == (17, 20)
    assert (
        schema.STRICT_JACCARD_NUMERATOR,
        schema.STRICT_JACCARD_DENOMINATOR,
    ) == (19, 20)
    assert schema.MIN_FINGERPRINT_COVERAGE == 0.99


def test_normalized_shingles_ignore_comments_formatting_and_literals() -> None:
    first = "\n".join(f"value_{i} = {i}" for i in range(40)) + "\n"
    second = "\n\n# comment\n" + "\n".join(
        f"value_{i}= {i + 1000}" for i in range(40)
    )
    renamed = "\n".join(f"other_{i} = {i}" for i in range(40)) + "\n"
    assert audit.token_shingles(first) == audit.token_shingles(second)
    assert audit.token_shingles(first) != audit.token_shingles(renamed)


def test_short_or_unparseable_code_is_not_silently_fingerprinted() -> None:
    assert audit.token_shingles("x = 1\n") is None
    assert audit.token_shingles("def broken(:\n") is None


def test_integer_threshold_is_inclusive_at_exact_boundary() -> None:
    assert audit.threshold_passes(17, 20, 17, 20)
    assert not audit.threshold_passes(16, 20, 17, 20)
    assert audit.threshold_passes(19, 20, 19, 20)


def test_prefix_join_matches_bruteforce_on_exhaustive_small_sets() -> None:
    sets = [
        set(values)
        for size in range(3, 7)
        for values in itertools.combinations(range(7), size)
    ]
    records = [record(index, values) for index, values in enumerate(sets)]
    joined, candidates = audit.exact_threshold_join(records)
    brute = audit.brute_force_edges(records)
    assert signatures(joined) == signatures(brute)
    assert candidates >= len(joined)


def test_prefix_join_matches_bruteforce_on_seeded_varied_lengths() -> None:
    generator = random.Random(20260826)
    records = []
    universe = list(range(250))
    for index in range(80):
        size = generator.randint(20, 120)
        records.append(record(index, set(generator.sample(universe, size))))
    # Inject exact, near-threshold, and length-filtered controls.
    base = set(range(1000, 1100))
    records.extend(
        [
            record(80, base),
            record(81, set(range(1000, 1085))),
            record(82, set(range(1000, 1084))),
            record(83, set(range(1000, 1050))),
        ]
    )
    joined, _ = audit.exact_threshold_join(records)
    brute = audit.brute_force_edges(records)
    assert signatures(joined) == signatures(brute)
    assert any(edge.left == 80 and edge.right == 81 for edge in joined)
    assert not any(edge.left == 80 and edge.right == 82 for edge in joined)
    assert not any(edge.left == 80 and edge.right == 83 for edge in joined)


def test_lineage_relations_are_mutually_exclusive() -> None:
    sibling_a = record(0, set(range(30)), run="run-a", parent="p")
    sibling_b = record(1, set(range(30)), run="run-a", parent="p")
    parent = record(2, set(range(30)), run="run-b", parent="root")
    child = audit.FingerprintedRecord(
        "child", "run-b", "task-a", parent.card_id, frozenset(range(30))
    )
    same_run = record(3, set(range(30)), run="run-c", parent="p1")
    same_run_other = record(4, set(range(30)), run="run-c", parent="p2")
    cross_run_same = record(5, set(range(30)), run="run-d", task="task-a")
    cross_run_other = record(6, set(range(30)), run="run-e", task="task-b")
    assert audit.relation(sibling_a, sibling_b) == "same_parent_siblings"
    assert audit.relation(parent, child) == "parent_child"
    assert audit.relation(same_run, same_run_other) == "same_run_other"
    assert audit.relation(sibling_a, cross_run_same) == "cross_run_same_task"
    assert audit.relation(sibling_a, cross_run_other) == "cross_run_cross_task"


def test_empty_parent_does_not_create_a_false_sibling_relation() -> None:
    left = record(0, set(range(30)), run="run-a", parent="")
    right = record(1, set(range(30)), run="run-a", parent="")
    assert audit.relation(left, right) == "same_run_other"


def test_summary_reports_cross_run_components_without_identity_values() -> None:
    records = [
        record(0, set(range(30)), run="run-a", task="secret-task-a"),
        record(1, set(range(30)), run="run-b", task="secret-task-a"),
        record(2, set(range(30)), run="run-c", task="secret-task-b"),
        record(3, set(range(30)), run="run-d", task="secret-task-c"),
    ]
    edges = [
        audit.NearEdge(0, 1, 30, 30),
        audit.NearEdge(1, 2, 30, 30),
        audit.NearEdge(2, 3, 30, 30),
    ]
    summary = audit.summarize_edges(records, edges)
    assert summary["cross_run_pairs"] == 3
    assert summary["cross_run_affected_endpoints"] == 4
    assert summary["cross_task_affected_endpoints"] == 3
    assert summary["cross_run_components"] == 1
    assert summary["largest_cross_run_component_endpoints"] == 4
    assert summary["largest_cross_run_component_tasks"] == 3
    serialized = json.dumps(summary, sort_keys=True)
    assert "secret-task" not in serialized
    assert "card-" not in serialized
    assert "run-" not in serialized


def test_edge_digest_changes_when_exact_overlap_changes() -> None:
    left = record(0, set(range(30)))
    right = record(1, set(range(30)))
    first = audit.edge_digest(left, right, audit.NearEdge(0, 1, 30, 30))
    second = audit.edge_digest(left, right, audit.NearEdge(0, 1, 29, 31))
    assert first != second
    assert len(first) == 64


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_state(
    tmp_path: Path, programs: list[str] | None = None
) -> tuple[Path, Path]:
    state = tmp_path / "state"
    snapshot = state / "snapshots" / ("a" * 64)
    intake = state / "intakes" / "drop-1"
    base = "\n".join(f"value_{index} = {index}" for index in range(45)) + "\n"
    literal = "\n".join(
        f"value_{index} = {index + 1000}" for index in range(45)
    ) + "\n"
    renamed = "\n".join(f"other_{index} = {index}" for index in range(45)) + "\n"
    rows = []
    selected = programs if programs is not None else [base, renamed, literal, base]
    assert len(selected) == 4
    specifications = [
        ("card-a", "run-a", "task-a", "parent-a", selected[0], "2026-01-01T00:00:00Z"),
        ("card-b", "run-a", "task-a", "parent-b", selected[1], "2026-01-01T00:00:00Z"),
        ("card-c", "run-b", "task-a", "parent-c", selected[2], "2026-01-02T00:00:00Z"),
        ("card-d", "run-c", "task-b", "parent-d", selected[3], "2026-01-03T00:00:00Z"),
    ]
    for card_id, run_id, task, parent, code, started in specifications:
        rows.append(
            {
                "card_id": card_id,
                "task": task,
                "run_id": run_id,
                "code": code,
                "code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "lineage": {
                    "depth": 1,
                    "step": 1,
                    "n_siblings": 1,
                    "op": "Draft",
                    "parent": parent,
                },
                "generation_started_at_utc": started,
                "source_sha256": "b" * 64,
            }
        )
    manifest = intake / "eligible_blind_manifest.jsonl"
    write_jsonl(manifest, rows)
    intake_summary = intake / "summary.json"
    write_json(
        intake_summary,
        {
            "outputs": {"eligible_blind_manifest_sha256": file_sha(manifest)},
            "security": {
                "env_members_read": False,
                "live_event_journal_members_read": False,
                "journal_scanned_before_json": True,
            },
            "blindness": {
                "labels_used_for_run_selection": False,
                "labels_used_for_endpoint_selection": False,
            },
        },
    )
    write_jsonl(
        snapshot / "intake_registry.jsonl",
        [
            {
                "drop_id": "drop-1",
                "intake_dir": str(intake.resolve()),
                "summary_sha256": file_sha(intake_summary),
            }
        ],
    )
    write_jsonl(
        snapshot / "accumulator" / "provisional_runs.jsonl",
        [
            {
                "run_id": "run-a",
                "task": "task-a",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": 2,
                "generation_started_at_utc": "2026-01-01T00:00:00Z",
                "source_sha256": "b" * 64,
            },
            {
                "run_id": "run-b",
                "task": "task-a",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": 1,
                "generation_started_at_utc": "2026-01-02T00:00:00Z",
                "source_sha256": "b" * 64,
            },
            {
                "run_id": "run-c",
                "task": "task-b",
                "drop_id": "drop-1",
                "flow_status": "scoreable",
                "endpoints": 1,
                "generation_started_at_utc": "2026-01-03T00:00:00Z",
                "source_sha256": "b" * 64,
            },
        ],
    )
    write_json(
        snapshot / "accumulator" / "summary.json",
        {
            "inventory": {
                "drops": 1,
                "eligible_runs": 3,
                "eligible_endpoints": 4,
                "provisional_first960_runs": 3,
                "provisional_first960_endpoints": 4,
            },
            "security": {
                "label_vault_opened": False,
                "outcome_files_opened": [],
                "scorer_prediction_files_opened": [],
            },
            "closure": {"provided": False},
        },
    )
    return state, snapshot


def test_independent_verifier_recomputes_real_join_without_importing_producer(
    tmp_path: Path,
) -> None:
    state, snapshot = synthetic_state(tmp_path)
    receipt = audit.audit(state, snapshot, 960, "c" * 40)
    receipt_path = tmp_path / "receipt.json"
    write_json(receipt_path, receipt)
    receipt["_receipt_path"] = str(receipt_path)
    independent = verifier.reproduce(state, snapshot, receipt)
    assert independent["producer_aggregate_matches"] is True
    assert independent["subset_bruteforce_matches"] is True
    assert independent["primary_near_duplicate_pairs"] == 3
    assert receipt["primary_jaccard_0_85"]["cross_run_pairs"] == 3
    assert receipt["primary_jaccard_0_85"]["cross_task_affected_endpoints"] == 3
    assert receipt["pre_registered_gate"]["strong_low_fuzzy_clone_support"] is False


def test_independent_verifier_fails_on_aggregate_tampering(tmp_path: Path) -> None:
    state, snapshot = synthetic_state(tmp_path)
    receipt = audit.audit(state, snapshot, 960, "d" * 40)
    receipt["primary_jaccard_0_85"]["cross_run_pairs"] += 1
    receipt_path = tmp_path / "tampered.json"
    write_json(receipt_path, receipt)
    receipt["_receipt_path"] = str(receipt_path)
    try:
        verifier.reproduce(state, snapshot, receipt)
    except verifier.VerificationError as error:
        assert "primary mismatch" in str(error)
    else:
        raise AssertionError("tampered aggregate was accepted")


def test_verifier_module_does_not_import_authoring_module() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")
    assert "from phase1 import audit_prospective_fuzzy_code_clones" not in source
    assert "import phase1.audit_prospective_fuzzy_code_clones" not in source


def identifier_program(prefix: str, literal_offset: int) -> str:
    return f'''import {prefix}_package as {prefix}_pd
from {prefix}_model import {prefix}_estimator

def {prefix}_fit({prefix}_frame, {prefix}_target):
    {prefix}_data = {prefix}_frame.copy()
    {prefix}_numeric = {prefix}_data.select_dtypes(include=["number"])
    if {prefix}_numeric.empty:
        raise ValueError("missing-{literal_offset}")
    for {prefix}_column in {prefix}_numeric.columns:
        {prefix}_median = {prefix}_numeric[{prefix}_column].median()
        {prefix}_numeric[{prefix}_column] = {prefix}_numeric[{prefix}_column].fillna({prefix}_median)
    try:
        {prefix}_model = {prefix}_estimator(random_state={literal_offset + 7})
        {prefix}_model.fit({prefix}_numeric, {prefix}_target)
    except Exception as {prefix}_error:
        return {{"status": "failed-{literal_offset}", "value": None}}
    {prefix}_scores = []
    while len({prefix}_scores) < {literal_offset + 3}:
        {prefix}_scores.append({prefix}_model.predict({prefix}_numeric))
    return {{"status": "ok-{literal_offset}", "value": {prefix}_scores[-1]}}
'''


def unrelated_identifier_program(prefix: str) -> str:
    return f'''class {prefix}_writer:
    def __enter__(self):
        return self

    def __exit__(self, {prefix}_kind, {prefix}_value, {prefix}_trace):
        return False

    async def {prefix}_emit(self, {prefix}_items):
        async for {prefix}_item in {prefix}_items:
            match {prefix}_item:
                case {{"kind": "alpha", "payload": {prefix}_payload}}:
                    yield tuple(reversed({prefix}_payload))
                case [*{prefix}_prefix, {prefix}_last]:
                    yield ({prefix}_last, {prefix}_prefix)
                case _:
                    continue
'''


def test_identifier_erasure_matches_alpha_renaming_and_literal_changes() -> None:
    first = identifier_program("alpha", 0)
    second = identifier_program("omega", 100)
    assert audit.token_shingles(first) != audit.token_shingles(second)
    assert audit.identifier_erased_token_shingles(first) == (
        audit.identifier_erased_token_shingles(second)
    )
    assert audit.identifier_erased_token_shingles(first) == (
        verifier.identifier_erased_shingles(first)
    )
    assert audit.identifier_erased_token_shingles(first) != (
        audit.identifier_erased_token_shingles(unrelated_identifier_program("zeta"))
    )


def test_identifier_erased_mode_is_independently_reproduced_end_to_end(
    tmp_path: Path,
) -> None:
    programs = [
        identifier_program("alpha", 0),
        identifier_program("beta", 10),
        identifier_program("gamma", 20),
        unrelated_identifier_program("delta"),
    ]
    state, snapshot = synthetic_state(tmp_path, programs)
    receipt = audit.audit(
        state,
        snapshot,
        960,
        "e" * 40,
        schema.IDENTIFIER_ERASED_REPRESENTATION,
    )
    receipt_path = tmp_path / "identifier-receipt.json"
    write_json(receipt_path, receipt)
    receipt["_receipt_path"] = str(receipt_path)
    independent = verifier.reproduce(state, snapshot, receipt)
    assert receipt["protocol"] == schema.IDENTIFIER_ERASED_PROTOCOL
    assert receipt["fingerprinting"]["fingerprinted_endpoints"] == 4
    assert receipt["primary_jaccard_0_85"]["near_duplicate_pairs"] == 3
    assert receipt["primary_jaccard_0_85"]["cross_run_pairs"] == 2
    assert receipt["pre_registered_gate"]["strict_lineage_local_support"] is False
    assert independent["representation"] == schema.IDENTIFIER_ERASED_REPRESENTATION
    assert independent["producer_aggregate_matches"] is True
