"""Independent verifier for the decision exact-config v2 support gate.

The verifier deliberately does not import the producer.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "decision-semantic-exact-config-support-v2"
VERIFY_STATUS = "INDEPENDENT_DECISION_EXACT_CONFIG_SUPPORT_VERIFIED"
SENIOR = "baf6bddefe62b769b2fab699ff5805dd627dc69f"
LOCKS = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "merged": ("c62dae814f7834b9beb3457d63fb60963636a31a811b216616e6912681bba2f4", 2858161),
    "draft": ("84adc361226899d4fd7b1a17cef3bf27884e76ec591566c7a4470fd525a94de7", 1714459),
    "improve": ("c2a062a81b7aa12457d4cb6a66aa102f8623bdfbb2961dd7d443c2c3e16ab516", 1143702),
}
PAIR_SCHEMA = {
    "better", "budget", "clears_tau", "gap_raw", "intask_split", "loto_fold",
    "parent", "set_size", "src", "task", "worse",
}
CONFIG = ("task", "client", "hardware", "time_limit", "execution_timeout")
SECRET_RX = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class VerificationError(RuntimeError):
    pass


def hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1048576):
            result.update(block)
    return result.hexdigest()


def check_input(path: Path, role: str) -> None:
    expected_hash, expected_size = LOCKS[role]
    if path.stat().st_size != expected_size or hash_file(path) != expected_hash:
        raise VerificationError(f"{role} identity mismatch")
    suffix = b""
    with path.open("rb") as handle:
        while block := handle.read(1048576):
            candidate = suffix + block
            if SECRET_RX.search(candidate):
                raise VerificationError("credential-shaped content")
            suffix = candidate[-512:]


def read_pairs(path: Path) -> list[dict[str, Any]]:
    output = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            value = json.loads(line)
            if not line.strip() or not isinstance(value, dict) or set(value) != PAIR_SCHEMA:
                raise VerificationError(f"bad pair row {number}")
            output.append(value)
    return output


def compact(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    endpoints = sorted((row["better"], row["worse"]))
    return row["task"], row["parent"], endpoints[0], endpoints[1]


def load_configs(
    path: Path, wanted: set[str]
) -> tuple[dict[str, tuple[Any, ...]], dict[str, str], dict[str, int]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise VerificationError("bad card root")
    configs: dict[str, tuple[Any, ...]] = {}
    runs: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for run, cards in grouped.items():
        for card in cards:
            total += 1
            identifier = card.get("id") if isinstance(card, dict) else None
            if not isinstance(identifier, str) or identifier in seen:
                raise VerificationError("bad card identity")
            seen.add(identifier)
            if identifier not in wanted:
                continue
            task = card.get("task", {}).get("name") if isinstance(card.get("task"), dict) else None
            config = (task, card.get("client"), card.get("hardware"), card.get("time_limit"), card.get("execution_timeout"))
            if not all(isinstance(value, str) and value for value in config[:3]) or not all(
                isinstance(value, int) for value in config[3:]
            ):
                raise VerificationError("bad card config")
            configs[identifier] = config
            runs[identifier] = run
    if set(configs) != wanted:
        raise VerificationError("missing pair endpoints")
    return configs, runs, {"run_groups": len(grouped), "cards": total, "needed_cards": len(wanted), "duplicate_card_ids": total - len(seen)}


def exact(row: dict[str, Any], configs: dict[str, tuple[Any, ...]]) -> bool:
    return configs[row["better"]] == configs[row["worse"]]


def changed(row: dict[str, Any], configs: dict[str, tuple[Any, ...]]) -> tuple[str, ...]:
    return tuple(
        field for field, left, right in zip(CONFIG, configs[row["better"]], configs[row["worse"]])
        if left != right
    )


def split_inventory(rows: list[dict[str, Any]]) -> dict[str, int]:
    train = sum(row["intask_split"] == "train" for row in rows)
    test = sum(row["intask_split"] == "test" for row in rows)
    return {"train": train, "test": test, "total": len(rows)}


def independent_summary(
    merged: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    improve: list[dict[str, Any]],
    configs: dict[str, tuple[Any, ...]],
    runs: dict[str, str],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    raw = {"merged": merged, "draft": draft, "improve": improve}
    raw_integrity = {
        "merged_is_exact_component_union": Counter(map(compact, merged)) == Counter(map(compact, [*draft, *improve])),
        "draft_improve_pair_ids_disjoint": not {key(row) for row in draft}.intersection(key(row) for row in improve),
        "pair_ids_unique": all(len(rows_) == len({key(row) for row in rows_}) for rows_ in raw.values()),
        "card_inventory_exact": True,
    }
    eligible = {name: [row for row in rows_ if exact(row, configs)] for name, rows_ in raw.items()}
    filtered_integrity: dict[str, Any] = {
        "merged_is_exact_component_union": Counter(map(compact, eligible["merged"]))
        == Counter(map(compact, [*eligible["draft"], *eligible["improve"]])),
        "draft_improve_pair_ids_disjoint": not {key(row) for row in eligible["draft"]}.intersection(
            key(row) for row in eligible["improve"]
        ),
        "all_pairs_exact_config": all(exact(row, configs) for row in eligible["merged"]),
        "pair_task_matches_config": all(
            configs[row["better"]][0] == row["task"] == configs[row["worse"]][0]
            for row in eligible["merged"]
        ),
    }
    train = [row for row in eligible["merged"] if row["intask_split"] == "train"]
    test = [row for row in eligible["merged"] if row["intask_split"] == "test"]
    train_cards = {row[role] for row in train for role in ("better", "worse")}
    test_cards = {row[role] for row in test for role in ("better", "worse")}
    train_runs, test_runs = {runs[item] for item in train_cards}, {runs[item] for item in test_cards}
    filtered_integrity.update(
        train_test_endpoint_disjoint=not train_cards.intersection(test_cards),
        train_test_physical_run_disjoint=not train_runs.intersection(test_runs),
        train_endpoints=len(train_cards), test_endpoints=len(test_cards),
        train_runs=len(train_runs), test_runs=len(test_runs),
        train_test_endpoint_overlap=len(train_cards.intersection(test_cards)),
        train_test_run_overlap=len(train_runs.intersection(test_runs)),
    )
    patterns = Counter("+".join(changed(row, configs)) for row in merged if not exact(row, configs))
    fields = Counter(field for row in merged if not exact(row, configs) for field in changed(row, configs))
    cells = Counter()
    for semantics in ("draft", "improve"):
        for row in raw[semantics]:
            cells[(semantics, row["intask_split"])] += not exact(row, configs)
    raw_inventory = {name: split_inventory(rows_) for name, rows_ in raw.items()}
    eligible_inventory = {name: split_inventory(rows_) for name, rows_ in eligible.items()}
    task_counts = Counter(row["task"] for row in test)
    supported = sum(value >= 10 for value in task_counts.values())
    dominant = max(task_counts.values(), default=0) / len(test) if test else None
    gates = {
        "merged_train_ge_4000": eligible_inventory["merged"]["train"] >= 4000,
        "merged_test_ge_750": eligible_inventory["merged"]["test"] >= 750,
        "draft_train_ge_2000": eligible_inventory["draft"]["train"] >= 2000,
        "draft_test_ge_200": eligible_inventory["draft"]["test"] >= 200,
        "improve_train_ge_1500": eligible_inventory["improve"]["train"] >= 1500,
        "improve_test_ge_400": eligible_inventory["improve"]["test"] >= 400,
        "test_tasks_ge_20": len(task_counts) >= 20,
        "supported_test_tasks_ge_15": supported >= 15,
        "dominant_test_task_share_le_0_25": dominant is not None and dominant <= .25,
        "all_integrity_checks": all(raw_integrity.values()) and all(filtered_integrity[key] for key in (
            "merged_is_exact_component_union", "draft_improve_pair_ids_disjoint", "all_pairs_exact_config",
            "pair_task_matches_config", "train_test_endpoint_disjoint", "train_test_physical_run_disjoint",
        )),
    }
    per_task = []
    for task in sorted({row["task"] for row in merged}):
        record: dict[str, Any] = {"task": task}
        for semantics in ("merged", "draft", "improve"):
            for role in ("train", "test"):
                record[f"{semantics}_{role}_raw"] = sum(
                    row["task"] == task and row["intask_split"] == role for row in raw[semantics]
                )
                record[f"{semantics}_{role}_eligible"] = sum(
                    row["task"] == task and row["intask_split"] == role for row in eligible[semantics]
                )
        per_task.append(record)
    return {
        "protocol": PROTOCOL, "raw_integrity": raw_integrity, "filtered_integrity": filtered_integrity,
        "raw_inventory": raw_inventory, "eligible_inventory": eligible_inventory,
        "mismatch": {
            "pairs": len(merged) - len(eligible["merged"]),
            "share": (len(merged) - len(eligible["merged"])) / len(merged),
            "by_field": dict(sorted(fields.items())), "by_pattern": dict(sorted(patterns.items())),
            "by_semantics_split": {f"{kind}_{role}": cells[(kind, role)] for kind in ("draft", "improve") for role in ("train", "test")},
        },
        "eligible_test_support": {
            "tasks": len(task_counts), "tasks_with_at_least_10_pairs": supported,
            "dominant_task_pairs": max(task_counts.values(), default=0), "dominant_task_share": dominant,
            "pairs_per_task": dict(sorted(task_counts.items())),
        },
        "gates": gates,
        "status": "V2_EXACT_CONFIG_SUPPORT_ELIGIBLE" if all(gates.values()) else "V2_INSUFFICIENT_EXACT_CONFIG_SUPPORT",
        "scope": {
            "gap_raw_used_for_selection": False, "pair_orientation_used_for_selection": False,
            "code_field_used_for_selection": False, "card_label_used_for_selection": False,
            "model_fit": False,
            "checkpoint_read": False, "prospective_vault_read": False, "gpu_hours": 0,
            "api_calls": 0, "credential_shape_matches": 0,
        },
    }, eligible, per_task


def canonical_lines(rows: list[dict[str, Any]]) -> bytes:
    return "".join(compact(row) + "\n" for row in rows).encode()


def parse_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: (value if key == "task" else int(value)) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def verify(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(__file__).resolve().parent.parent
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != args.source_commit or args.senior_commit != SENIOR:
        raise VerificationError("source identity mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise VerificationError("dirty verifier worktree")
    paths = {name: getattr(args, name).resolve(strict=True) for name in LOCKS}
    for name, path in paths.items():
        check_input(path, name)
    artifact = args.artifact.resolve(strict=True)
    names = {path.name for path in artifact.iterdir() if path.is_file()}
    expected_names = {
        "eligible_merged.jsonl", "eligible_draft.jsonl", "eligible_improve.jsonl",
        "per_task_support.csv", "summary.json", "artifact_manifest.json",
    }
    if names != expected_names:
        raise VerificationError("artifact filenames mismatch")
    manifest = json.loads((artifact / "artifact_manifest.json").read_text(encoding="utf-8"))
    expected_manifest = {name: hash_file(artifact / name) for name in expected_names - {"artifact_manifest.json"}}
    if manifest != expected_manifest:
        raise VerificationError("artifact manifest mismatch")
    raw = {name: read_pairs(paths[name]) for name in ("merged", "draft", "improve")}
    wanted = {row[role] for rows in raw.values() for row in rows for role in ("better", "worse")}
    configs, runs, inventory = load_configs(paths["cards"], wanted)
    if inventory["run_groups"] != 676 or inventory["cards"] != 31742:
        raise VerificationError("card inventory mismatch")
    rebuilt, eligible, per_task = independent_summary(
        raw["merged"], raw["draft"], raw["improve"], configs, runs
    )
    summary = json.loads((artifact / "summary.json").read_text(encoding="utf-8"))
    checks = {
        "protocol": summary.get("protocol") == PROTOCOL,
        "source_commit": summary.get("source_commit") == commit,
        "senior_commit": summary.get("senior_source_commit") == SENIOR,
        "inputs": summary.get("inputs") == {
            name: {"sha256": LOCKS[name][0], "bytes": LOCKS[name][1]} for name in sorted(LOCKS)
        },
        "card_inventory": summary.get("card_inventory") == inventory,
        "scientific_summary": all(summary.get(name) == rebuilt[name] for name in (
            "protocol", "raw_integrity", "filtered_integrity", "raw_inventory", "eligible_inventory",
            "mismatch", "eligible_test_support", "gates", "status", "scope",
        )),
        "eligible_merged": (artifact / "eligible_merged.jsonl").read_bytes() == canonical_lines(eligible["merged"]),
        "eligible_draft": (artifact / "eligible_draft.jsonl").read_bytes() == canonical_lines(eligible["draft"]),
        "eligible_improve": (artifact / "eligible_improve.jsonl").read_bytes() == canonical_lines(eligible["improve"]),
        "per_task": parse_csv(artifact / "per_task_support.csv") == per_task,
        "producer_source": summary.get("reproducibility", {}).get("source_sha256")
        == hash_file(args.producer_source.resolve(strict=True)),
    }
    if not all(checks.values()):
        raise VerificationError("verification mismatch: " + ",".join(name for name, ok in checks.items() if not ok))
    return {
        "protocol": "independent-decision-semantic-exact-config-support-v2",
        "status": VERIFY_STATUS, "source_commit": commit,
        "scientific_status": rebuilt["status"], "verification": checks, "all_pass": True,
        "observed": {
            "mismatch_pairs": rebuilt["mismatch"]["pairs"],
            "eligible_train": rebuilt["eligible_inventory"]["merged"]["train"],
            "eligible_test": rebuilt["eligible_inventory"]["merged"]["test"],
            "passed_gates": sum(rebuilt["gates"].values()), "total_gates": len(rebuilt["gates"]),
        },
        "scope": {"producer_imported": False, "model_fit": False, "prospective_vault_read": False},
    }


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in LOCKS:
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--senior-commit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--producer-source", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.output.exists():
        print("DECISION_EXACT_CONFIG_VERIFY_ERROR: output exists", file=sys.stderr)
        return 2
    try:
        receipt = verify(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes((json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    except (VerificationError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DECISION_EXACT_CONFIG_VERIFY_ERROR: {error}", file=sys.stderr)
        return 1
    print(
        VERIFY_STATUS,
        f"scientific_status={receipt['scientific_status']}",
        f"eligible_test={receipt['observed']['eligible_test']}",
        "model_fit=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
