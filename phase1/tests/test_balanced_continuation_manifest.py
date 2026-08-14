from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from phase1.balanced_continuation_manifest import ManifestError, build
from phase1.verify_balanced_continuation_manifest import VerifyError, verify


H64 = "a" * 64
C64 = "c" * 64
D64 = "d" * 64


def contract() -> dict:
    return {
        "schema_version": "balanced-continuation-contract-v1",
        "model_id": "model-a",
        "provider": "provider-a",
        "operator_config_sha256": H64,
        "prompt_sha256": C64,
        "source_commit": "b" * 40,
        "dataset_contract_sha256": D64,
        "evaluator_contract_sha256": "e" * 64,
        "hardware_class": "gpu-class-a",
        "execution_timeout_seconds": 120,
        "continuation_horizon": 2,
        "debug_policy": "fixed_one_operator_per_step",
        "workspace_policy": "fresh_per_rollout",
        "temperature": 0.7,
    }


def anchor_rows(anchor_count: int = 2, siblings: int = 3) -> list[dict]:
    rows = []
    code_number = 1
    for anchor_index in range(anchor_count):
        for sibling_index in range(siblings):
            rows.append(
                {
                    "anchor_id": f"anchor-{anchor_index}",
                    "task": f"task-{anchor_index}",
                    "source_run_id": f"run-{anchor_index}",
                    "parent_id": f"parent-{anchor_index}",
                    "sibling_id": f"sibling-{anchor_index}-{sibling_index}",
                    "code_sha256": f"{code_number:064x}",
                    "anchor_contract_sha256": H64,
                }
            )
            code_number += 1
    return rows


def write_inputs(tmp_path: Path, rows: list[dict] | None = None) -> tuple[Path, Path]:
    anchors = tmp_path / "anchors.jsonl"
    contract_path = tmp_path / "contract.json"
    rows = anchor_rows() if rows is None else rows
    anchors.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    contract_path.write_text(json.dumps(contract()), encoding="utf-8")
    return anchors, contract_path


def args(anchors: Path, contract_path: Path, output: Path) -> Namespace:
    return Namespace(
        anchors=str(anchors),
        contract=str(contract_path),
        output=str(output),
        siblings_per_anchor=3,
        replicates=2,
        horizon=2,
        seed=20260814,
        created_utc="2026-08-14T00:00:00Z",
    )


def test_end_to_end_exact_balance_and_independent_verification(tmp_path: Path) -> None:
    anchors, contract_path = write_inputs(tmp_path)
    output = tmp_path / "result"
    assert build(args(anchors, contract_path, output)) == 0

    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["anchor_count"] == 2
    assert summary["rollout_jobs"] == 12
    assert summary["planned_total_candidate_executions"] == 36
    rows = [json.loads(line) for line in (output / "assignment_manifest.jsonl").read_text().splitlines()]
    counts: dict[str, int] = {}
    blocks: dict[str, set[str]] = {}
    for row in rows:
        counts[row["sibling_id"]] = counts.get(row["sibling_id"], 0) + 1
        blocks.setdefault(row["block_id"], set()).add(row["sibling_id"])
        assert row["inclusion_probability"] == 1.0
        assert row["order_probability"] == pytest.approx(1 / 3)
    assert set(counts.values()) == {2}
    assert {len(value) for value in blocks.values()} == {3}

    receipt = tmp_path / "verify.json"
    assert verify(Namespace(result=str(output), receipt=str(receipt))) == 0
    verified = json.loads(receipt.read_text(encoding="utf-8"))
    assert verified["status"] == "VERIFIED_OUTCOME_BLIND_BALANCED_ASSIGNMENT"
    assert verified["independent_reconstruction_exact"] is True


def test_assignment_is_invariant_to_anchor_input_order(tmp_path: Path) -> None:
    rows = anchor_rows()
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_anchors, first_contract = write_inputs(first_dir, rows)
    second_anchors, second_contract = write_inputs(second_dir, list(reversed(rows)))
    first_output = tmp_path / "out-first"
    second_output = tmp_path / "out-second"
    build(args(first_anchors, first_contract, first_output))
    build(args(second_anchors, second_contract, second_output))
    assert (first_output / "assignment_manifest.jsonl").read_bytes() == (
        second_output / "assignment_manifest.jsonl"
    ).read_bytes()


def test_anchor_schema_refuses_outcome_field(tmp_path: Path) -> None:
    rows = anchor_rows()
    rows[0]["grade"] = 0.99
    anchors, contract_path = write_inputs(tmp_path, rows)
    with pytest.raises(ManifestError, match="exactly"):
        build(args(anchors, contract_path, tmp_path / "result"))


def test_unequal_sibling_support_fails_closed(tmp_path: Path) -> None:
    rows = anchor_rows()
    rows.pop()
    anchors, contract_path = write_inputs(tmp_path, rows)
    with pytest.raises(ManifestError, match="expected 3"):
        build(args(anchors, contract_path, tmp_path / "result"))


def test_credential_shape_fails_before_json_parse(tmp_path: Path) -> None:
    anchors = tmp_path / "anchors.jsonl"
    anchors.write_bytes(b"not-json sk-" + b"x" * 24)
    contract_path = tmp_path / "contract.json"
    contract_path.write_text(json.dumps(contract()), encoding="utf-8")
    with pytest.raises(ManifestError, match="credential-shaped"):
        build(args(anchors, contract_path, tmp_path / "result"))


def test_independent_verifier_detects_manifest_tampering(tmp_path: Path) -> None:
    anchors, contract_path = write_inputs(tmp_path)
    output = tmp_path / "result"
    build(args(anchors, contract_path, output))
    manifest = output / "assignment_manifest.jsonl"
    rows = manifest.read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["rollout_seed"] += 1
    rows[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")
    hashes = json.loads((output / "sha256_manifest.json").read_text(encoding="utf-8"))
    import hashlib

    hashes["assignment_manifest.jsonl"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    (output / "sha256_manifest.json").write_text(json.dumps(hashes), encoding="utf-8")
    with pytest.raises(VerifyError, match="independent reconstruction"):
        verify(Namespace(result=str(output), receipt=str(tmp_path / "verify.json")))
