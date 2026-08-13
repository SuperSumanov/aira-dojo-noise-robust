"""Attach source-truth physical-run IDs before flattening journals into a corpus batch.

The legacy fallback infers boundaries when labeled-card steps fail to increase.  That can
silently merge adjacent runs when the next journal's early steps have no usable labels.
This command instead maps every flattened card back to the exact source journal, assigns
one deterministic run ID per journal, and optionally writes cards carrying those IDs.

It reads only journal JSONL files, never env files, archives, or pair/frozen artifacts.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_cards(path: Path, expected_sha: str) -> tuple[list[dict[str, Any]], str]:
    actual = sha256(path)
    if actual != expected_sha.lower():
        raise IntegrityError("cards SHA mismatch")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    ids = [str(row["id"]) for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise IntegrityError("cards are empty or IDs are not unique")
    return rows, actual


def canonical_journals(root: Path) -> list[Path]:
    by_run: dict[Path, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.name.lower() != "journal.jsonl":
            continue
        run_dir = path.parent.parent
        current = by_run.get(run_dir)
        if current is None or ("checkpoint" in path.parts and "checkpoint" not in current.parts):
            by_run[run_dir] = path
    return [by_run[key] for key in sorted(by_run, key=lambda item: item.as_posix())]


def source_index(
    rows: Iterable[dict[str, Any]], journals_root: Path
) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[str, Any]]:
    wanted = {str(row["id"]) for row in rows}
    sources_for_card: dict[str, set[str]] = collections.defaultdict(set)
    journal_meta: dict[str, dict[str, Any]] = {}
    credential_files = 0
    scanned = canonical_journals(journals_root)
    for journal in scanned:
        blob = journal.read_bytes()
        if CREDENTIAL.search(blob):
            credential_files += 1
            continue
        nodes = [json.loads(line) for line in blob.decode("utf-8").splitlines() if line]
        task = next(
            (
                str((node.get("metric_info") or {})["competition_id"])
                for node in nodes
                if (node.get("metric_info") or {}).get("competition_id")
            ),
            None,
        )
        if task is None:
            continue
        local = set()
        for node in nodes:
            card_id = f"{task}__{node.get('id', node.get('step'))}"
            if card_id in wanted:
                local.add(card_id)
        if not local:
            continue
        relative = journal.relative_to(journals_root).as_posix()
        journal_meta[relative] = {
            "source_journal": relative,
            "source_journal_sha256": hashlib.sha256(blob).hexdigest(),
            "cards": len(local),
            "task": task,
        }
        for card_id in local:
            sources_for_card[card_id].add(relative)
    collisions = {key: sorted(value) for key, value in sources_for_card.items() if len(value) != 1}
    missing = sorted(wanted - set(sources_for_card))
    if credential_files:
        raise IntegrityError(f"credential shapes found in {credential_files} source journals")
    if collisions or missing:
        raise IntegrityError(
            f"card-to-journal mapping not exact: collisions={len(collisions)} missing={len(missing)}"
        )
    card_source = {key: next(iter(value)) for key, value in sources_for_card.items()}
    if set(card_source.values()) != set(journal_meta):
        raise IntegrityError("matched journal without cards after indexing")
    audit = {
        "canonical_journals_scanned": len(scanned),
        "matched_journals": len(journal_meta),
        "mapped_cards": len(card_source),
        "credential_shape_journals": credential_files,
        "source_collisions": 0,
        "source_missing_cards": 0,
    }
    return card_source, journal_meta, audit


def assign_runs(
    rows: list[dict[str, Any]], card_source: dict[str, str], batch_name: str
) -> tuple[dict[str, str], dict[str, dict[str, Any]], dict[str, Any]]:
    if Path(batch_name).name != batch_name or not batch_name.endswith(".jsonl"):
        raise IntegrityError("batch name must be a plain JSONL filename")
    sources = sorted(set(card_source.values()))
    source_to_run = {source: f"{batch_name}:{index}" for index, source in enumerate(sources)}
    run_map = {card_id: source_to_run[source] for card_id, source in card_source.items()}
    run_tasks: dict[str, set[str]] = collections.defaultdict(set)
    parent_cross_run = 0
    by_id = {str(row["id"]): row for row in rows}
    for card_id, row in by_id.items():
        run_id = run_map[card_id]
        run_tasks[run_id].add(str(row["task"]["name"]))
        parent = row.get("lineage", {}).get("parent_id")
        if parent and parent in by_id and run_map[str(parent)] != run_id:
            parent_cross_run += 1
    if parent_cross_run or any(len(value) != 1 for value in run_tasks.values()):
        raise IntegrityError("source-truth run failed parent/task validation")
    provenance = {
        source_to_run[source]: {"source_journal": source} for source in sources
    }
    return run_map, provenance, {
        "runs": len(sources),
        "parent_cross_run_violations": parent_cross_run,
        "mixed_task_runs": sum(len(value) != 1 for value in run_tasks.values()),
    }


def compare_heuristic(path: Path | None, source_map: dict[str, str]) -> dict[str, Any]:
    if path is None:
        return {"provided": False}
    heuristic = json.loads(path.read_text(encoding="utf-8"))
    if set(heuristic) != set(source_map):
        raise IntegrityError("heuristic map coverage mismatch")
    heuristic_sources: dict[str, set[str]] = collections.defaultdict(set)
    source_heuristics: dict[str, set[str]] = collections.defaultdict(set)
    for card_id, source_run in source_map.items():
        heuristic_run = str(heuristic[card_id])
        heuristic_sources[heuristic_run].add(source_run)
        source_heuristics[source_run].add(heuristic_run)
    merged = {key: sorted(value) for key, value in heuristic_sources.items() if len(value) > 1}
    split = {key: sorted(value) for key, value in source_heuristics.items() if len(value) > 1}
    return {
        "provided": True,
        "heuristic_runs": len(set(heuristic.values())),
        "source_runs": len(set(source_map.values())),
        "merged_heuristic_runs": merged,
        "split_source_runs": split,
    }


def write_cards(
    path: Path,
    rows: list[dict[str, Any]],
    run_map: dict[str, str],
    provenance: dict[str, dict[str, Any]],
    journal_meta: dict[str, dict[str, Any]],
) -> str:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    source_by_run = {run: item["source_journal"] for run, item in provenance.items()}
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            card_id = str(row["id"])
            run_id = run_map[card_id]
            source = source_by_run[run_id]
            row["run_id"] = run_id
            card_provenance = row.setdefault("provenance", {})
            card_provenance["run_id_source"] = "source-journal-path:pre-flattening"
            card_provenance["source_journal_sha256"] = journal_meta[source][
                "source_journal_sha256"
            ]
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    os.replace(temporary, path)
    return sha256(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--journals-root", required=True, type=Path)
    parser.add_argument("--batch-name", required=True)
    parser.add_argument("--expect-cards-sha256", required=True)
    parser.add_argument("--expect-cards", required=True, type=int)
    parser.add_argument("--expect-runs", required=True, type=int)
    parser.add_argument("--heuristic-run-map", type=Path)
    parser.add_argument("--out-cards", required=True, type=Path)
    parser.add_argument("--out-run-map", required=True, type=Path)
    parser.add_argument("--out-run-provenance", required=True, type=Path)
    parser.add_argument("--out-summary", required=True, type=Path)
    args = parser.parse_args()

    rows, cards_sha = load_cards(args.cards, args.expect_cards_sha256)
    card_source, journal_meta, source_audit = source_index(rows, args.journals_root)
    run_map, provenance, run_audit = assign_runs(rows, card_source, args.batch_name)
    heuristic_audit = compare_heuristic(args.heuristic_run_map, run_map)
    integrity = {
        "cards_expected": len(rows) == args.expect_cards,
        "runs_expected": len(set(run_map.values())) == args.expect_runs,
        "source_map_exact": len(card_source) == len(rows),
        "parent_cross_run_zero": run_audit["parent_cross_run_violations"] == 0,
        "mixed_task_runs_zero": run_audit["mixed_task_runs"] == 0,
    }
    if not all(integrity.values()):
        raise IntegrityError(f"source-truth inventory gate failed: {integrity}")
    output_sha = write_cards(
        args.out_cards, rows, run_map, provenance, journal_meta
    )
    for run_id, item in provenance.items():
        source = item["source_journal"]
        item.update(journal_meta[source])
    summary = {
        "status": "SOURCE_JOURNAL_RUN_IDS_COMPLETE",
        "inputs": {
            "cards_sha256": cards_sha,
            "journals_root": str(args.journals_root),
            "batch_name": args.batch_name,
        },
        "inventory": {
            "cards": len(rows),
            "tasks": len({str(row["task"]["name"]) for row in rows}),
            "runs": len(set(run_map.values())),
        },
        "source_audit": source_audit,
        "run_audit": run_audit,
        "heuristic_audit": heuristic_audit,
        "integrity": integrity,
        "outputs": {
            "cards_sha256": output_sha,
        },
    }
    atomic_json(args.out_run_map, run_map)
    atomic_json(args.out_run_provenance, provenance)
    atomic_json(args.out_summary, summary)
    print(
        summary["status"],
        f"cards={len(rows)}",
        f"runs={len(set(run_map.values()))}",
        f"merged_heuristic_runs={len(heuristic_audit.get('merged_heuristic_runs', {}))}",
        f"split_source_runs={len(heuristic_audit.get('split_source_runs', {}))}",
        f"output_sha256={output_sha}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
