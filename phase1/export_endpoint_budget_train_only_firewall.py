#!/usr/bin/env python3
"""Trusted firewall exporting only the certified historical train residual."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phase1 import audit_historical_independent_sibling_graph_gate as qualification
from phase1 import develop_yield_guarded_breadth_feasibility_v2 as historical
from phase1 import falsify_historical_run_split_breadth_pareto as graph_source


PROTOCOL = "endpoint-budget-label-efficiency-smoke-v1"
TOPOLOGY = "endpoint-budget-train-only-topology-v1"
LABELS = "endpoint-budget-train-only-labels-v1"
RECEIPT = "endpoint-budget-train-only-firewall-receipt-v1"


class FirewallError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FirewallError(message)


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def value_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(), f"unsafe JSON: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"object required: {path}")
    return value


def load_protocol(path: Path, expected_sha: str) -> dict[str, Any]:
    require(file_sha(path) == expected_sha, "protocol SHA")
    value = read_object(path)
    require(value.get("protocol") == PROTOCOL, "protocol name")
    require(value["population"]["source_rows_must_have_intask_split"] == "train", "train contract")
    require(value["population"]["senior_test_rows_forbidden"] is True, "test contract")
    return value


def reconstruct_residual(
    worktree: Path, data_root: Path, cards_root: Path
) -> tuple[list[Any], dict[str, Any]]:
    paths = historical.paths(worktree, data_root, cards_root)
    topology_protocol = read_object(
        worktree / "phase1/historical_run_split_breadth_pareto_falsification_v1.json"
    )
    prior_protocol_path = (
        worktree / "phase1/historical_independent_label_scarce_yield_confirmation_v1.json"
    )
    prior_protocol, _ = graph_source.prior.load_protocol(
        prior_protocol_path,
        topology_protocol["immutable_inputs"]["prior_protocol"]["sha256"],
    )
    qualification_result, _ = graph_source.prior.verify_qualification(
        paths, prior_protocol
    )
    old_protocol_path = Path(paths.qualification_protocol).resolve()
    old_protocol = qualification.load_protocol(
        old_protocol_path,
        prior_protocol["immutable_inputs"]["qualification_protocol"]["sha256"],
    )
    qualification.verify_published_dependencies(paths, old_protocol)
    qualification.verify_security_receipt(
        Path(paths.senior_security_receipt).resolve(), old_protocol
    )
    immutable = old_protocol["immutable_inputs"]
    card_path = Path(paths.senior_cards).resolve()
    run_path = Path(paths.senior_run_split).resolve()
    decision_path = Path(paths.senior_decision).resolve()
    require(file_sha(card_path) == immutable["senior_safe_cards"]["sha256"], "cards SHA")
    require(file_sha(run_path) == immutable["senior_run_split"]["sha256"], "run SHA")
    require(file_sha(decision_path) == immutable["senior_decision"]["sha256"], "decision SHA")
    senior_protocol_path = Path(paths.senior_quarantine_protocol).resolve()
    senior_binding = immutable["senior_0819_quarantine_protocol"]
    senior_protocol = qualification.quarantine.load_protocol(
        senior_protocol_path, senior_binding["sha256"]
    )
    all_runs, held_runs = qualification.relation.base.load_run_split(
        run_path, senior_protocol
    )
    card_refs, _ = qualification.relation.base.load_cards(card_path, all_runs)
    rows, diagnostics = qualification.relation.read_rows(
        decision_path,
        card_refs,
        held_runs,
        senior_protocol["immutable_inputs"]["decision"],
    )
    core = [row for row in rows if qualification.quarantine.is_core(row, held_runs)]
    train_core = [row for row in core if row.split == "train"]
    require(
        len(core) == 1270 and len(train_core) == 952 and diagnostics["rows"] == 7644,
        "core closure",
    )
    v11 = qualification.load_v11_graph(Path(paths.v11_pairs).resolve(), old_protocol)
    residual, _ = qualification.strict_residual(
        train_core,
        set(v11["endpoints"]) | set(v11["parents"]),
        set(v11["runs"]),
    )
    require(
        qualification.fingerprint(residual)
        == qualification_result["identity_fingerprints"]["strict_residual"],
        "residual fingerprint",
    )
    require(
        len(residual) == 539
        and all(
            row.split == "train"
            and row.first_run == row.second_run == row.parent_run
            and row.relation == "verified_direct_sibling"
            for row in residual
        ),
        "strict train-only residual",
    )
    return residual, {
        "source_rows": diagnostics["rows"],
        "core_rows": len(core),
        "train_core_rows": len(train_core),
        "strict_residual_rows": len(residual),
        "strict_residual_fingerprint_sha256": qualification.fingerprint(residual),
    }


def build(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    protocol = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    residual, census = reconstruct_residual(
        args.worktree.resolve(), args.data_root.resolve(), args.cards_root.resolve()
    )
    ordered = sorted(
        residual,
        key=lambda row: (
            tuple(sorted((row.first, row.second))),
            row.parent,
            row.task,
            row.first_run,
        ),
    )
    topology_rows = [
        {
            "u": min(row.first, row.second),
            "v": max(row.first, row.second),
            "parent": row.parent,
            "task": row.task,
            "physical_run": row.first_run,
            "source_split": "train",
        }
        for row in ordered
    ]
    label_rows = [
        {
            "better": row.first,
            "worse": row.second,
            "parent": row.parent,
            "task": row.task,
            "physical_run": row.first_run,
            "source_split": "train",
            "relation": "verified_direct_sibling",
        }
        for row in ordered
    ]
    require(
        len({(row["u"], row["v"]) for row in topology_rows}) == len(topology_rows),
        "topology duplicate",
    )
    topology = {
        "protocol": TOPOLOGY,
        "protocol_sha256": args.protocol_sha256,
        "source_commit": args.source_commit,
        "rows": topology_rows,
        "pair_orientation_emitted": False,
        "all_source_rows_train": True,
    }
    labels = {
        "protocol": LABELS,
        "protocol_sha256": args.protocol_sha256,
        "source_commit": args.source_commit,
        "rows": label_rows,
        "all_source_rows_train": True,
        "senior_test_rows_emitted": 0,
    }
    receipt = {
        "protocol": RECEIPT,
        "status": "TRAIN_ONLY_FIREWALL_COMPLETE",
        "protocol_sha256": args.protocol_sha256,
        "source_commit": args.source_commit,
        "input_bindings": {
            "decision_sha256": protocol["immutable_inputs"]["senior_decision"]["sha256"],
            "run_split_sha256": protocol["immutable_inputs"]["senior_run_split"]["sha256"],
            "safe_cards_sha256": protocol["immutable_inputs"]["senior_safe_cards"]["sha256"],
            "security_receipt_sha256": protocol["immutable_inputs"]["senior_security_receipt"]["sha256"],
        },
        "census": census,
        "topology_sha256": value_sha(topology),
        "labels_sha256": value_sha(labels),
        "scope": {
            "trusted_firewall_parsed_source_rows_before_split_export": True,
            "analysis_selection_receives_raw_decision_path": False,
            "model_fit_receives_raw_decision_path": False,
            "senior_test_rows_exported": 0,
            "prospective_rows_or_values_used": False,
            "gpu_api_model_fit_base_update": "0/0/0/0",
        },
    }
    return receipt, topology, labels


def write_exclusive(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(canonical_bytes(value))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--cards-root", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--topology-output", type=Path, required=True)
    parser.add_argument("--labels-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(
        len(args.source_commit) == 40
        and all(character in "0123456789abcdef" for character in args.source_commit),
        "source commit",
    )
    receipt, topology, labels = build(args)
    write_exclusive(args.topology_output.resolve(), topology)
    write_exclusive(args.labels_output.resolve(), labels)
    require(
        file_sha(args.topology_output.resolve()) == receipt["topology_sha256"],
        "written topology SHA",
    )
    require(
        file_sha(args.labels_output.resolve()) == receipt["labels_sha256"],
        "written labels SHA",
    )
    write_exclusive(args.receipt_output.resolve(), receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
