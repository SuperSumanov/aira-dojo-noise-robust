"""Outcome-blind support audit for a frozen parent-relative transition escrow."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import itertools
import json
import re
from pathlib import Path
from typing import Any


PROTOCOL = "transition-future-escrow-support-audit-v1"
STATUS_OVERLAP = "CURRENT_SUPPORT_NOT_SOURCE_INDEPENDENT"
STATUS_NOVEL = "CURRENT_SUPPORT_SOURCE_NOVEL"
BLIND_KEYS = {
    "card_id", "task", "run_id", "code", "code_sha256", "lineage",
    "generation_started_at_utc", "source_sha256",
}
LINEAGE_KEYS = {"depth", "step", "n_siblings", "op", "parent"}
RUN_KEYS = {
    "run_id", "task", "drop_id", "flow_status", "endpoints",
    "generation_started_at_utc", "source_sha256",
}
SHA = re.compile(r"[0-9a-f]{64}")
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|"
    rb"AIza[0-9A-Za-z_-]{20,}|Bearer[ \t]+[A-Za-z0-9._~-]{16,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class SupportAuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SupportAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path.name}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank JSONL line: {path.name}:{line_number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"non-object JSONL row: {path.name}:{line_number}")
            rows.append(value)
    return rows


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
    require(isinstance(value, str) and value.endswith("Z"), "UTC timestamp must end in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SupportAuditError("UTC timestamp is invalid") from error
    require(parsed.tzinfo is not None, "UTC timestamp is naive")
    return parsed.astimezone(dt.timezone.utc)


def load_snapshot(state_root: Path, expected_snapshot: str):
    state_root = state_root.resolve()
    require(SHA.fullmatch(expected_snapshot) is not None, "invalid snapshot digest")
    require((state_root / "LATEST").read_text().strip() == expected_snapshot, "LATEST mismatch")
    snapshot = (state_root / "snapshots" / expected_snapshot).resolve()
    require(snapshot.parent == state_root / "snapshots" and snapshot.is_dir(), "snapshot path mismatch")
    registry_path = snapshot / "intake_registry.jsonl"
    registry = read_jsonl(registry_path)
    cards: dict[str, dict[str, Any]] = {}
    run_drop: dict[str, str] = {}
    manifest_hashes: dict[str, str] = {}
    summary_hashes: dict[str, str] = {}
    for entry in registry:
        require(set(entry) == {"drop_id", "intake_dir", "summary_sha256"}, "registry schema mismatch")
        drop_id = entry["drop_id"]
        intake = Path(entry["intake_dir"]).resolve()
        require(
            isinstance(drop_id, str)
            and intake.parent == state_root / "intakes"
            and intake.name == drop_id
            and drop_id not in manifest_hashes,
            "registry intake identity mismatch",
        )
        summary_path = intake / "summary.json"
        require(sha256_file(summary_path) == entry["summary_sha256"], "intake summary SHA mismatch")
        summary = read_json(summary_path)
        outputs = summary.get("outputs")
        security = summary.get("security")
        blindness = summary.get("blindness")
        require(all(isinstance(value, dict) for value in (outputs, security, blindness)), "intake contract missing")
        require(
            security.get("env_members_read") is False
            and security.get("live_event_journal_members_read") is False
            and blindness.get("labels_used_for_run_selection") is False
            and blindness.get("labels_used_for_endpoint_selection") is False
            and blindness.get("metrics_computed") == [],
            "intake security/blindness contract failed",
        )
        manifest = intake / "eligible_blind_manifest.jsonl"
        manifest_sha = outputs.get("eligible_blind_manifest_sha256")
        require(isinstance(manifest_sha, str) and sha256_file(manifest) == manifest_sha, "manifest SHA mismatch")
        require(credential_free(manifest), "credential-shaped bytes in blind manifest")
        manifest_hashes[drop_id] = manifest_sha
        summary_hashes[drop_id] = entry["summary_sha256"]
        for row in read_jsonl(manifest):
            require(set(row) == BLIND_KEYS, "blind manifest schema mismatch")
            lineage = row.get("lineage")
            require(isinstance(lineage, dict) and set(lineage) == LINEAGE_KEYS, "blind lineage schema mismatch")
            identifier = row["card_id"]
            task = row["task"]
            run_id = row["run_id"]
            code = row["code"]
            parent = lineage["parent"]
            operation = lineage["op"]
            require(
                all(
                    isinstance(value, str) and value
                    for value in (
                        identifier,
                        task,
                        run_id,
                        code,
                        parent,
                        operation,
                        row["generation_started_at_utc"],
                    )
                )
                and identifier not in cards,
                "invalid or duplicate blind card",
            )
            parse_utc(row["generation_started_at_utc"])
            require(hashlib.sha256(code.encode()).hexdigest() == row["code_sha256"], "blind code SHA mismatch")
            require(SHA.fullmatch(str(row["source_sha256"])) is not None, "blind source SHA invalid")
            for key in ("depth", "step", "n_siblings"):
                value = lineage[key]
                require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, "lineage integer invalid")
            owner = run_drop.setdefault(run_id, drop_id)
            require(owner == drop_id, "run spans intake drops")
            cards[identifier] = {
                "task": task,
                "run": run_id,
                "parent": parent,
                "code_sha256": row["code_sha256"],
                "generation_started_at_utc": row["generation_started_at_utc"],
                "source_sha256": row["source_sha256"],
            }

    runs_path = snapshot / "accumulator" / "provisional_runs.jsonl"
    runs = read_jsonl(runs_path)
    run_rows: dict[str, dict[str, Any]] = {}
    for row in runs:
        require(set(row) == RUN_KEYS, "provisional run schema mismatch")
        run_id = row["run_id"]
        require(
            isinstance(run_id, str)
            and run_id not in run_rows
            and row.get("flow_status") == "scoreable"
            and row.get("drop_id") == run_drop.get(run_id),
            "provisional run identity mismatch",
        )
        require(isinstance(row.get("task"), str) and bool(row["task"]), "provisional run task invalid")
        require(
            isinstance(row.get("endpoints"), int)
            and not isinstance(row["endpoints"], bool)
            and row["endpoints"] > 0,
            "provisional run endpoint count invalid",
        )
        parse_utc(row["generation_started_at_utc"])
        require(SHA.fullmatch(str(row["source_sha256"])) is not None, "provisional source SHA invalid")
        run_rows[run_id] = row
    require(set(run_rows) == {card["run"] for card in cards.values()}, "card/run support mismatch")
    endpoint_counts = collections.Counter(card["run"] for card in cards.values())
    for run_id, row in run_rows.items():
        require(
            row["endpoints"] == endpoint_counts[run_id]
            and all(
                card["task"] == row["task"]
                and card["generation_started_at_utc"] == row["generation_started_at_utc"]
                and card["source_sha256"] == row["source_sha256"]
                for card in cards.values()
                if card["run"] == run_id
            ),
            "card/run accounting mismatch",
        )

    ordered = sorted(
        runs,
        key=lambda row: (row["generation_started_at_utc"], row["source_sha256"], row["run_id"]),
    )
    selected_runs = {row["run_id"] for row in ordered[:960]}
    selected = {identifier: card for identifier, card in cards.items() if card["run"] in selected_runs}
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for identifier, card in selected.items():
        groups[(card["task"], card["run"], card["parent"])].append(identifier)
    pairs = [
        (group, left, right)
        for group in sorted(groups)
        for left, right in itertools.combinations(sorted(groups[group]), 2)
    ]
    require(bool(selected) and bool(pairs), "empty first-960 support")
    inventory = read_json(snapshot / "accumulator" / "summary.json").get("inventory")
    require(isinstance(inventory, dict), "accumulator inventory missing")
    checks = {
        "drops": inventory.get("drops") == len(registry),
        "runs": inventory.get("eligible_runs") == len(runs),
        "endpoints": inventory.get("eligible_endpoints") == len(cards),
        "first960_runs": inventory.get("provisional_first960_runs") == len(selected_runs),
        "first960_endpoints": inventory.get("provisional_first960_endpoints") == len(selected),
        "first960_pairs": inventory.get("provisional_first960_structural_pairs") == len(pairs),
    }
    require(all(checks.values()), "accumulator cross-check failed")
    metadata = {
        "accumulator_summary_sha256": sha256_file(snapshot / "accumulator" / "summary.json"),
        "blind_manifest_hash_registry_sha256": hashlib.sha256(
            json.dumps(manifest_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "intake_registry_sha256": sha256_file(registry_path),
        "intake_summary_hash_registry_sha256": hashlib.sha256(
            json.dumps(summary_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "provisional_runs_sha256": sha256_file(runs_path),
        "snapshot_cross_checks": checks,
    }
    return selected, selected_runs, pairs, metadata


def load_training(cards_path: Path, train_path: Path, dev_path: Path):
    pair_rows = read_jsonl(train_path) + read_jsonl(dev_path)
    needed = set()
    for row in pair_rows:
        for key in ("better", "worse", "parent"):
            value = row.get(key)
            require(isinstance(value, str) and value, "training pair identity missing")
            needed.add(value)
    grouped = json.loads(cards_path.read_text(encoding="utf-8"))
    require(isinstance(grouped, dict), "training Cards root is not grouped")
    identifiers = set()
    runs = set()
    code_sha = set()
    for run_id, rows in grouped.items():
        require(isinstance(run_id, str) and isinstance(rows, list), "invalid training Cards group")
        for row in rows:
            identifier = row.get("id") if isinstance(row, dict) else None
            if identifier not in needed:
                continue
            require(identifier not in identifiers and isinstance(row.get("code"), str), "invalid needed training card")
            identifiers.add(identifier)
            runs.add(run_id)
            code_sha.add(hashlib.sha256(row["code"].encode()).hexdigest())
    require(identifiers == needed, "needed training card missing")
    return identifiers, runs, code_sha, len(pair_rows)


def summarize(
    state_root: Path,
    snapshot_sha: str,
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    expected_hashes: dict[str, str],
) -> dict[str, Any]:
    for role, path in (("cards", cards_path), ("train", train_path), ("dev", dev_path)):
        require(sha256_file(path) == expected_hashes[role], f"{role} input SHA mismatch")
    selected, selected_runs, pairs, snapshot_metadata = load_snapshot(state_root, snapshot_sha)
    train_ids, train_runs, train_code, train_rows = load_training(cards_path, train_path, dev_path)
    parent_groups = {group for group, _, _ in pairs}
    present_parent_groups = {group for group in parent_groups if group[2] in selected}
    require(
        all(selected[parent]["task"] == task and selected[parent]["run"] == run for task, run, parent in present_parent_groups),
        "present parent task/run mismatch",
    )
    covered_pairs = [(group, left, right) for group, left, right in pairs if group[2] in selected]
    card_overlap = set(selected) & train_ids
    run_overlap = selected_runs & train_runs
    selected_code = {card["code_sha256"] for card in selected.values()}
    code_overlap = selected_code & train_code

    source_novel_pairs = []
    for group, left, right in covered_pairs:
        parent = group[2]
        identifiers = (left, right, parent)
        if (
            not (set(identifiers) & train_ids)
            and selected[left]["code_sha256"] not in train_code
            and selected[right]["code_sha256"] not in train_code
            and selected[parent]["code_sha256"] not in train_code
            and group[1] not in train_runs
        ):
            source_novel_pairs.append((group, left, right))
    pair_tasks = collections.Counter(group[0] for group, _, _ in pairs)
    covered_tasks = collections.Counter(group[0] for group, _, _ in covered_pairs)
    summary = {
        "blindness": {
            "effect_metrics_computed": [],
            "label_vault_opened": False,
            "outcome_paths_accepted_by_cli": False,
            "score_registry_opened": False,
        },
        "inputs": {
            "cards_sha256": expected_hashes["cards"],
            "dev_sha256": expected_hashes["dev"],
            "snapshot_sha256": snapshot_sha,
            "train_sha256": expected_hashes["train"],
            **snapshot_metadata,
        },
        "inventory": {
            "blind_cards": len(selected),
            "blind_runs": len(selected_runs),
            "blind_tasks": len({card["task"] for card in selected.values()}),
            "covered_pair_tasks": len(covered_tasks),
            "dominant_covered_pair_task_share": (
                max(covered_tasks.values()) / len(covered_pairs) if covered_pairs else 0.0
            ),
            "dominant_pair_task_share": max(pair_tasks.values()) / len(pairs),
            "pair_parent_source_coverage": len(covered_pairs) / len(pairs),
            "pairs": len(pairs),
            "pairs_with_parent_source": len(covered_pairs),
            "parent_groups": len(parent_groups),
            "parent_groups_with_source": len(present_parent_groups),
            "source_novel_parent_covered_pairs": len(source_novel_pairs),
            "training_needed_cards": len(train_ids),
            "training_pair_rows": train_rows,
        },
        "overlap": {
            "blind_card_ids_in_training_support": len(card_overlap),
            "blind_code_sha_in_training_support": len(code_overlap),
            "blind_run_ids_in_training_support": len(run_overlap),
            "zero_run_overlap": not run_overlap,
        },
        "protocol": PROTOCOL,
        "status": STATUS_OVERLAP if card_overlap or code_overlap or run_overlap else STATUS_NOVEL,
    }
    return summary


def write_json(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("xb") as handle:
        handle.write(payload.encode())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True, type=Path)
    parser.add_argument("--expect-snapshot-sha", required=True)
    parser.add_argument("--training-cards", required=True, type=Path)
    parser.add_argument("--expect-training-cards-sha", required=True)
    parser.add_argument("--train-pairs", required=True, type=Path)
    parser.add_argument("--expect-train-pairs-sha", required=True)
    parser.add_argument("--dev-pairs", required=True, type=Path)
    parser.add_argument("--expect-dev-pairs-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(not args.output.exists(), "refusing to overwrite output")
    result = summarize(
        args.state_root,
        args.expect_snapshot_sha,
        args.training_cards,
        args.train_pairs,
        args.dev_pairs,
        {
            "cards": args.expect_training_cards_sha,
            "train": args.expect_train_pairs_sha,
            "dev": args.expect_dev_pairs_sha,
        },
    )
    write_json(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
