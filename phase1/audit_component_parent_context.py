"""Audit ancestor-parent context overlap in the fixed component critic split."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "component-split-parent-context-audit-v1"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
    "test": ("cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da", 381803),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}


class ParentAuditError(RuntimeError):
    """Raised when an input or structural invariant fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ParentAuditError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def verify_identity(path: Path, role: str) -> None:
    expected_hash, expected_bytes = EXPECTED[role]
    require(path.stat().st_size == expected_bytes, f"{role} byte count mismatch")
    require(sha256_file(path) == expected_hash, f"{role} SHA-256 mismatch")


def pair_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        left, right = sorted((row["better"], row["worse"]))
        values = row["task"], row["parent"], left, right
    except (KeyError, TypeError, ValueError) as error:
        raise ParentAuditError("invalid pair identity") from error
    require(all(isinstance(value, str) and value for value in values), "empty pair identity")
    require(left != right, "self pair")
    return values


def read_pairs(path: Path, expected_split: str | None = None) -> list[dict[str, str]]:
    rows = []
    seen = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank row at {path.name}:{line_number}")
            source = json.loads(line)
            require(isinstance(source, dict), "pair row is not an object")
            key = pair_key(source)
            require(key not in seen, f"duplicate pair in {path.name}")
            seen.add(key)
            if expected_split is not None:
                require(source.get("intask_split") == expected_split, f"split mismatch in {path.name}")
            rows.append({
                "task": source["task"],
                "parent": source["parent"],
                "better": source["better"],
                "worse": source["worse"],
                "src": str(source.get("src")),
            })
    return rows


def load_semantics(draft_path: Path, improve_path: Path) -> dict[tuple[str, str, str, str], str]:
    output = {}
    for label, path in (("Draft", draft_path), ("Improve", improve_path)):
        for row in read_pairs(path):
            key = pair_key(row)
            require(key not in output, "Draft/Improve identity overlap")
            output[key] = label
    return output


def load_card_projection(path: Path, needed: set[str]):
    grouped = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(grouped, dict), "Cards root is not grouped")
    run_of = {}
    lineage_parent_of = {}
    code_hash_of = {}
    seen = set()
    total = 0
    for run_id, cards in grouped.items():
        require(isinstance(run_id, str) and isinstance(cards, list), "invalid card group")
        for card in cards:
            total += 1
            require(isinstance(card, dict) and isinstance(card.get("id"), str), "invalid card")
            card_id = card["id"]
            require(card_id not in seen, "duplicate card id")
            seen.add(card_id)
            if card_id not in needed:
                continue
            lineage = card.get("lineage")
            code = card.get("code")
            require(isinstance(lineage, dict) and isinstance(code, str), "needed card lacks code/lineage")
            run_of[card_id] = run_id
            lineage_parent_of[card_id] = lineage.get("parent_id")
            code_hash_of[card_id] = hashlib.sha256(code.encode()).hexdigest()
    require(set(run_of) == needed, "needed endpoint or parent card missing")
    return run_of, lineage_parent_of, code_hash_of, {
        "cards": total, "run_groups": len(grouped), "needed_cards": len(needed)
    }


def parent_set(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row["task"], row["parent"]) for row in rows}


def overlap_receipt(
    left_name: str,
    right_name: str,
    rows: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    shared = parent_set(rows[left_name]) & parent_set(rows[right_name])
    return {
        "parents": len(shared),
        f"{left_name}_rows": sum((row["task"], row["parent"]) in shared for row in rows[left_name]),
        f"{right_name}_rows": sum((row["task"], row["parent"]) in shared for row in rows[right_name]),
        "identity_digest": hashlib.sha256(compact(sorted(shared)).encode()).hexdigest(),
    }


def describe_rows(
    rows: list[dict[str, str]],
    run_of: dict[str, str],
    lineage_parent_of: dict[str, Any],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        better, worse, parent = row["better"], row["worse"], row["parent"]
        matches = int(lineage_parent_of[better] == parent) + int(lineage_parent_of[worse] == parent)
        counts["rows"] += 1
        counts["same_endpoint_run"] += run_of[better] == run_of[worse]
        counts["cross_endpoint_run"] += run_of[better] != run_of[worse]
        counts["parent_is_card"] += parent in run_of
        counts[("no", "one", "both")[matches] + "_lineage_parent_match"] += 1
        counts["parent_run_equals_endpoint_run"] += run_of[parent] in {run_of[better], run_of[worse]}
        counts["src_" + row["src"]] += 1
    return dict(sorted(counts.items()))


def analyze(
    cards_path: Path,
    train_path: Path,
    dev_path: Path,
    test_path: Path,
    draft_path: Path,
    improve_path: Path,
) -> dict[str, Any]:
    paths = {
        "cards": cards_path, "train": train_path, "dev": dev_path, "test": test_path,
        "draft": draft_path, "improve": improve_path,
    }
    for role, path in paths.items():
        verify_identity(path, role)
    pools = {
        "train": read_pairs(train_path, "train"),
        "dev": read_pairs(dev_path, "dev"),
        "test": read_pairs(test_path, "test"),
    }
    semantics = load_semantics(draft_path, improve_path)
    all_keys = {pair_key(row) for split_rows in pools.values() for row in split_rows}
    require(set(semantics) == all_keys, "semantic map does not exactly cover split pairs")
    needed = {
        identity
        for split_rows in pools.values()
        for row in split_rows
        for identity in (row["better"], row["worse"], row["parent"])
    }
    run_of, lineage_parent_of, code_hash_of, card_inventory = load_card_projection(cards_path, needed)

    outer_rows = pools["train"] + pools["dev"]
    outer_parent_set = parent_set(outer_rows)
    test_parent_set = parent_set(pools["test"])
    shared = outer_parent_set & test_parent_set
    shared_outer_rows = [row for row in outer_rows if (row["task"], row["parent"]) in shared]
    shared_test_rows = [row for row in pools["test"] if (row["task"], row["parent"]) in shared]
    shared_semantics = {
        semantics[pair_key(row)] for row in (*shared_outer_rows, *shared_test_rows)
    }

    semantic_counts = {
        split: {
            "rows": len(split_rows),
            **dict(sorted(Counter(semantics[pair_key(row)] for row in split_rows).items())),
        }
        for split, split_rows in pools.items()
    }
    shared_semantic_rows = {
        split: {
            "rows": len(selected := [
                row for row in split_rows if (row["task"], row["parent"]) in shared
            ]),
            **dict(sorted(Counter(semantics[pair_key(row)] for row in selected).items())),
        }
        for split, split_rows in pools.items()
    }
    same_semantic_parent_overlap = {}
    for label in ("Draft", "Improve"):
        outer = {
            (row["task"], row["parent"]) for row in outer_rows
            if semantics[pair_key(row)] == label
        }
        test = {
            (row["task"], row["parent"]) for row in pools["test"]
            if semantics[pair_key(row)] == label
        }
        overlap = outer & test
        same_semantic_parent_overlap[label] = {
            "parents": len(overlap),
            "identity_digest": hashlib.sha256(compact(sorted(overlap)).encode()).hexdigest(),
        }

    endpoint_runs = {
        split: {run_of[row[side]] for row in split_rows for side in ("better", "worse")}
        for split, split_rows in pools.items()
    }
    parent_runs = {
        split: {run_of[row["parent"]] for row in split_rows}
        for split, split_rows in pools.items()
    }
    outer_endpoint_runs = endpoint_runs["train"] | endpoint_runs["dev"]
    outer_parent_runs = parent_runs["train"] | parent_runs["dev"]
    outer_codes = {
        code_hash_of[row[side]] for row in shared_outer_rows for side in ("better", "worse")
    }
    test_codes = {
        code_hash_of[row[side]] for row in shared_test_rows for side in ("better", "worse")
    }
    overlaps = {
        "train_dev": overlap_receipt("train", "dev", pools),
        "train_test": overlap_receipt("train", "test", pools),
        "dev_test": overlap_receipt("dev", "test", pools),
        "outer_train_test": {
            "parents": len(shared),
            "outer_train_rows": len(shared_outer_rows),
            "test_rows": len(shared_test_rows),
            "identity_digest": hashlib.sha256(compact(sorted(shared)).encode()).hexdigest(),
        },
    }
    run_overlap = {
        "endpoint_only_outer_train_test": len(outer_endpoint_runs & endpoint_runs["test"]),
        "parent_only_outer_train_test": len(outer_parent_runs & parent_runs["test"]),
        "endpoint_plus_parent_context_outer_train_test": len(
            (outer_endpoint_runs | outer_parent_runs)
            & (endpoint_runs["test"] | parent_runs["test"])
        ),
    }
    gates = {
        "endpoint_run_overlap_zero": run_overlap["endpoint_only_outer_train_test"] == 0,
        "outer_test_parent_overlap_nonzero": len(shared) > 0,
        "all_shared_rows_are_draft": shared_semantics == {"Draft"},
        "draft_parent_overlap_nonzero": same_semantic_parent_overlap["Draft"]["parents"] > 0,
        "improve_parent_overlap_zero": same_semantic_parent_overlap["Improve"]["parents"] == 0,
        "all_shared_parents_resolve_to_cards": all(parent in run_of for _, parent in shared),
        "shared_endpoint_exact_code_overlap_zero": len(outer_codes & test_codes) == 0,
        "outcome_aggregates_computed_false": True,
    }
    require(all(gates.values()), "fixed parent-context structural gates changed")
    return {
        "protocol": PROTOCOL,
        "status": "PARENT_CONTEXT_OVERLAP_CONFINED_TO_SYNTHETIC_DRAFT_PENDING_INDEPENDENT_VERIFICATION",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in paths
        },
        "outcome_fields_used": False,
        "card_inventory": card_inventory,
        "split_semantic_counts": semantic_counts,
        "parent_overlaps": overlaps,
        "shared_parent_rows_by_semantic": shared_semantic_rows,
        "same_semantic_parent_overlap": same_semantic_parent_overlap,
        "shared_parent_characterization": {
            "shared_parents": len(shared),
            "shared_parent_card_presence": sum(parent in run_of for _, parent in shared),
            "outer_train_rows": describe_rows(shared_outer_rows, run_of, lineage_parent_of),
            "test_rows": describe_rows(shared_test_rows, run_of, lineage_parent_of),
            "exact_endpoint_code_hash_overlap": len(outer_codes & test_codes),
        },
        "run_overlap": run_overlap,
        "gates": gates,
        "pending_independent_verification": True,
        "context_overlap_claim_allowed": False,
    }


def write_output(path: Path, summary: dict[str, Any]) -> None:
    require(not path.exists(), "output already exists")
    json.dumps(summary, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cards", "train", "dev", "test", "draft", "improve", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    summary = analyze(args.cards, args.train, args.dev, args.test, args.draft, args.improve)
    write_output(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
