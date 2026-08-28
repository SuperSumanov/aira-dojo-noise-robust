from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PRODUCER = REPO / "phase1" / "audit_decision_corpus_lineage_v2.py"
VERIFIER = REPO / "phase1" / "verify_decision_corpus_lineage_v2.py"
TEMPLATE = REPO / "phase1" / "decision_corpus_lineage_audit_v2.json"
SET_NAMES = (
    "extension:b0",
    "extension:b1",
    "extension:b2",
    "frozen:b0",
    "frozen:b1",
    "frozen:b2",
    "train:b0",
    "train:b1",
    "train:b2",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values), encoding="utf-8")


def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(raw).hexdigest()


def build_fixture(tmp_path: Path, mutation: str | None = None) -> tuple[Path, str, Path]:
    cards: list[dict[str, object]] = []
    rows_by_set: dict[str, list[dict[str, object]]] = {}
    target = "frozen:b0"
    for index, name in enumerate(SET_NAMES):
        partition, budget_text = name.split(":b")
        budget = int(budget_text)
        stem = name.replace(":", "_")
        task, run = f"task_{stem}", f"run_{stem}"
        parent, left, right = f"parent_{stem}", f"left_{stem}", f"right_{stem}"
        parent_for_lineage = parent
        parent_run = run
        endpoint_runs = (run, run)
        include_parent = True
        declared_parent = parent
        if name == target and mutation == "orphan":
            include_parent = False
        elif name == target and mutation == "same_run_non_sibling":
            declared_parent = f"alternate_{stem}"
            cards.append({"id": declared_parent, "task": task, "run_id": run, "lineage": {"parent_id": None}})
        elif name == target and mutation == "cross_run":
            endpoint_runs = (run, f"run_other_{stem}")
        elif name == target and mutation == "visible_parent_cross_run":
            parent_run = f"run_parent_other_{stem}"
        if include_parent:
            cards.append({"id": parent, "task": task, "run_id": parent_run, "lineage": {"parent_id": None}})
        cards.extend(
            [
                {"id": left, "task": task, "run_id": endpoint_runs[0], "lineage": {"parent_id": parent_for_lineage}},
                {"id": right, "task": task, "run_id": endpoint_runs[1], "lineage": {"parent_id": parent_for_lineage}},
            ]
        )
        row: dict[str, object] = {
            "better": left,
            "worse": right,
            "parent": declared_parent,
            "task": task,
            "budget": budget,
            "intask_split": "train" if partition == "train" else "test",
        }
        if name == target and mutation == "outcome_fields":
            row.update({"better_score": 0.9, "worse_score": 0.1, "prediction": "left"})
        elif name == target and mutation == "row_metadata_mismatch":
            row.update({
                "task": f"declared_task_other_{stem}",
                "budget": budget + 10,
                "intask_split": "train",
                "run_id": f"declared_run_other_{stem}",
            })
        if endpoint_runs[0] == endpoint_runs[1]:
            row["run_id"] = endpoint_runs[0]
        if name == target and mutation == "row_metadata_mismatch":
            row["run_id"] = f"declared_run_other_{stem}"
        rows = [row]
        if name == target and mutation == "duplicate_reverse":
            reverse = dict(row)
            reverse["better"], reverse["worse"] = row["worse"], row["better"]
            rows.append(reverse)
        rows_by_set[name] = rows

    if mutation == "split_overlap":
        source = dict(rows_by_set["train:b0"][0])
        source["intask_split"] = "test"
        rows_by_set[target] = [source]

    cards_path = tmp_path / "cards.jsonl"
    write_jsonl(cards_path, cards)
    run_map = {str(card["id"]): str(card["run_id"]) for card in cards}
    run_map_path = tmp_path / "run_map.json"
    write_json(run_map_path, run_map)

    v1_card_path = tmp_path / "v1_card.json"
    write_json(v1_card_path, {"status": "VERIFIED_DECISION_CORPUS_AUDIT"})
    v1_verification_path = tmp_path / "v1_verification.json"
    write_json(
        v1_verification_path,
        {
            "status": "INDEPENDENTLY_VERIFIED_DECISION_CORPUS_AUDIT",
            "source_card": {"sha256_normalized_lf": digest(v1_card_path)},
            "verified_same_budget_isolation": {
                f"b{budget}": {"pairs": 0, "endpoints": 0, "parents": 0, "runs": 0, "passed": True}
                for budget in range(3)
            },
        },
    )

    protocol = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    protocol["immutable_inputs"]["cards"] = {
        "path": cards_path.name,
        "sha256": digest(cards_path),
        "rows": len(cards),
    }
    protocol["immutable_inputs"]["run_map"] = {
        "path": run_map_path.name,
        "sha256": digest(run_map_path),
        "entries": len(run_map),
    }
    protocol["immutable_inputs"]["v1_audit_card"] = {
        "path": v1_card_path.name,
        "sha256": digest(v1_card_path),
    }
    protocol["immutable_inputs"]["v1_independent_verification"] = {
        "path": v1_verification_path.name,
        "sha256": digest(v1_verification_path),
    }
    pair_metadata: dict[str, dict[str, object]] = {}
    known: dict[str, dict[str, int]] = {}
    card_by_id = {str(card["id"]): card for card in cards}
    for name, rows in rows_by_set.items():
        path = tmp_path / f"{name.replace(':', '_')}.jsonl"
        write_jsonl(path, rows)
        partition, budget_text = name.split(":b")
        pair_metadata[name] = {
            "path": path.name,
            "sha256": digest(path),
            "partition": partition,
            "budget": int(budget_text),
            "rows": len(rows),
        }
        endpoints = {str(row[key]) for row in rows for key in ("better", "worse")}
        parents = {str(row["parent"]) for row in rows}
        runs = {str(card_by_id[endpoint]["run_id"]) for endpoint in endpoints}
        tasks = {str(row["task"]) for row in rows}
        known[name] = {
            "pairs": len(rows),
            "parents": len(parents),
            "endpoints": len(endpoints),
            "runs": len(runs),
            "tasks": len(tasks),
            "mapped_parent_choice_sets": sum(parent in card_by_id for parent in parents),
        }
    protocol["immutable_inputs"]["pair_sets"] = pair_metadata
    protocol["known_before_freeze"]["set_summaries"] = known
    protocol["support_gates"].update(
        {
            "minimum_strict_core_pair_retention": "1/1",
            "minimum_strict_core_task_retention": "1/1",
            "minimum_strict_core_run_retention": "1/1",
            "minimum_strict_core_endpoint_retention": "1/1",
            "maximum_single_task_pair_share": "1/1",
            "maximum_single_run_pair_share": "1/1",
        }
    )
    protocol_path = tmp_path / "protocol.json"
    write_json(protocol_path, protocol)
    return protocol_path, digest(protocol_path), tmp_path / "producer.json"


def execute(tmp_path: Path, mutation: str | None = None) -> tuple[dict[str, object], Path, Path, str]:
    protocol, protocol_hash, producer_output = build_fixture(tmp_path, mutation)
    subprocess.run(
        [
            sys.executable,
            str(PRODUCER),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            protocol_hash,
            "--root",
            str(tmp_path),
            "--source-commit",
            "a" * 40,
            "--output",
            str(producer_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    verification = tmp_path / "verification.json"
    subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            protocol_hash,
            "--root",
            str(tmp_path),
            "--producer-result",
            str(producer_output),
            "--producer-script",
            str(PRODUCER),
            "--output",
            str(verification),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(producer_output.read_text()), producer_output, verification, protocol_hash


def test_all_parent_present_direct_rows_receive_strongest_classification(tmp_path: Path) -> None:
    result, _producer, verification, _hash = execute(tmp_path)
    assert result["classification"] == "HISTORICAL_V11_FULL_PARENT_CLOSED_DIRECT_SIBLING_CORPUS"
    assert result["scientific"]["hard_integrity_gate_count"] == {"passed": 15, "total": 15}
    assert json.loads(verification.read_text())["all_aggregate_fields_equal"] is True


def test_orphan_parent_is_separate_lineage_verified_tier(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "orphan")
    profile = result["scientific"]["set_profiles"]["frozen:b0"]
    assert profile["relation_counts"]["lineage_verified_orphan_parent_sibling"] == 1
    assert profile["strict_core"]["pairs"] == 0
    assert result["classification"] == "HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT"


def test_wrong_declared_parent_is_same_run_non_sibling(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "same_run_non_sibling")
    counts = result["scientific"]["set_profiles"]["frozen:b0"]["relation_counts"]
    assert counts["same_run_declared_context_non_sibling"] == 1


def test_cross_run_context_is_not_promoted_to_sibling(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "cross_run")
    counts = result["scientific"]["set_profiles"]["frozen:b0"]["relation_counts"]
    assert counts["cross_run_declared_context"] == 1


def test_visible_declared_parent_in_other_run_is_cross_run_context(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "visible_parent_cross_run")
    counts = result["scientific"]["set_profiles"]["frozen:b0"]["relation_counts"]
    assert counts["cross_run_declared_context"] == 1
    assert counts["same_run_declared_context_non_sibling"] == 0


def test_duplicate_or_reverse_pair_fails_integrity_classification(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "duplicate_reverse")
    assert result["classification"] == "HISTORICAL_V11_LINEAGE_AUDIT_INTEGRITY_GATE_FAIL"
    assert result["scientific"]["hard_integrity_gates"]["within_set_unordered_duplicates_and_orientation_conflicts_zero"] is False


def test_same_budget_train_frozen_overlap_fails_closed(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "split_overlap")
    gates = result["scientific"]["hard_integrity_gates"]
    assert result["classification"] == "HISTORICAL_V11_LINEAGE_AUDIT_INTEGRITY_GATE_FAIL"
    assert gates["same_budget_strict_core_train_frozen_pair_overlap_zero"] is False
    assert gates["same_budget_strict_core_train_frozen_endpoint_overlap_zero"] is False
    assert gates["same_budget_strict_core_train_frozen_parent_overlap_zero"] is False
    assert gates["same_budget_strict_core_train_frozen_referenced_run_overlap_zero"] is False


def test_row_metadata_mismatches_emit_aggregate_failure_receipt(tmp_path: Path) -> None:
    result, *_ = execute(tmp_path, "row_metadata_mismatch")
    profile = result["scientific"]["set_profiles"]["frozen:b0"]["all_rows"]
    violations = profile["row_context_violation_counts"]
    assert result["classification"] == "HISTORICAL_V11_LINEAGE_AUDIT_INTEGRITY_GATE_FAIL"
    assert result["scientific"]["hard_integrity_gates"]["all_pair_endpoints_known_and_row_task_run_split_budget_consistent"] is False
    assert violations == {
        "endpoint_card_task_disagreement": 0,
        "row_task_mismatch": 1,
        "budget_mismatch": 1,
        "split_mismatch": 1,
        "declared_run_mismatch": 1,
    }


def test_outcome_like_extra_fields_do_not_change_scientific_aggregates(tmp_path: Path) -> None:
    baseline, *_ = execute(tmp_path / "baseline")
    injected, *_ = execute(tmp_path / "injected", "outcome_fields")
    assert baseline["scientific"] == injected["scientific"]
    assert injected["scope"]["grade_gap_label_prediction_accuracy_or_utility_used"] is False


def test_independent_verifier_rejects_tampered_aggregate(tmp_path: Path) -> None:
    result, producer, _verification, protocol_hash = execute(tmp_path)
    result["scientific"]["set_profiles"]["frozen:b0"]["strict_core"]["pairs"] += 1
    write_json(producer, result)
    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--protocol",
            str(tmp_path / "protocol.json"),
            "--protocol-sha256",
            protocol_hash,
            "--root",
            str(tmp_path),
            "--producer-result",
            str(producer),
            "--producer-script",
            str(PRODUCER),
            "--output",
            str(tmp_path / "tampered-verification.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0


def test_protocol_hash_drift_fails_closed(tmp_path: Path) -> None:
    protocol, protocol_hash, producer = build_fixture(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(PRODUCER),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            "0" * 64 if protocol_hash != "0" * 64 else "1" * 64,
            "--root",
            str(tmp_path),
            "--source-commit",
            "a" * 40,
            "--output",
            str(producer),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0


def test_aggregate_receipt_contains_no_card_or_run_identity(tmp_path: Path) -> None:
    result, producer, *_ = execute(tmp_path)
    serialized = producer.read_text()
    assert "left_frozen_b0" not in serialized
    assert "run_frozen_b0" not in serialized
    assert result["scope"]["row_level_release_created"] is False
