from __future__ import annotations

import collections
import hashlib
import json
import os
import re
from pathlib import Path


CARDS = Path("/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl")
RUN_MAP = Path("/research/d7/spc/yzyang4/aira-dojo/phase1/card_run_map.json")
OUT = Path("/research/d7/spc/yzyang4/experiments/v11_source_provenance_audit_20260814")
EXPECTED_CARDS_SHA = "6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75"
EXPECTED_RUN_MAP_SHA = "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30"
ROOTS = {
    "ours": Path("/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"),
    "senior_older": Path("/research/d7/spc/yzyang4/external/senior_runs"),
    "senior_0806": Path("/research/d7/spc/yzyang4/external/senior_data/extract_0806"),
    "senior_0807": Path("/research/d7/spc/yzyang4/external/senior_data/extract_0807"),
    "senior_0808": Path("/research/d7/spc/yzyang4/external/senior_data/extract_0808"),
    "senior_0809": Path("/research/d7/spc/yzyang4/external/senior_data/extract_0809"),
    "senior_0810": Path(
        "/research/d7/spc/yzyang4/external/senior_data/extract_0810_codex_20260813"
    ),
    "senior_0811": Path(
        "/research/d7/spc/yzyang4/external/senior_data/extract_0811_codex_20260813_v2"
    ),
}
CREDENTIAL = re.compile(
    rb"(?:^|[^A-Za-z0-9])(?:sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|"
    rb"gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|"
    rb"Bearer\s+[A-Za-z0-9._-]{20,}|BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)"
)


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def canonical_journals(root: Path) -> dict[Path, Path]:
    by_run = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() == "journal.jsonl":
            run_dir = path.parent.parent
            current = by_run.get(run_dir)
            if current is None or ("checkpoint" in path.parts and "checkpoint" not in current.parts):
                by_run[run_dir] = path
    return by_run


def main() -> None:
    if sha256(CARDS) != EXPECTED_CARDS_SHA or sha256(RUN_MAP) != EXPECTED_RUN_MAP_SHA:
        raise RuntimeError("v11 input SHA mismatch")
    if OUT.exists():
        raise FileExistsError(OUT)
    OUT.mkdir(parents=True)

    cards = {}
    wanted = set()
    for line in CARDS.open(encoding="utf-8"):
        row = json.loads(line)
        card_id = str(row["id"])
        cards[card_id] = {
            "task": str(row["task"]["name"]),
            "batch": str(row["run_id"]).split(":", 1)[0],
        }
        wanted.add(card_id)
    heuristic = json.loads(RUN_MAP.read_text(encoding="utf-8"))
    if set(heuristic) != wanted:
        raise RuntimeError("run map coverage mismatch")

    card_sources = collections.defaultdict(set)
    source_paths = collections.defaultdict(set)
    source_cards = collections.defaultdict(set)
    root_stats = {}
    credential_files = []
    for alias, root in ROOTS.items():
        if not root.is_dir():
            root_stats[alias] = {"exists": False}
            continue
        journals = canonical_journals(root)
        matched_journals = matched_cards = 0
        for run_dir, journal in sorted(journals.items(), key=lambda item: str(item[0])):
            blob = journal.read_bytes()
            if CREDENTIAL.search(blob):
                credential_files.append(f"{alias}:{journal.relative_to(root).as_posix()}")
                continue
            journal_sha = sha256_bytes(blob)
            nodes = [json.loads(line) for line in blob.decode("utf-8").splitlines() if line.strip()]
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
            matched_journals += 1
            matched_cards += len(local)
            source_key = journal_sha
            source_paths[source_key].add(f"{alias}:{run_dir.relative_to(root).as_posix()}")
            source_cards[source_key].update(local)
            for card_id in local:
                card_sources[card_id].add(source_key)
        root_stats[alias] = {
            "exists": True,
            "canonical_journals": len(journals),
            "matched_journals": matched_journals,
            "matched_card_occurrences": matched_cards,
        }
        print("ROOT_COMPLETE", alias, json.dumps(root_stats[alias], sort_keys=True), flush=True)

    unique_card_source = {
        card_id: next(iter(sources))
        for card_id, sources in card_sources.items()
        if len(sources) == 1
    }
    collisions = {
        card_id: sorted(source[:16] for source in sources)
        for card_id, sources in card_sources.items()
        if len(sources) > 1
    }
    heuristic_sources = collections.defaultdict(set)
    source_heuristics = collections.defaultdict(set)
    for card_id, source in unique_card_source.items():
        hrun = str(heuristic[card_id])
        heuristic_sources[hrun].add(source)
        source_heuristics[source].add(hrun)
    merges = {key: sorted(value) for key, value in heuristic_sources.items() if len(value) > 1}
    splits = {key: sorted(value) for key, value in source_heuristics.items() if len(value) > 1}

    per_batch = {}
    for batch in sorted({meta["batch"] for meta in cards.values()}):
        batch_ids = {card_id for card_id, meta in cards.items() if meta["batch"] == batch}
        batch_runs = {str(heuristic[card_id]) for card_id in batch_ids}
        covered = batch_ids & set(unique_card_source)
        merged_runs = batch_runs & set(merges)
        split_sources = {
            unique_card_source[card_id]
            for card_id in covered
            if unique_card_source[card_id] in splits
        }
        per_batch[batch] = {
            "cards": len(batch_ids),
            "heuristic_runs": len(batch_runs),
            "source_covered_cards": len(covered),
            "source_coverage": len(covered) / len(batch_ids),
            "merged_heuristic_runs": len(merged_runs),
            "split_source_journals": len(split_sources),
        }

    covered_heuristic_runs = {str(heuristic[card_id]) for card_id in unique_card_source}
    audit = {
        "status": "V11_SOURCE_PROVENANCE_AUDIT_COMPLETE",
        "inputs": {
            "cards_sha256": EXPECTED_CARDS_SHA,
            "run_map_sha256": EXPECTED_RUN_MAP_SHA,
        },
        "inventory": {
            "cards": len(cards),
            "heuristic_runs": len(set(heuristic.values())),
            "source_covered_cards": len(unique_card_source),
            "source_coverage": len(unique_card_source) / len(cards),
            "covered_heuristic_runs": len(covered_heuristic_runs),
            "unique_source_journals": len(source_cards),
            "card_source_collisions": len(collisions),
            "merged_heuristic_runs": len(merges),
            "split_source_journals": len(splits),
            "credential_shape_journals": len(credential_files),
        },
        "root_stats": root_stats,
        "per_batch": per_batch,
        "merged_heuristic_runs": {
            run: {
                "source_journal_sha256": values,
                "source_paths": {
                    source: sorted(source_paths[source]) for source in values
                },
            }
            for run, values in sorted(merges.items())
        },
        "split_source_journals": {
            source: {
                "heuristic_runs": values,
                "source_paths": sorted(source_paths[source]),
            }
            for source, values in sorted(splits.items())
        },
        "card_source_collisions": collisions,
        "credential_shape_journals": credential_files,
        "limitations": [
            "No frozen pair file was opened.",
            "Uncovered cards remain unaudited; absence of a source match is not proof of a bad run id.",
            "Journal SHA collapses exact duplicate copies but is not a universal physical-run identifier.",
        ],
    }
    atomic_json(OUT / "summary.json", audit)
    atomic_json(OUT / "covered_card_source_sha.json", unique_card_source)
    print("AUDIT_COMPLETE", json.dumps(audit["inventory"], sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
