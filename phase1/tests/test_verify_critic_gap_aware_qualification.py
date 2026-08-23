from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

pytest.importorskip("scipy")
pytest.importorskip("sklearn")

from phase1 import critic_gap_aware_qualification as producer
from phase1 import verify_critic_gap_aware_qualification as verifier


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "phase1" / "critic_gap_aware_qualification_v1.json"
VERIFIER_SOURCE = ROOT / "phase1" / "verify_critic_gap_aware_qualification.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(verifier.compact(row) + "\n")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pair_row(
    task: str,
    parent: str,
    better: str,
    worse: str,
    gap: float,
    component_seed: str,
    split: str = "train",
) -> dict[str, Any]:
    return {
        "task": task,
        "parent": parent,
        "better": better,
        "worse": worse,
        "gap_raw": gap,
        "pair_component_id": hashlib.sha256(component_seed.encode("utf-8")).hexdigest(),
        "intask_split": split,
        "outer_intask_split": "train",
        "train_dev_protocol": "pair-graph-component-train-dev-split-v1",
        "train_dev_seed": 20260821,
        "train_dev_target_numerator": 1,
        "train_dev_target_denominator": 10,
        "src": "decision",
    }


def card(card_id: str, task: str, code: str) -> dict[str, Any]:
    return {
        "id": card_id,
        "code": code,
        "task": {"name": task},
        "client": "synthetic-client",
        "hardware": "synthetic-hardware",
        "time_limit": 300,
        "execution_timeout": 300,
    }


def source_receipt(path: Path, *, rows: int | None = None) -> dict[str, Any]:
    output: dict[str, Any] = {"sha256": digest(path), "bytes": path.stat().st_size}
    if rows is not None:
        output["rows"] = rows
    return output


def write_artifact_bundle(bundle: Path, expected: dict[str, Any]) -> None:
    bundle.mkdir()
    (bundle / "summary.json").write_bytes(verifier.canonical_bytes(expected["summary"]))
    write_csv(bundle / "arm_metrics.csv", verifier.ARM_FIELDS, expected["arm_rows"])
    write_csv(bundle / "task_metrics.csv", verifier.TASK_FIELDS, expected["task_rows"])
    write_csv(bundle / "task_scales.csv", verifier.SCALE_FIELDS, expected["scale_rows"])
    write_jsonl(bundle / "per_pair.jsonl", expected["pair_rows"])
    manifest = {
        "protocol": verifier.PROTOCOL,
        "files": {
            name: source_receipt(bundle / name)
            for name in sorted(verifier.MANIFESTED_FILES)
        },
    }
    (bundle / "artifact_manifest.json").write_bytes(verifier.canonical_bytes(manifest))


def refresh_manifest(bundle: Path, name: str) -> None:
    manifest_path = bundle / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][name] = source_receipt(bundle / name)
    manifest_path.write_bytes(verifier.canonical_bytes(manifest))


def synthetic_case(root: Path) -> dict[str, Any]:
    train_rows: list[dict[str, Any]] = []
    dev_rows: list[dict[str, Any]] = []
    grouped_cards: dict[str, list[dict[str, Any]]] = {}
    for task_index in range(20):
        task = f"task-{task_index:02d}"
        for pair_index, gap in enumerate((1.0, 2.0, 3.0, 4.0)):
            better = f"train-{task_index:02d}-{pair_index:02d}-better"
            worse = f"train-{task_index:02d}-{pair_index:02d}-worse"
            run_id = f"train-run-{task_index:02d}-{pair_index:02d}"
            grouped_cards[run_id] = [
                card(
                    better,
                    task,
                    f"def solve(): return 'shared quality better signal {task} train {pair_index}'",
                ),
                card(
                    worse,
                    task,
                    f"def solve(): return 'shared quality worse signal {task} train {pair_index}'",
                ),
            ]
            train_rows.append(
                pair_row(
                    task,
                    f"train-parent-{task_index:02d}-{pair_index:02d}",
                    better,
                    worse,
                    gap,
                    f"train-component-{task_index}-{pair_index}",
                )
            )
        for pair_index in range(10):
            better = f"dev-{task_index:02d}-{pair_index:02d}-better"
            worse = f"dev-{task_index:02d}-{pair_index:02d}-worse"
            run_id = f"dev-run-{task_index:02d}-{pair_index:02d}"
            grouped_cards[run_id] = [
                card(
                    better,
                    task,
                    f"def solve(): return 'shared quality better signal {task} dev {pair_index}'",
                ),
                card(
                    worse,
                    task,
                    f"def solve(): return 'shared quality worse signal {task} dev {pair_index}'",
                ),
            ]
            dev_rows.append(
                pair_row(
                    task,
                    f"dev-parent-{task_index:02d}-{pair_index:02d}",
                    better,
                    worse,
                    float(1 + (pair_index % 4)),
                    f"dev-component-{task_index}-{pair_index}",
                    split="dev",
                )
            )

    cards_path = root / "cards.json"
    train_path = root / "train.jsonl"
    dev_path = root / "dev.jsonl"
    cards_path.write_bytes(verifier.canonical_bytes(grouped_cards))
    write_jsonl(train_path, train_rows)
    write_jsonl(dev_path, dev_rows)
    source = {
        "cards": source_receipt(cards_path),
        "train": source_receipt(train_path, rows=len(train_rows)),
        "dev": source_receipt(dev_path, rows=len(dev_rows)),
    }
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for role in ("cards", "train", "dev"):
        contract["inputs"][role].update(source[role])
    contract_path = root / "contract.json"
    contract_path.write_bytes(verifier.canonical_bytes(contract))
    contract_sha256 = digest(contract_path)
    expected = verifier.reconstruct_expected_bundle(
        cards_path,
        train_path,
        dev_path,
        contract_path,
        expected_contract_sha256=contract_sha256,
        source=source,
    )
    bundle = root / "bundle"
    write_artifact_bundle(bundle, expected)
    return {
        "cards": cards_path,
        "train": train_path,
        "dev": dev_path,
        "contract": contract_path,
        "contract_sha256": contract_sha256,
        "source": source,
        "expected": expected,
        "bundle": bundle,
        "train_rows": train_rows,
        "dev_rows": dev_rows,
    }


@pytest.fixture(scope="module")
def case(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    return synthetic_case(tmp_path_factory.mktemp("gap-aware-verifier"))


def copied_bundle(case: dict[str, Any], target: Path) -> Path:
    bundle = target / "bundle"
    shutil.copytree(case["bundle"], bundle)
    return bundle


def validate_copy(case: dict[str, Any], bundle: Path) -> dict[str, Any]:
    return verifier.validate_output_bundle(bundle, case["expected"])


def test_contract_hash_independence_and_fixed_cli_surface() -> None:
    assert digest(CONTRACT) == verifier.CONTRACT_SHA256
    source = VERIFIER_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(name.endswith("critic_gap_aware_qualification") for name in imported)

    parser = verifier.build_parser()
    positional = [
        action.dest
        for action in parser._actions
        if action.option_strings == [] and action.dest != argparse.SUPPRESS
    ]
    assert positional == ["cards", "train", "dev", "artifact_dir", "verification_output"]
    optional = {option for action in parser._actions for option in action.option_strings}
    assert optional == {"-h", "--help", "--contract"}
    args = parser.parse_args(
        ["CARDS", "TRAIN", "DEV", "BUNDLE", "OUTPUT_JSON", "--contract", "CONTRACT"]
    )
    assert args.cards == Path("CARDS")
    assert args.artifact_dir == Path("BUNDLE")
    assert args.verification_output == Path("OUTPUT_JSON")
    assert args.contract == Path("CONTRACT")
    with pytest.raises(SystemExit):
        parser.parse_args(["CARDS", "TRAIN", "DEV", "BUNDLE", "OUTPUT_JSON"])


def test_train_q75_and_task_mass_weight_definition_are_independent() -> None:
    rows = [
        {"task": "a", "gap_raw": value} for value in (1.0, 2.0, 3.0, 4.0)
    ] + [
        {"task": "b", "gap_raw": value} for value in (10.0, 20.0, 30.0, 40.0)
    ]
    scales = verifier.recompute_task_scales(rows)
    assert scales == pytest.approx({"a": 3.25, "b": 32.5})
    relative = verifier.relative_gap_vector(rows, scales)
    weights = verifier.recompute_task_mass_weights(rows, relative)
    for task in ("a", "b"):
        indices = [index for index, row in enumerate(rows) if row["task"] == task]
        assert float(np.mean(weights[indices])) == pytest.approx(1.0, abs=1e-12)
    with pytest.raises(verifier.VerificationError, match="dev-only task"):
        verifier.relative_gap_vector([{"task": "c", "gap_raw": 1.0}], scales)


def test_hash_cyclic_control_is_orientation_blind_and_preserves_each_task_multiset() -> None:
    rows = [
        {"task": "a", "parent": "p1", "better": "a1", "worse": "a0"},
        {"task": "a", "parent": "p2", "better": "a2", "worse": "a0"},
        {"task": "a", "parent": "p3", "better": "a3", "worse": "a0"},
        {"task": "b", "parent": "q1", "better": "b1", "worse": "b0"},
        {"task": "b", "parent": "q2", "better": "b2", "worse": "b0"},
    ]
    weights = np.asarray([0.25, 1.0, 4.0, 0.5, 2.0], dtype=np.float64)
    permuted = verifier.independently_permute_task_weights(rows, weights)
    for task in ("a", "b"):
        indices = np.asarray([index for index, row in enumerate(rows) if row["task"] == task])
        assert np.array_equal(np.sort(permuted[indices]), np.sort(weights[indices]))
        ordered = sorted(
            indices.tolist(),
            key=lambda index: hashlib.sha256(
                f"{verifier.PERMUTATION_SEED}|{verifier.compact(verifier.unordered_key(rows[index]))}".encode()
            ).hexdigest(),
        )
        for position, destination in enumerate(ordered):
            assert permuted[destination] == weights[ordered[(position + 1) % len(ordered)]]
    reversed_rows = [
        {**row, "better": row["worse"], "worse": row["better"]} for row in rows
    ]
    reversed_permuted = verifier.independently_permute_task_weights(reversed_rows, weights)
    assert np.array_equal(permuted, reversed_permuted)


def test_pair_to_parent_to_task_aggregation_is_recomputed() -> None:
    rows = [
        {"task": "a", "parent": "p1"},
        {"task": "a", "parent": "p1"},
        {"task": "a", "parent": "p2"},
        {"task": "b", "parent": "q1"},
    ]
    margins = {
        "binary_bt": np.asarray([1.0, 1.0, -1.0, -1.0]),
        "gap_permuted_bt": np.asarray([1.0, -1.0, -1.0, 1.0]),
        "gap_weighted_bt": np.asarray([1.0, 1.0, 1.0, -1.0]),
        "gap_ridge": np.asarray([1.0, -1.0, 0.0, 1.0]),
    }
    metrics, task_rows, values = verifier.recompute_arm_statistics(rows, margins, np.ones(4))
    assert metrics["binary_bt"]["pair_micro_accuracy"] == pytest.approx(0.5)
    assert values["binary_bt"] == pytest.approx({"a": 0.5, "b": 0.0})
    assert metrics["binary_bt"]["task_macro_parent_macro_accuracy"] == pytest.approx(0.25)
    assert values["gap_weighted_bt"] == pytest.approx({"a": 1.0, "b": 0.0})
    assert len(task_rows) == 8


def test_formal_status_requires_both_frozen_primary_contrasts() -> None:
    tasks = [f"task-{index:02d}" for index in range(20)]
    parent_counts = {task: 10 for task in tasks}
    values = {
        "binary_bt": {task: 0.50 for task in tasks},
        "gap_permuted_bt": {task: 0.51 for task in tasks},
        "gap_weighted_bt": {task: 0.52 for task in tasks},
        "gap_ridge": {task: 0.99 for task in tasks},
    }
    passed = verifier.recompute_primary(values, parent_counts)
    assert passed["gap_weighted_minus_binary"]["all_pass"] is True
    assert passed["gap_weighted_minus_gap_permuted"]["all_pass"] is True
    assert passed["all_pass"] is True

    values["gap_permuted_bt"] = {task: 0.52 for task in tasks}
    failed = verifier.recompute_primary(values, parent_counts)
    assert failed["gap_weighted_minus_binary"]["all_pass"] is True
    assert failed["gap_weighted_minus_gap_permuted"]["all_pass"] is False
    assert failed["all_pass"] is False


def test_synthetic_bundle_refits_all_four_arms_and_verifies_every_output(case: dict[str, Any]) -> None:
    receipt = verifier.verify(
        case["cards"],
        case["train"],
        case["dev"],
        case["contract"],
        case["bundle"],
        expected_contract_sha256=case["contract_sha256"],
        source=case["source"],
    )
    assert receipt["status"] == "INDEPENDENT_SOURCE_REFIT_PASS"
    assert receipt["unique_cpu_critic_refits"] == 4
    assert receipt["rows"] == {
        "arm_metrics": 4,
        "task_metrics": 80,
        "task_scales": 20,
        "per_pair": 200,
    }
    assert receipt["maximum_numeric_difference"] <= 1e-12
    assert receipt["summary_status"] == "RETROSPECTIVE_DEV_GAP_AWARE_NO_UNLOCK"
    assert case["expected"]["summary"]["primary"]["support"]["all_pass"] is True
    assert case["expected"]["summary"]["primary"]["all_pass"] is False
    assert set(receipt["primary_point_deltas"]) == {
        "gap_weighted_minus_binary",
        "gap_weighted_minus_gap_permuted",
    }
    first_pair = case["expected"]["pair_rows"][0]
    assert set(first_pair) == {
        "pair_id",
        "task",
        "parent",
        "better",
        "worse",
        "left",
        "right",
        "gap_raw",
        "train_task_gap_q75",
        "task_relative_gap",
        "better_minus_worse_margins",
        "credits",
    }
    assert set(first_pair["better_minus_worse_margins"]) == set(verifier.ARM_ORDER)


def test_synthetic_producer_bundle_passes_independent_source_refit(
    case: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    producer_bundle = tmp_path / "producer-bundle"
    monkeypatch.setattr(producer, "CONTRACT_SHA256", case["contract_sha256"])
    summary = producer.analyze(
        case["cards"],
        case["train"],
        case["dev"],
        producer_bundle,
        case["contract"],
    )
    receipt = verifier.verify(
        case["cards"],
        case["train"],
        case["dev"],
        case["contract"],
        producer_bundle,
        expected_contract_sha256=case["contract_sha256"],
        source=case["source"],
    )
    assert receipt["status"] == "INDEPENDENT_SOURCE_REFIT_PASS"
    assert receipt["summary_status"] == summary["status"]
    assert receipt["maximum_numeric_difference"] <= 1e-12


def test_margin_tamper_is_rejected_with_self_consistent_manifest(
    case: dict[str, Any], tmp_path: Path
) -> None:
    bundle = copied_bundle(case, tmp_path)
    rows = [json.loads(line) for line in (bundle / "per_pair.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["better_minus_worse_margins"]["gap_permuted_bt"] += 0.25
    (bundle / "per_pair.jsonl").unlink()
    write_jsonl(bundle / "per_pair.jsonl", rows)
    refresh_manifest(bundle, "per_pair.jsonl")
    with pytest.raises(verifier.VerificationError, match="numeric mismatch at pair"):
        validate_copy(case, bundle)


def test_status_tamper_is_rejected_with_self_consistent_manifest(
    case: dict[str, Any], tmp_path: Path
) -> None:
    bundle = copied_bundle(case, tmp_path)
    summary_path = bundle / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["status"] = "RETROSPECTIVE_DEV_GAP_AWARE_QUALIFIED_FOR_FUTURE"
    summary_path.write_bytes(verifier.canonical_bytes(summary))
    refresh_manifest(bundle, "summary.json")
    with pytest.raises(verifier.VerificationError, match="value mismatch at summary.status"):
        validate_copy(case, bundle)


def test_task_scale_tamper_is_rejected_with_self_consistent_manifest(
    case: dict[str, Any], tmp_path: Path
) -> None:
    bundle = copied_bundle(case, tmp_path)
    scale_path = bundle / "task_scales.csv"
    with scale_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["train_gap_q75"] = str(float(rows[0]["train_gap_q75"]) * 2.0)
    scale_path.unlink()
    write_csv(scale_path, verifier.SCALE_FIELDS, rows)
    refresh_manifest(bundle, "task_scales.csv")
    with pytest.raises(verifier.VerificationError, match="numeric mismatch at scale"):
        validate_copy(case, bundle)


def test_per_pair_orientation_schema_tamper_is_rejected(
    case: dict[str, Any], tmp_path: Path
) -> None:
    bundle = copied_bundle(case, tmp_path)
    path = bundle / "per_pair.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0].pop("better")
    path.unlink()
    write_jsonl(path, rows)
    refresh_manifest(bundle, "per_pair.jsonl")
    with pytest.raises(verifier.VerificationError, match="mapping schema mismatch at pair"):
        validate_copy(case, bundle)


def test_manifest_tamper_is_rejected(case: dict[str, Any], tmp_path: Path) -> None:
    bundle = copied_bundle(case, tmp_path)
    manifest_path = bundle / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["summary.json"]["sha256"] = "0" * 64
    manifest_path.write_bytes(verifier.canonical_bytes(manifest))
    with pytest.raises(verifier.VerificationError, match="manifest hash mismatch"):
        validate_copy(case, bundle)


def test_input_identity_tamper_fails_before_refit(
    case: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    train = tmp_path / "train.jsonl"
    shutil.copy2(case["train"], train)
    with train.open("ab") as handle:
        handle.write(b"\n")

    def forbidden_refit(*_args, **_kwargs):
        raise AssertionError("input identity tamper reached model refit")

    monkeypatch.setattr(verifier, "independently_refit_four_arms", forbidden_refit)
    with pytest.raises(verifier.VerificationError, match="train input identity mismatch"):
        verifier.verify(
            case["cards"],
            train,
            case["dev"],
            case["contract"],
            case["bundle"],
            expected_contract_sha256=case["contract_sha256"],
            source=case["source"],
        )


def test_contract_hash_tamper_is_rejected(case: dict[str, Any], tmp_path: Path) -> None:
    contract = tmp_path / "contract.json"
    contract.write_bytes(case["contract"].read_bytes() + b"\n")
    with pytest.raises(verifier.VerificationError, match="contract identity mismatch"):
        verifier.load_contract(contract, case["contract_sha256"], case["source"])


def test_train_dev_endpoint_overlap_fails_before_refit(
    case: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dev_rows = copy.deepcopy(case["dev_rows"])
    dev_rows[0]["better"] = case["train_rows"][0]["better"]
    dev_rows[0]["worse"] = case["train_rows"][0]["worse"]
    dev = tmp_path / "overlap-dev.jsonl"
    write_jsonl(dev, dev_rows)
    source = copy.deepcopy(case["source"])
    source["dev"] = source_receipt(dev, rows=len(dev_rows))
    contract = json.loads(case["contract"].read_text(encoding="utf-8"))
    contract["inputs"]["dev"].update(source["dev"])
    contract_path = tmp_path / "overlap-contract.json"
    contract_path.write_bytes(verifier.canonical_bytes(contract))

    def forbidden_refit(*_args, **_kwargs):
        raise AssertionError("train/dev overlap reached model refit")

    monkeypatch.setattr(verifier, "independently_refit_four_arms", forbidden_refit)
    with pytest.raises(verifier.VerificationError, match="train/dev leakage"):
        verifier.reconstruct_expected_bundle(
            case["cards"],
            case["train"],
            dev,
            contract_path,
            expected_contract_sha256=digest(contract_path),
            source=source,
        )
