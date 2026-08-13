"""Build an append-only exploratory corpus from manifest-complete Qwen/K2 runs.

This builder deliberately does not mutate the released v11 corpus or its frozen evaluation
sets.  A run is accepted only when the pool manifest marks it completed with exit code zero,
the checkpoint journal is non-empty, checkpoint/state.json is valid, and exactly one final
MCTS search export exists whose node count matches the journal.  Failed/cancelled 20-step
checkpoints are recorded but excluded.

The output extension carries the physical run id directly.  The combined corpus is an
append-only byte-for-byte v11 prefix plus the extension; a full card->run map is emitted for
the existing decision-pair builder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from collections import Counter
from pathlib import Path

from phase1.build_cards import TASK_TYPE, _peek_competition
from phase1.cards import TaskInfo, parse_journal


DEFAULT_BATCHES = (
    "gen2K2a,gen2K2b,gen2Q01,gen2Q02,gen2Q03,gen2Q04,gen2Q05,"
    "gen2Q06,gen2Q07,gen2Q08"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--batches", default=DEFAULT_BATCHES)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--combined", type=Path, required=True)
    parser.add_argument("--run-map", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path):
    raw = path.read_bytes()
    if not raw.strip():
        raise RuntimeError(f"empty JSON: {path}")
    return json.loads(raw)


def atomic_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    return os.fdopen(fd, "wb"), Path(temporary)


def atomic_json(path: Path, value: object) -> None:
    handle, temporary = atomic_writer(path)
    try:
        with handle:
            handle.write(
                (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
            )
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def count_lines(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def exact_prefix(prefix: Path, combined: Path) -> bool:
    remaining = prefix.stat().st_size
    with prefix.open("rb") as left, combined.open("rb") as right:
        while remaining:
            block_size = min(1024 * 1024, remaining)
            if left.read(block_size) != right.read(block_size):
                return False
            remaining -= block_size
    return True


def safe_card_dict(card, run_id: str, source: dict) -> tuple[dict, bool]:
    row = card.to_json()
    label = row.get("label") or {}
    values = (label.get("graded"), label.get("y_norm"))
    invalid = any(
        value is not None
        and (not isinstance(value, (int, float)) or not math.isfinite(float(value)))
        for value in values
    )
    if invalid:
        label.update({"graded": None, "y_norm": None, "medal_bucket": "invalid"})
        row["label"] = label
    row["run_id"] = run_id
    row["provenance"] = {
        "collection_source": source,
        "label_status": "quarantined:nonfinite_label" if invalid else "finite",
        "run_id_source": "pool-manifest:experiment-dir",
        "task_type_source": "phase1.build_cards:TASK_TYPE",
    }
    return row, invalid


def main() -> None:
    args = parse_args()
    batches = tuple(item.strip() for item in args.batches.split(",") if item.strip())
    if len(batches) != len(set(batches)):
        raise RuntimeError("duplicate batch names")

    base_rows: list[bytes] = []
    base_ids: set[str] = set()
    run_map: dict[str, str] = {}
    with args.base.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            card_id = row["id"]
            if card_id in base_ids:
                raise RuntimeError(f"duplicate base id at line {line_number}: {card_id}")
            if not row.get("run_id"):
                raise RuntimeError(f"base card lacks run_id at line {line_number}: {card_id}")
            base_ids.add(card_id)
            run_map[card_id] = row["run_id"]
            base_rows.append(line if line.endswith(b"\n") else line + b"\n")

    accepted_runs: list[dict] = []
    rejected_runs: list[dict] = []
    extension_rows: list[dict] = []
    extension_ids: set[str] = set()
    per_task_cards: Counter[str] = Counter()
    per_task_runs: Counter[str] = Counter()
    quarantined = 0

    for batch in batches:
        root = args.runs_root / f"user_yzyang4_issue_mcts_data_{batch}"
        manifests = sorted(root.glob("srun_pool/*/manifest.json"))
        if len(manifests) != 1:
            raise RuntimeError(f"{batch}: expected one manifest, found {len(manifests)}")
        manifest_path = manifests[0]
        manifest = load_json(manifest_path)
        for task_id, meta in sorted(manifest["tasks"].items()):
            exp = Path(meta["experiment_dir"])
            base_record = {
                "batch": batch,
                "task_id": task_id,
                "task": meta.get("task_name"),
                "manifest_status": meta.get("status"),
                "manifest_exit": meta.get("exit_code"),
                "manifest_sha256": sha256(manifest_path),
                "experiment_dir": str(exp),
            }
            reasons: list[str] = []
            if meta.get("status") != "completed":
                reasons.append("manifest_not_completed")
            if meta.get("exit_code") != 0:
                reasons.append("manifest_nonzero_exit")

            journal = exp / "checkpoint/journal.jsonl"
            state_path = exp / "checkpoint/state.json"
            searches = sorted(exp.glob("*_MCTS_search_data.json"))
            if not journal.exists() or journal.stat().st_size == 0:
                reasons.append("journal_missing_or_empty")
            if not state_path.exists() or state_path.stat().st_size == 0:
                reasons.append("state_missing_or_empty")
            if len(searches) != 1:
                reasons.append(f"final_search_count_{len(searches)}")

            journal_lines = count_lines(journal) if journal.exists() else 0
            state = None
            search = None
            if not reasons:
                state = load_json(state_path)
                search = load_json(searches[0])
                if not isinstance(search, dict) or not isinstance(search.get("nodes"), list):
                    reasons.append("invalid_search_shape")
                elif len(search["nodes"]) != journal_lines:
                    reasons.append("search_journal_count_mismatch")
                if state.get("current_step") != journal_lines:
                    reasons.append("state_journal_count_mismatch")

            if reasons:
                rejected_runs.append({**base_record, "reasons": reasons, "journal_lines": journal_lines})
                continue

            competition = _peek_competition(str(journal))
            if competition is not None and competition != meta.get("task_name"):
                raise RuntimeError(
                    f"task mismatch for {task_id}: manifest={meta.get('task_name')} journal={competition}"
                )
            competition = meta.get("task_name")
            if competition not in TASK_TYPE:
                raise RuntimeError(f"unknown task type: {competition}")
            task = TaskInfo(name=competition, type=TASK_TYPE[competition], metric="", desc=competition)
            cards = parse_journal(str(journal), task)
            run_id = f"exploratory-20260812:{batch}:{task_id}"
            new_count = 0
            finite_count = 0
            pending_rows: list[dict] = []
            pending_ids: set[str] = set()
            for card in cards:
                if card.y is None:
                    continue
                if card.id in base_ids or card.id in extension_ids or card.id in pending_ids:
                    raise RuntimeError(f"card id collision: {card.id}")
                row, invalid = safe_card_dict(
                    card,
                    run_id,
                    {
                        "batch": batch,
                        "task_id": task_id,
                        "journal_sha256": sha256(journal),
                        "search_sha256": sha256(searches[0]),
                    },
                )
                pending_rows.append(row)
                pending_ids.add(card.id)
                new_count += 1
                finite_count += int(not invalid)
            if finite_count == 0:
                rejected_runs.append(
                    {
                        **base_record,
                        "reasons": ["zero_usable_finite_labels"],
                        "journal_lines": journal_lines,
                        "raw_labeled_cards": new_count,
                    }
                )
                continue
            for row in pending_rows:
                extension_ids.add(row["id"])
                run_map[row["id"]] = run_id
                extension_rows.append(row)
                per_task_cards[competition] += 1
                quarantined += int((row.get("provenance") or {}).get("label_status") != "finite")
            per_task_runs[competition] += 1
            accepted_runs.append(
                {
                    **base_record,
                    "journal_lines": journal_lines,
                    "labeled_cards": new_count,
                    "finite_labeled_cards": finite_count,
                    "state_current_step": state["current_step"],
                    "journal_sha256": sha256(journal),
                    "search_sha256": sha256(searches[0]),
                    "run_id": run_id,
                }
            )

    extension_rows.sort(key=lambda row: (row["run_id"], row["lineage"].get("step") or 0, row["id"]))
    for row in extension_rows:
        parent = (row.get("lineage") or {}).get("parent_id")
        if parent in extension_ids and run_map[parent] != row["run_id"]:
            raise RuntimeError(f"cross-run parent edge: {parent} -> {row['id']}")

    extension_handle, extension_temporary = atomic_writer(args.extension)
    try:
        with extension_handle:
            for row in extension_rows:
                extension_handle.write(
                    (json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode()
                )
        os.replace(extension_temporary, args.extension)
    except BaseException:
        extension_temporary.unlink(missing_ok=True)
        raise

    combined_handle, combined_temporary = atomic_writer(args.combined)
    try:
        with combined_handle, args.extension.open("rb") as extension_handle:
            for line in base_rows:
                combined_handle.write(line)
            for block in iter(lambda: extension_handle.read(1024 * 1024), b""):
                combined_handle.write(block)
        os.replace(combined_temporary, args.combined)
    except BaseException:
        combined_temporary.unlink(missing_ok=True)
        raise

    audit = {
        "status": "PASS",
        "role": "exploratory_only_not_frozen_confirmation",
        "acceptance_rule": (
            "manifest completed+exit0; nonempty journal/state; exactly one parseable final "
            "search; state/search node counts equal journal"
        ),
        "base": {
            "path": str(args.base),
            "cards": len(base_ids),
            "sha256": sha256(args.base),
        },
        "extension": {
            "path": str(args.extension),
            "cards": len(extension_rows),
            "runs": len(accepted_runs),
            "tasks": len(per_task_runs),
            "quarantined_labels": quarantined,
            "sha256": sha256(args.extension),
        },
        "combined": {
            "path": str(args.combined),
            "cards": len(base_ids) + len(extension_rows),
            "runs": len(set(run_map.values())),
            "sha256": sha256(args.combined),
            "base_is_exact_prefix": exact_prefix(args.base, args.combined),
        },
        "run_map": {
            "path": str(args.run_map),
            "cards": len(run_map),
        },
        "accepted_runs": accepted_runs,
        "rejected_runs": rejected_runs,
        "per_task_cards": dict(sorted(per_task_cards.items())),
        "per_task_runs": dict(sorted(per_task_runs.items())),
    }
    if not audit["combined"]["base_is_exact_prefix"]:
        raise RuntimeError("combined corpus does not preserve base bytes as an exact prefix")
    atomic_json(args.run_map, run_map)
    audit["run_map"]["sha256"] = sha256(args.run_map)
    atomic_json(args.audit, audit)
    print(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
