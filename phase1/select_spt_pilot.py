#!/usr/bin/env python3
"""Label-blind deterministic selection of a small SPT sibling pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from phase1.scoreable_prediction_tap import instrument


TASKS = (
    "random-acts-of-pizza",
    "us-patent-phrase-to-phrase-matching",
    "petfinder-pawpularity-score",
)
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9._-]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?key|access[_-]?token)\s*=\s*['\"][^'\"]{12,}['\"]"),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_text(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(text)


def secret_free(code: str) -> bool:
    return not any(pattern.search(code) for pattern in SECRET_PATTERNS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--split", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    if args.manifest.exists() or args.audit.exists():
        raise RuntimeError("manifest/audit already exists")

    split = json.loads(args.split.read_text(encoding="utf-8"))
    all_runs = set(split["all"])
    hold_runs = set(split["hold"])
    if not hold_runs < all_runs:
        raise RuntimeError("hold runs must be a strict subset of all runs")
    train_runs = all_runs - hold_runs
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    census = Counter()
    task_metadata: dict[str, dict] = {}

    # Deliberately project only identity, topology, task and source code.  The
    # label/obs fields are neither accessed nor copied into any pilot artifact.
    for line in args.cards.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        raw_task = raw.get("task") or {}
        projected = {
            "id": raw.get("id"),
            "run_id": raw.get("run_id"),
            "task": raw_task.get("name"),
            "parent_id": (raw.get("lineage") or {}).get("parent_id"),
            "code": raw.get("code"),
        }
        task = projected["task"]
        if task not in TASKS:
            continue
        metadata = {
            "metric": raw_task.get("metric"),
            "higher_is_better": raw_task.get("higher_is_better"),
        }
        if task in task_metadata and task_metadata[task] != metadata:
            raise RuntimeError(f"inconsistent task metadata: {task}")
        if not isinstance(metadata["higher_is_better"], bool):
            raise RuntimeError(f"missing metric orientation: {task}")
        task_metadata[task] = metadata
        census[(task, "cards_seen")] += 1
        if projected["run_id"] not in train_runs:
            census[(task, "excluded_hold_or_unknown_run")] += 1
            continue
        if not all(isinstance(projected[name], str) and projected[name] for name in projected):
            census[(task, "missing_required_field")] += 1
            continue
        code = projected["code"]
        if not secret_free(code):
            census[(task, "secret_pattern_rejected")] += 1
            continue
        try:
            tapped, tap_audit = instrument(code)
        except (RuntimeError, SyntaxError, ValueError):
            census[(task, "not_instrumentable")] += 1
            continue
        census[(task, "instrumentable_cards")] += 1
        groups[(task, projected["run_id"], projected["parent_id"])].append(
            {
                **projected,
                "base_code_sha256": sha256_bytes(code.encode("utf-8")),
                "base_code_bytes": len(code.encode("utf-8")),
                "tapped_code": tapped,
                "tapped_code_sha256": sha256_bytes(tapped.encode("utf-8")),
                "site_count": int(tap_audit["site_count"]),
                "tap_audit": tap_audit,
            }
        )

    eligible: dict[str, list[tuple[tuple, tuple[str, str, str], list[dict]]]] = defaultdict(list)
    for key, cards in groups.items():
        unique_by_code: dict[str, dict] = {}
        for card in cards:
            unique_by_code.setdefault(card["base_code_sha256"], card)
        unique = sorted(
            unique_by_code.values(),
            key=lambda row: (
                -row["site_count"],
                row["base_code_bytes"],
                row["base_code_sha256"],
                row["id"],
            ),
        )
        if len(unique) < 2:
            continue
        pair = unique[:2]
        group_hash = sha256_bytes("\0".join(key).encode("utf-8"))
        rank = (
            -min(card["site_count"] for card in pair),
            max(card["base_code_bytes"] for card in pair),
            group_hash,
        )
        eligible[key[0]].append((rank, key, pair))

    selected: list[tuple[tuple[str, str, str], list[dict]]] = []
    for task in TASKS:
        choices = sorted(eligible[task], key=lambda item: item[0])
        if not choices:
            raise RuntimeError(f"no label-blind instrumentable sibling group for task: {task}")
        _, key, pair = choices[0]
        selected.append((key, pair))

    corpus_sha = sha256_file(args.cards)
    split_sha = sha256_file(args.split)
    runtime_sha = sha256_file(args.runtime)
    rows: list[dict] = []
    selected_audit: list[dict] = []
    card_counter = 0
    for group_index, (key, pair) in enumerate(selected):
        task, run_id, parent_id = key
        group_id = sha256_bytes("\0".join(key).encode("utf-8"))[:20]
        for sibling_index, card in enumerate(pair):
            rotations = (
                ("original_a", "original_b", "tap"),
                ("tap", "original_a", "original_b"),
                ("original_b", "tap", "original_a"),
            )
            arms = rotations[card_counter % len(rotations)]
            for arm in arms:
                executed_code = card["tapped_code"] if arm == "tap" else card["code"]
                rows.append(
                    {
                        "index": len(rows),
                        "group_index": group_index,
                        "group_id": group_id,
                        "sibling_index": sibling_index,
                        "card_id": card["id"],
                        "competition": task,
                        "metric": task_metadata[task]["metric"],
                        "higher_is_better": task_metadata[task]["higher_is_better"],
                        "run_id": run_id,
                        "parent_id": parent_id,
                        "arm": arm,
                        "seed": 20260813,
                        "code": executed_code,
                        "code_sha256": sha256_bytes(executed_code.encode("utf-8")),
                        "base_code_sha256": card["base_code_sha256"],
                        "tap_runtime_sha256": runtime_sha if arm == "tap" else None,
                        "tap_site_count": card["site_count"],
                        "source_export_sha256": corpus_sha,
                        "split_sha256": split_sha,
                    }
                )
            selected_audit.append(
                {
                    "group_index": group_index,
                    "group_id": group_id,
                    "sibling_index": sibling_index,
                    "card_id": card["id"],
                    "competition": task,
                    "run_id": run_id,
                    "parent_id": parent_id,
                    "base_code_sha256": card["base_code_sha256"],
                    "tapped_code_sha256": card["tapped_code_sha256"],
                    "base_code_bytes": card["base_code_bytes"],
                    "tap_site_count": card["site_count"],
                    "tap_sites": card["tap_audit"]["sites"],
                }
            )
            card_counter += 1

    if len(rows) != 18 or len({row["card_id"] for row in rows}) != 6:
        raise RuntimeError("pilot must contain six cards and eighteen executions")
    manifest_text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    audit = {
        "schema_version": 1,
        "selection": (
            "Fixed three-task whitelist; non-hold runs only; group by (task,run,parent); "
            "require two unique precision-instrumentable siblings; rank by maximum minimum "
            "tap-site count, then minimum maximum code bytes, then deterministic group hash."
        ),
        "forbidden_fields_not_accessed": ["label", "obs"],
        "tasks": list(TASKS),
        "task_metadata": task_metadata,
        "cards_sha256": corpus_sha,
        "split_sha256": split_sha,
        "runtime_sha256": runtime_sha,
        "manifest_sha256": sha256_bytes(manifest_text.encode("utf-8")),
        "census": {
            task: {
                name: census[(task, name)]
                for name in (
                    "cards_seen",
                    "excluded_hold_or_unknown_run",
                    "missing_required_field",
                    "secret_pattern_rejected",
                    "not_instrumentable",
                    "instrumentable_cards",
                )
            }
            for task in TASKS
        },
        "eligible_groups": {task: len(eligible[task]) for task in TASKS},
        "selected": selected_audit,
    }
    atomic_text(args.manifest, manifest_text)
    atomic_text(
        args.audit,
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(
        "SPT_LABEL_BLIND_SELECTION_PASS "
        f"groups={len(selected)} cards={len(selected_audit)} rows={len(rows)} "
        f"manifest_sha256={audit['manifest_sha256']}"
    )


if __name__ == "__main__":
    main()
