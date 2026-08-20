"""Outcome-independent exact-config support gate for decision semantic v2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "decision-semantic-exact-config-support-v2"
SENIOR_COMMIT = "baf6bddefe62b769b2fab699ff5805dd627dc69f"
INPUTS = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "merged": ("c62dae814f7834b9beb3457d63fb60963636a31a811b216616e6912681bba2f4", 2858161),
    "draft": ("84adc361226899d4fd7b1a17cef3bf27884e76ec591566c7a4470fd525a94de7", 1714459),
    "improve": ("c2a062a81b7aa12457d4cb6a66aa102f8623bdfbb2961dd7d443c2c3e16ab516", 1143702),
}
FIELDS = {
    "better", "budget", "clears_tau", "gap_raw", "intask_split", "loto_fold",
    "parent", "set_size", "src", "task", "worse",
}
CONFIG_FIELDS = ("task", "client", "hardware", "time_limit", "execution_timeout")
SECRET = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


class SupportError(RuntimeError):
    """Fail-closed support or integrity error."""


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def compact(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def scan_credential_shapes(path: Path, role: str) -> None:
    tail = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            candidate = tail + chunk
            if SECRET.search(candidate):
                raise SupportError(f"credential-shaped {role} content")
            tail = candidate[-512:]


def secure(path: Path, role: str) -> None:
    expected_hash, expected_size = INPUTS[role]
    if path.stat().st_size != expected_size or digest(path) != expected_hash:
        raise SupportError(f"{role} input identity mismatch")
    scan_credential_shapes(path, role)


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                raise SupportError(f"blank pair row {path.name}:{number}")
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != FIELDS:
                raise SupportError(f"pair schema mismatch {path.name}:{number}")
            if (
                row.get("src") != "decision"
                or row.get("intask_split") not in {"train", "test"}
                or not all(isinstance(row.get(key), str) and row[key] for key in ("better", "worse", "task", "parent"))
                or row["better"] == row["worse"]
            ):
                raise SupportError(f"pair identity invalid {path.name}:{number}")
            rows.append(row)
    return rows


def pair_id(row: dict[str, Any]) -> tuple[str, str, str, str]:
    left, right = sorted((row["better"], row["worse"]))
    return row["task"], row["parent"], left, right


def card_provenance(
    path: Path, needed: set[str]
) -> tuple[dict[str, tuple[Any, ...]], dict[str, str], dict[str, Any]]:
    grouped = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grouped, dict):
        raise SupportError("card root is not grouped")
    configs: dict[str, tuple[Any, ...]] = {}
    run_of: dict[str, str] = {}
    seen: set[str] = set()
    total = 0
    for run, cards in grouped.items():
        if not isinstance(run, str) or not isinstance(cards, list):
            raise SupportError("invalid card run group")
        for card in cards:
            total += 1
            if not isinstance(card, dict) or not isinstance(card.get("id"), str) or card["id"] in seen:
                raise SupportError("duplicate or invalid card")
            identifier = card["id"]
            seen.add(identifier)
            if identifier not in needed:
                continue
            task_object = card.get("task")
            task = task_object.get("name") if isinstance(task_object, dict) else None
            config = (
                task, card.get("client"), card.get("hardware"),
                card.get("time_limit"), card.get("execution_timeout"),
            )
            if (
                not all(isinstance(value, str) and value for value in config[:3])
                or not all(isinstance(value, int) for value in config[3:])
            ):
                raise SupportError("card config incomplete")
            configs[identifier] = config
            run_of[identifier] = run
    if set(configs) != needed:
        raise SupportError("pair endpoint missing from cards")
    return configs, run_of, {
        "run_groups": len(grouped), "cards": total, "needed_cards": len(needed),
        "duplicate_card_ids": total - len(seen),
    }


def exact(row: dict[str, Any], configs: dict[str, tuple[Any, ...]]) -> bool:
    return configs[row["better"]] == configs[row["worse"]]


def mismatch_fields(row: dict[str, Any], configs: dict[str, tuple[Any, ...]]) -> tuple[str, ...]:
    left, right = configs[row["better"]], configs[row["worse"]]
    return tuple(field for field, lvalue, rvalue in zip(CONFIG_FIELDS, left, right) if lvalue != rvalue)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(compact(row) + "\n")


def split_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {name: sum(row["intask_split"] == name for row in rows) for name in ("train", "test")}


def support_inventory(
    rows: list[dict[str, Any]],
    configs: dict[str, tuple[Any, ...]],
    run_of: dict[str, str],
) -> dict[str, dict[str, int]]:
    output: dict[str, dict[str, int]] = {}
    for split in ("all", "train", "test"):
        selected = rows if split == "all" else [row for row in rows if row["intask_split"] == split]
        endpoints = {row[role] for row in selected for role in ("better", "worse")}
        output[split] = {
            "pairs": len(selected),
            "endpoints": len(endpoints),
            "physical_runs": len({run_of[identifier] for identifier in endpoints}),
            "tasks": len({row["task"] for row in selected}),
            "task_parent_keys": len({(row["task"], row["parent"]) for row in selected}),
            "exact_config_strata": len({configs[row["better"]] for row in selected}),
        }
    return output


def summarize(
    merged: list[dict[str, Any]],
    draft: list[dict[str, Any]],
    improve: list[dict[str, Any]],
    configs: dict[str, tuple[Any, ...]],
    run_of: dict[str, str],
    card_inventory: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    raw = {"merged": merged, "draft": draft, "improve": improve}
    raw_checks = {
        "merged_is_exact_component_union": Counter(map(compact, merged))
        == Counter(map(compact, [*draft, *improve])),
        "draft_improve_pair_ids_disjoint": not {pair_id(row) for row in draft}.intersection(
            pair_id(row) for row in improve
        ),
        "pair_ids_unique": all(len(rows) == len({pair_id(row) for row in rows}) for rows in raw.values()),
        "card_inventory_exact": card_inventory["run_groups"] == 676 and card_inventory["cards"] == 31742,
    }
    if not all(raw_checks.values()):
        raise SupportError("raw integrity gate failed")
    eligible = {name: [row for row in rows if exact(row, configs)] for name, rows in raw.items()}
    filtered_checks = {
        "merged_is_exact_component_union": Counter(map(compact, eligible["merged"]))
        == Counter(map(compact, [*eligible["draft"], *eligible["improve"]])),
        "draft_improve_pair_ids_disjoint": not {pair_id(row) for row in eligible["draft"]}.intersection(
            pair_id(row) for row in eligible["improve"]
        ),
        "all_pairs_exact_config": all(exact(row, configs) for row in eligible["merged"]),
        "pair_task_matches_config": all(
            configs[row["better"]][0] == row["task"] == configs[row["worse"]][0]
            for row in eligible["merged"]
        ),
    }
    train = [row for row in eligible["merged"] if row["intask_split"] == "train"]
    test = [row for row in eligible["merged"] if row["intask_split"] == "test"]
    train_cards = {row[key] for row in train for key in ("better", "worse")}
    test_cards = {row[key] for row in test for key in ("better", "worse")}
    train_runs = {run_of[identifier] for identifier in train_cards}
    test_runs = {run_of[identifier] for identifier in test_cards}
    filtered_checks.update(
        train_test_endpoint_disjoint=not train_cards.intersection(test_cards),
        train_test_physical_run_disjoint=not train_runs.intersection(test_runs),
    )
    if not all(filtered_checks.values()):
        raise SupportError("filtered integrity gate failed")

    mismatch_pattern = Counter("+".join(mismatch_fields(row, configs)) for row in merged if not exact(row, configs))
    mismatch_per_field = Counter(
        field for row in merged if not exact(row, configs) for field in mismatch_fields(row, configs)
    )
    mismatch_by_cell = Counter()
    for kind in ("draft", "improve"):
        for row in raw[kind]:
            if not exact(row, configs):
                mismatch_by_cell[(kind, row["intask_split"])] += 1

    raw_inventory = {name: {**split_counts(rows), "total": len(rows)} for name, rows in raw.items()}
    eligible_inventory = {
        name: {**split_counts(rows), "total": len(rows)} for name, rows in eligible.items()
    }
    eligible_support = {
        name: support_inventory(rows, configs, run_of) for name, rows in eligible.items()
    }
    test_task_counts = Counter(row["task"] for row in test)
    supported_tasks = sum(count >= 10 for count in test_task_counts.values())
    dominant = max(test_task_counts.values(), default=0) / len(test) if test else None
    gates = {
        "merged_train_ge_4000": eligible_inventory["merged"]["train"] >= 4000,
        "merged_test_ge_750": eligible_inventory["merged"]["test"] >= 750,
        "draft_train_ge_2000": eligible_inventory["draft"]["train"] >= 2000,
        "draft_test_ge_200": eligible_inventory["draft"]["test"] >= 200,
        "improve_train_ge_1500": eligible_inventory["improve"]["train"] >= 1500,
        "improve_test_ge_400": eligible_inventory["improve"]["test"] >= 400,
        "test_tasks_ge_20": len(test_task_counts) >= 20,
        "supported_test_tasks_ge_15": supported_tasks >= 15,
        "dominant_test_task_share_le_0_25": dominant is not None and dominant <= 0.25,
        "all_integrity_checks": all(raw_checks.values()) and all(filtered_checks.values()),
    }
    per_task_rows = []
    for task in sorted({row["task"] for row in merged}):
        item: dict[str, Any] = {"task": task}
        for kind in ("merged", "draft", "improve"):
            for role in ("train", "test"):
                raw_count = sum(row["task"] == task and row["intask_split"] == role for row in raw[kind])
                eligible_count = sum(
                    row["task"] == task and row["intask_split"] == role for row in eligible[kind]
                )
                item[f"{kind}_{role}_raw"] = raw_count
                item[f"{kind}_{role}_eligible"] = eligible_count
        per_task_rows.append(item)
    return {
        "protocol": PROTOCOL,
        "raw_integrity": raw_checks,
        "filtered_integrity": {
            **filtered_checks,
            "train_endpoints": len(train_cards), "test_endpoints": len(test_cards),
            "train_runs": len(train_runs), "test_runs": len(test_runs),
            "train_test_endpoint_overlap": 0, "train_test_run_overlap": 0,
        },
        "raw_inventory": raw_inventory,
        "eligible_inventory": eligible_inventory,
        "eligible_support": eligible_support,
        "mismatch": {
            "pairs": len(merged) - len(eligible["merged"]),
            "share": (len(merged) - len(eligible["merged"])) / len(merged),
            "by_field": dict(sorted(mismatch_per_field.items())),
            "by_pattern": dict(sorted(mismatch_pattern.items())),
            "by_semantics_split": {
                f"{kind}_{role}": mismatch_by_cell[(kind, role)]
                for kind in ("draft", "improve") for role in ("train", "test")
            },
        },
        "eligible_test_support": {
            "tasks": len(test_task_counts), "tasks_with_at_least_10_pairs": supported_tasks,
            "dominant_task_pairs": max(test_task_counts.values(), default=0),
            "dominant_task_share": dominant,
            "pairs_per_task": dict(sorted(test_task_counts.items())),
        },
        "gates": gates,
        "status": "V2_EXACT_CONFIG_SUPPORT_ELIGIBLE"
        if all(gates.values())
        else "V2_INSUFFICIENT_EXACT_CONFIG_SUPPORT",
        "scope": {
            "gap_raw_used_for_selection": False,
            "pair_orientation_used_for_selection": False,
            "code_field_used_for_selection": False,
            "card_label_used_for_selection": False,
            "model_fit": False,
            "checkpoint_read": False,
            "prospective_vault_read": False,
            "gpu_hours": 0,
            "api_calls": 0,
            "credential_shape_matches": 0,
        },
    }, eligible, per_task_rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["task"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.senior_commit != SENIOR_COMMIT:
        raise SupportError("senior commit mismatch")
    repo = Path(__file__).resolve().parent.parent
    commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if commit != args.source_commit:
        raise SupportError("source commit mismatch")
    if subprocess.check_output(
        ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], text=True
    ).strip():
        raise SupportError("dirty scientific worktree")
    paths = {name: getattr(args, name).resolve(strict=True) for name in INPUTS}
    for name, path in paths.items():
        secure(path, name)
    merged, draft, improve = (read_rows(paths[name]) for name in ("merged", "draft", "improve"))
    needed = {row[key] for row in [*merged, *draft, *improve] for key in ("better", "worse")}
    configs, runs, card_inventory = card_provenance(paths["cards"], needed)
    summary, eligible, per_task = summarize(
        merged, draft, improve, configs, runs, card_inventory
    )
    summary.update(
        source_commit=commit,
        senior_source_commit=SENIOR_COMMIT,
        inputs={name: {"sha256": INPUTS[name][0], "bytes": INPUTS[name][1]} for name in sorted(INPUTS)},
        card_inventory=card_inventory,
        reproducibility={
            "python": platform.python_version(),
            "source_sha256": digest(Path(__file__).resolve()),
            "runtime_recorded_externally": True,
        },
    )
    output = args.output
    if output.exists():
        raise SupportError("output exists")
    output.mkdir(parents=True)
    for name in ("merged", "draft", "improve"):
        write_jsonl(output / f"eligible_{name}.jsonl", eligible[name])
    write_csv(output / "per_task_support.csv", per_task)
    (output / "summary.json").write_bytes(canonical(summary))
    names = ["eligible_merged.jsonl", "eligible_draft.jsonl", "eligible_improve.jsonl", "per_task_support.csv", "summary.json"]
    manifest = {name: digest(output / name) for name in names}
    (output / "artifact_manifest.json").write_bytes(canonical(manifest))
    return summary


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in INPUTS:
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--senior-commit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        result = execute(arguments())
    except (SupportError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"DECISION_EXACT_CONFIG_SUPPORT_ERROR: {error}")
        return 1
    print(
        "DECISION_EXACT_CONFIG_SUPPORT_COMPLETE",
        f"status={result['status']}",
        f"eligible_train={result['eligible_inventory']['merged']['train']}",
        f"eligible_test={result['eligible_inventory']['merged']['test']}",
        "model_fit=false",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
