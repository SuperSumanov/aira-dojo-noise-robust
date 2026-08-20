#!/usr/bin/env python3
"""Seal WL graph extension predictions for an outcome-blind first-960 snapshot."""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from phase1.activate_wl_graph_extension import (
    PROTOCOL,
    STATUS as ACTIVATION_STATUS,
    ActivationError,
    bind_source,
    locked,
    read_object,
    sha256_file,
)
from phase1 import wl_graph_multiview_extension as scorer


STATUS = "PROSPECTIVE_WL_GRAPH_PREDICTION_ESCROW_COMPLETE"
COHORT_RUN_TARGET = 960
ARMS = scorer.ARMS
BLIND_KEYS = {
    "card_id",
    "task",
    "run_id",
    "code",
    "code_sha256",
    "lineage",
    "generation_started_at_utc",
    "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id",
    "task",
    "drop_id",
    "flow_status",
    "endpoints",
    "generation_started_at_utc",
    "source_sha256",
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class EscrowError(RuntimeError):
    pass


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise EscrowError(f"blank JSONL line: {path.name}:{line_number}")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise EscrowError(f"non-object JSONL line: {path.name}:{line_number}")
            yield value


def require_sha(path: Path, expected: Any) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise EscrowError(f"SHA mismatch: {path.name}")


def credential_free(path: Path) -> bool:
    overlap = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            window = overlap + chunk
            if CREDENTIAL.search(window):
                return False
            overlap = window[-512:]
    return True


def parse_utc(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EscrowError("UTC timestamp must end in Z")
    parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None:
        raise EscrowError("UTC timestamp is naive")
    return parsed.astimezone(dt.timezone.utc)


def load_snapshot(
    state_root: Path,
    snapshot_root: Path,
    expected_snapshot: str,
    activated_at: dt.datetime,
) -> tuple[dict[str, dict[str, Any]], list[tuple[str, str]], dict[str, Any]]:
    state_root = state_root.resolve()
    snapshot_root = snapshot_root.resolve()
    if (
        snapshot_root.parent != state_root / "snapshots"
        or snapshot_root.name != expected_snapshot
        or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot)
    ):
        raise EscrowError("snapshot path/identity mismatch")
    registry_path = snapshot_root / "intake_registry.jsonl"
    runs_path = snapshot_root / "accumulator" / "provisional_runs.jsonl"
    accumulator_summary_path = snapshot_root / "accumulator" / "summary.json"
    registry = list(read_jsonl(registry_path))
    cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    intake_summary_shas: dict[str, str] = {}
    manifest_shas: dict[str, str] = {}

    for entry in registry:
        if set(entry) != {"drop_id", "intake_dir", "summary_sha256"}:
            raise EscrowError("registry schema mismatch")
        drop_id = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        if (
            not isinstance(drop_id, str)
            or drop_id in intake_summary_shas
            or intake.parent != state_root / "intakes"
            or intake.name != drop_id
        ):
            raise EscrowError("registry intake binding mismatch")
        summary_path = intake / "summary.json"
        require_sha(summary_path, entry["summary_sha256"])
        summary = read_object(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        if not all(isinstance(value, dict) for value in (outputs, security, blindness)):
            raise EscrowError("intake security/blindness contract missing")
        if (
            security.get("env_members_read") is not False
            or security.get("live_event_journal_members_read") is not False
            or blindness.get("labels_used_for_run_selection") is not False
            or blindness.get("labels_used_for_endpoint_selection") is not False
            or blindness.get("metrics_computed") != []
        ):
            raise EscrowError("intake security/blindness contract failed")
        manifest = intake / "eligible_blind_manifest.jsonl"
        manifest_sha = outputs.get("eligible_blind_manifest_sha256")
        require_sha(manifest, manifest_sha)
        if not credential_free(manifest):
            raise EscrowError("credential-shaped bytes in blind manifest")
        intake_summary_shas[drop_id] = entry["summary_sha256"]
        manifest_shas[drop_id] = str(manifest_sha)
        for row in read_jsonl(manifest):
            if set(row) != BLIND_KEYS or not isinstance(row.get("lineage"), dict):
                raise EscrowError("blind manifest schema mismatch")
            if set(row["lineage"]) != LINEAGE_KEYS:
                raise EscrowError("blind lineage schema mismatch")
            identifier = row["card_id"]
            task = row["task"]
            run_id = row["run_id"]
            code = row["code"]
            parent = row["lineage"]["parent"]
            op = row["lineage"]["op"]
            strings = (identifier, task, run_id, code, parent, op, row["generation_started_at_utc"])
            if not all(isinstance(value, str) and value for value in strings):
                raise EscrowError("blind identity/code field invalid")
            if identifier in cards or hashlib.sha256(code.encode()).hexdigest() != row["code_sha256"]:
                raise EscrowError("duplicate endpoint or code SHA mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", str(row["source_sha256"])):
                raise EscrowError("blind source SHA invalid")
            for key in ("depth", "step", "n_siblings"):
                value = row["lineage"][key]
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise EscrowError("blind lineage integer invalid")
            owner = run_drop.setdefault(run_id, drop_id)
            if owner != drop_id:
                raise EscrowError("run spans intake drops")
            cards[identifier] = {
                "id": identifier,
                "task": task,
                "run": run_id,
                "code": code,
                "code_sha256": row["code_sha256"],
                "parent": parent,
                "lineage": {key: row["lineage"][key] for key in ("depth", "step", "n_siblings", "op")},
                "generation_started_at_utc": row["generation_started_at_utc"],
                "source_sha256": row["source_sha256"],
            }

    runs = list(read_jsonl(runs_path))
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        if set(row) != RUN_KEYS:
            raise EscrowError("provisional run schema mismatch")
        run_id = row["run_id"]
        if (
            not isinstance(run_id, str)
            or run_id in run_rows
            or row.get("flow_status") != "scoreable"
            or row.get("drop_id") != run_drop.get(run_id)
        ):
            raise EscrowError("provisional run identity/status mismatch")
        parse_utc(row["generation_started_at_utc"])
        run_rows[run_id] = row
    if set(run_rows) != {card["run"] for card in cards.values()}:
        raise EscrowError("card/run support mismatch")
    endpoint_counts = collections.Counter(card["run"] for card in cards.values())
    for run_id, row in run_rows.items():
        if (
            row["endpoints"] != endpoint_counts[run_id]
            or any(
                card["task"] != row["task"]
                or card["generation_started_at_utc"] != row["generation_started_at_utc"]
                or card["source_sha256"] != row["source_sha256"]
                for card in cards.values()
                if card["run"] == run_id
            )
        ):
            raise EscrowError("card/run accounting mismatch")

    ordered = sorted(
        runs,
        key=lambda row: (row["generation_started_at_utc"], row["source_sha256"], row["run_id"]),
    )
    selected_rows = ordered[:COHORT_RUN_TARGET]
    selected_runs = {row["run_id"] for row in selected_rows}
    selected_cards = {
        identifier: card for identifier, card in sorted(cards.items()) if card["run"] in selected_runs
    }
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for identifier, card in selected_cards.items():
        groups[(card["task"], card["run"], card["parent"])].append(identifier)
    pairs = [
        pair
        for group in sorted(groups)
        for pair in itertools.combinations(sorted(groups[group]), 2)
    ]
    if not selected_cards or not pairs:
        raise EscrowError("empty first-960 prefix or pair set")
    pair_strata = collections.Counter(
        "strict_post_activation_primary"
        if parse_utc(selected_cards[left]["generation_started_at_utc"]) > activated_at
        else "outcome_unread_support_only"
        for left, right in pairs
    )
    run_strata = collections.Counter(
        "strict_post_activation_primary"
        if parse_utc(row["generation_started_at_utc"]) > activated_at
        else "outcome_unread_support_only"
        for row in selected_rows
    )
    accumulator = read_object(accumulator_summary_path)
    inventory = accumulator.get("inventory")
    if not isinstance(inventory, dict):
        raise EscrowError("accumulator inventory missing")
    checks = {
        "transactions": inventory.get("drops") == len(registry),
        "all_eligible_runs": inventory.get("eligible_runs") == len(runs),
        "all_eligible_endpoints": inventory.get("eligible_endpoints") == len(cards),
        "provisional_first960_runs": inventory.get("provisional_first960_runs") == len(selected_rows),
        "provisional_first960_endpoints": inventory.get("provisional_first960_endpoints") == len(selected_cards),
        "provisional_first960_pairs": inventory.get("provisional_first960_structural_pairs") == len(pairs),
    }
    if not all(checks.values()):
        raise EscrowError("snapshot reconstruction differs from accumulator")
    return selected_cards, pairs, {
        "snapshot_sha256": expected_snapshot,
        "intake_registry_sha256": sha256_file(registry_path),
        "provisional_runs_sha256": sha256_file(runs_path),
        "accumulator_summary_sha256": sha256_file(accumulator_summary_path),
        "intake_summary_sha256": dict(sorted(intake_summary_shas.items())),
        "blind_manifest_sha256": dict(sorted(manifest_shas.items())),
        "cross_checks_against_accumulator": checks,
        "run_strata": dict(sorted(run_strata.items())),
        "pair_strata": dict(sorted(pair_strata.items())),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path = locked(args.protocol, args.expect_protocol_sha256)
    activation_path = locked(args.activation_receipt, args.expect_activation_receipt_sha256)
    bundle_path = locked(args.bundle, args.expect_bundle_sha256)
    summary_path = locked(args.bundle_summary, args.expect_bundle_summary_sha256)
    verification_path = locked(args.bundle_verification, args.expect_bundle_verification_sha256)
    protocol = read_object(protocol_path)
    activation = read_object(activation_path)
    summary = read_object(summary_path)
    verification = read_object(verification_path)
    if protocol.get("protocol") != PROTOCOL or protocol.get("cohort_run_target") != COHORT_RUN_TARGET:
        raise EscrowError("prediction protocol mismatch")
    source_paths = protocol.get("source_paths")
    if not isinstance(source_paths, list) or not source_paths:
        raise EscrowError("prediction protocol source list missing")
    source_hashes = bind_source(args.repo_root.resolve(), args.source_commit, [str(value) for value in source_paths])
    if (
        activation.get("status") != ACTIVATION_STATUS
        or activation.get("source_commit") != args.source_commit
        or activation.get("inputs", {}).get("protocol_sha256") != args.expect_protocol_sha256
        or activation.get("inputs", {}).get("bundle_sha256") != args.expect_bundle_sha256
        or activation.get("inputs", {}).get("bundle_summary_sha256")
        != args.expect_bundle_summary_sha256
        or activation.get("inputs", {}).get("bundle_verification_sha256")
        != args.expect_bundle_verification_sha256
        or protocol.get("bundle", {}).get("bundle_sha256") != args.expect_bundle_sha256
        or protocol.get("bundle", {}).get("build_summary_sha256")
        != args.expect_bundle_summary_sha256
        or protocol.get("bundle", {}).get("independent_verification_sha256")
        != args.expect_bundle_verification_sha256
        or summary.get("status")
        != "WL_GRAPH_MULTIVIEW_BUILD_COMPLETE_NOT_YET_INDEPENDENTLY_VERIFIED"
        or summary.get("outputs", {}).get("bundle_sha256") != args.expect_bundle_sha256
        or verification.get("status") != "INDEPENDENT_WL_GRAPH_MULTIVIEW_REFIT_VERIFIED"
        or verification.get("bundle_sha256") != args.expect_bundle_sha256
        or verification.get("maximum_numeric_array_difference", 1.0) > 1e-12
        or verification.get("maximum_reference_score_difference", 1.0) > 1e-12
    ):
        raise EscrowError("activation/bundle verification chain mismatch")
    activated_at = parse_utc(activation["activated_at_utc"])
    cards, pairs, snapshot = load_snapshot(
        args.state_root, args.snapshot_root, args.expect_snapshot_sha256, activated_at
    )
    arrays = scorer.load_bundle(bundle_path)
    scores, graph_diagnostics = scorer.score_cards(cards, arrays)
    if set(scores) != set(cards):
        raise EscrowError("score coverage mismatch")

    output = args.output.resolve()
    staging = output.with_name(output.name + f".tmp-{os.getpid()}")
    if output.exists() or staging.exists():
        raise EscrowError("output path exists")
    staging.mkdir(parents=True)
    endpoint_path = staging / "endpoint_scores.csv"
    fields = (
        "card_id", "task", "run_id", "parent", "code_sha256", "generation_started_at_utc",
        "temporal_stratum", *ARMS,
    )
    with endpoint_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for identifier, card in sorted(cards.items()):
            stratum = (
                "strict_post_activation_primary"
                if parse_utc(card["generation_started_at_utc"]) > activated_at
                else "outcome_unread_support_only"
            )
            writer.writerow(
                {
                    "card_id": identifier,
                    "task": card["task"],
                    "run_id": card["run"],
                    "parent": card["parent"],
                    "code_sha256": card["code_sha256"],
                    "generation_started_at_utc": card["generation_started_at_utc"],
                    "temporal_stratum": stratum,
                    **{arm: format(scores[identifier][arm], ".17g") for arm in ARMS},
                }
            )
    pair_path = staging / "pair_predictions.jsonl"
    ties = {arm: 0 for arm in ARMS}
    pair_strata = collections.Counter()
    with pair_path.open("w", encoding="utf-8", newline="\n") as handle:
        for left, right in pairs:
            card = cards[left]
            stratum = (
                "strict_post_activation_primary"
                if parse_utc(card["generation_started_at_utc"]) > activated_at
                else "outcome_unread_support_only"
            )
            pair_strata[stratum] += 1
            row: dict[str, Any] = {
                "task": card["task"],
                "run_id": card["run"],
                "parent": card["parent"],
                "left": left,
                "right": right,
                "temporal_stratum": stratum,
                "pair_key_sha256": hashlib.sha256("\0".join((left, right)).encode()).hexdigest(),
            }
            for arm in ARMS:
                margin = scores[left][arm] - scores[right][arm]
                selected = left if margin > 0 else right if margin < 0 else "tie"
                ties[arm] += margin == 0
                row[f"{arm}_margin_left_minus_right"] = float(format(margin, ".17g"))
                row[f"{arm}_selected"] = selected
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    artifact = {
        "status": STATUS,
        "protocol": PROTOCOL,
        "source_commit": args.source_commit,
        "source_file_sha256": source_hashes,
        "activation": {
            "receipt_sha256": args.expect_activation_receipt_sha256,
            "activated_at_utc": activation["activated_at_utc"],
        },
        "inputs": {
            "protocol_sha256": args.expect_protocol_sha256,
            "bundle_sha256": args.expect_bundle_sha256,
            "bundle_summary_sha256": args.expect_bundle_summary_sha256,
            "bundle_verification_sha256": args.expect_bundle_verification_sha256,
            **{key: value for key, value in snapshot.items() if key not in {"run_strata", "pair_strata"}},
        },
        "inventory": {
            "endpoints": len(cards),
            "runs": len({card["run"] for card in cards.values()}),
            "tasks": len({card["task"] for card in cards.values()}),
            "pairs": len(pairs),
            "run_strata": snapshot["run_strata"],
            "pair_strata": dict(sorted(pair_strata.items())),
            "ties": ties,
        },
        "graph_diagnostics": graph_diagnostics,
        "outputs": {
            "endpoint_scores_sha256": sha256_file(endpoint_path),
            "pair_predictions_sha256": sha256_file(pair_path),
        },
        "scope": {
            "primary_effect_stratum": "strict_post_activation_primary",
            "pre_activation_effect_claim_allowed": False,
            "v11_frozen_or_extension_read": False,
            "prospective_outcomes_read": False,
            "temporal_label_vault_read": False,
            "effect_metrics_computed": [],
            "gpu": 0,
            "api_calls": 0,
            "base_llm_updates": 0,
        },
    }
    write_json(staging / "summary.json", artifact)
    write_json(
        staging / "sha256_manifest.json",
        {name: sha256_file(staging / name) for name in ("endpoint_scores.csv", "pair_predictions.jsonl", "summary.json")},
    )
    staging.replace(output)
    return artifact


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--repo-root", required=True, type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--protocol", required=True, type=Path)
    value.add_argument("--expect-protocol-sha256", required=True)
    value.add_argument("--activation-receipt", required=True, type=Path)
    value.add_argument("--expect-activation-receipt-sha256", required=True)
    value.add_argument("--bundle", required=True, type=Path)
    value.add_argument("--expect-bundle-sha256", required=True)
    value.add_argument("--bundle-summary", required=True, type=Path)
    value.add_argument("--expect-bundle-summary-sha256", required=True)
    value.add_argument("--bundle-verification", required=True, type=Path)
    value.add_argument("--expect-bundle-verification-sha256", required=True)
    value.add_argument("--state-root", required=True, type=Path)
    value.add_argument("--snapshot-root", required=True, type=Path)
    value.add_argument("--expect-snapshot-sha256", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> int:
    try:
        artifact = run(parser().parse_args())
    except (
        EscrowError,
        ActivationError,
        scorer.ExtensionError,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as error:
        print(f"PROSPECTIVE_WL_GRAPH_ESCROW_ERROR: {error}", file=sys.stderr)
        return 2
    inventory = artifact["inventory"]
    print(
        STATUS,
        f"endpoints={inventory['endpoints']}",
        f"pairs={inventory['pairs']}",
        f"strict_pairs={inventory['pair_strata'].get('strict_post_activation_primary', 0)}",
        "effect_metrics=0",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
