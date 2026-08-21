"""Independently verify the fixed component-split parent-context audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROTOCOL = "component-split-parent-context-independent-verifier-v1"
PRODUCER_PROTOCOL = "component-split-parent-context-audit-v1"
EXPECTED = {
    "cards": ("5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb", 604190866),
    "train": ("0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e", 3208089),
    "dev": ("3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4", 376635),
    "test": ("cb84d78d578e6a3f5378b3396a355fa83880739b4f9af8459d2b960c7ae005da", 381803),
    "draft": ("3ca77a18e224cacbb7f52121d6e8c2b66f17298c68dd06fbc42a14a238ad05b9", 1465008),
    "improve": ("7aca481afda5317fe78a0ad52fc7488fceff7fde6531c74ebb718df9e3b6926e", 1087821),
}


class IndependentVerificationError(RuntimeError):
    """Raised when raw inputs or the producer artifact fail verification."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise IndependentVerificationError(message)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, role: str) -> None:
    expected_sha, expected_size = EXPECTED[role]
    check(path.stat().st_size == expected_size, f"{role} size differs")
    check(sha256_file(path) == expected_sha, f"{role} digest differs")


def identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    try:
        first, second = sorted((row["better"], row["worse"]))
        result = row["task"], row["parent"], first, second
    except (KeyError, TypeError, ValueError) as error:
        raise IndependentVerificationError("malformed pair identity") from error
    check(all(isinstance(item, str) and item for item in result), "empty pair identity")
    check(first != second, "self comparison")
    return result


def pair_rows(path: Path, split: str | None = None) -> list[dict[str, str]]:
    projected = []
    identities = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            check(bool(line.strip()), f"blank line {path.name}:{number}")
            raw = json.loads(line)
            check(isinstance(raw, dict), "pair line is not an object")
            key = identity(raw)
            check(key not in identities, f"duplicate identity in {path.name}")
            identities.add(key)
            if split is not None:
                check(raw.get("intask_split") == split, f"wrong split in {path.name}")
            projected.append(
                {
                    "task": raw["task"],
                    "parent": raw["parent"],
                    "better": raw["better"],
                    "worse": raw["worse"],
                    "src": str(raw.get("src")),
                }
            )
    return projected


def semantic_index(draft: Path, improve: Path) -> dict[tuple[str, str, str, str], str]:
    labels: dict[tuple[str, str, str, str], str] = {}
    for semantic, path in (("Draft", draft), ("Improve", improve)):
        for row in pair_rows(path):
            key = identity(row)
            check(key not in labels, "semantic files overlap")
            labels[key] = semantic
    return labels


def card_index(path: Path, required: set[str]):
    root = json.loads(path.read_text(encoding="utf-8"))
    check(isinstance(root, dict), "Cards root must be an object")
    runs: dict[str, str] = {}
    parents: dict[str, Any] = {}
    code_digests: dict[str, str] = {}
    all_ids = set()
    total = 0
    for run_id, cards in root.items():
        check(isinstance(run_id, str) and isinstance(cards, list), "invalid Cards group")
        for card in cards:
            total += 1
            check(isinstance(card, dict) and isinstance(card.get("id"), str), "invalid card")
            card_id = card["id"]
            check(card_id not in all_ids, "duplicate card id")
            all_ids.add(card_id)
            if card_id in required:
                lineage = card.get("lineage")
                code = card.get("code")
                check(isinstance(lineage, dict) and isinstance(code, str), "card projection missing")
                runs[card_id] = run_id
                parents[card_id] = lineage.get("parent_id")
                code_digests[card_id] = hashlib.sha256(code.encode()).hexdigest()
    check(set(runs) == required, "required card absent")
    return runs, parents, code_digests, {
        "cards": total,
        "run_groups": len(root),
        "needed_cards": len(required),
    }


def parent_keys(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(row["task"], row["parent"]) for row in rows}


def digest_identities(values: set[tuple[str, str]]) -> str:
    return hashlib.sha256(canonical(sorted(values)).encode()).hexdigest()


def overlap(left: str, right: str, pools: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    common = parent_keys(pools[left]) & parent_keys(pools[right])
    return {
        "parents": len(common),
        f"{left}_rows": sum((row["task"], row["parent"]) in common for row in pools[left]),
        f"{right}_rows": sum((row["task"], row["parent"]) in common for row in pools[right]),
        "identity_digest": digest_identities(common),
    }


def characterize(
    rows: list[dict[str, str]],
    run_for: dict[str, str],
    lineage_parent: dict[str, Any],
) -> dict[str, int]:
    result: Counter[str] = Counter()
    for row in rows:
        better, worse, parent = row["better"], row["worse"], row["parent"]
        lineage_matches = sum(lineage_parent[endpoint] == parent for endpoint in (better, worse))
        result["rows"] += 1
        result["same_endpoint_run"] += run_for[better] == run_for[worse]
        result["cross_endpoint_run"] += run_for[better] != run_for[worse]
        result["parent_is_card"] += parent in run_for
        result[{0: "no", 1: "one", 2: "both"}[lineage_matches] + "_lineage_parent_match"] += 1
        result["parent_run_equals_endpoint_run"] += run_for[parent] in {
            run_for[better],
            run_for[worse],
        }
        result["src_" + row["src"]] += 1
    return dict(sorted(result.items()))


def independent_summary(paths: dict[str, Path]) -> dict[str, Any]:
    for role, path in paths.items():
        verify_file(path, role)
    pools = {
        name: pair_rows(paths[name], name)
        for name in ("train", "dev", "test")
    }
    labels = semantic_index(paths["draft"], paths["improve"])
    split_keys = {identity(row) for rows in pools.values() for row in rows}
    check(set(labels) == split_keys, "semantic coverage is not exact")
    required = {
        item
        for rows in pools.values()
        for row in rows
        for item in (row["better"], row["worse"], row["parent"])
    }
    run_for, lineage_parent, code_digest, inventory = card_index(paths["cards"], required)

    outer = pools["train"] + pools["dev"]
    shared = parent_keys(outer) & parent_keys(pools["test"])
    outer_shared = [row for row in outer if (row["task"], row["parent"]) in shared]
    test_shared = [row for row in pools["test"] if (row["task"], row["parent"]) in shared]
    shared_labels = {labels[identity(row)] for row in outer_shared + test_shared}

    split_semantics = {}
    shared_semantics = {}
    for split, rows in pools.items():
        counts = Counter(labels[identity(row)] for row in rows)
        split_semantics[split] = {"rows": len(rows), **dict(sorted(counts.items()))}
        selected = [row for row in rows if (row["task"], row["parent"]) in shared]
        selected_counts = Counter(labels[identity(row)] for row in selected)
        shared_semantics[split] = {
            "rows": len(selected),
            **dict(sorted(selected_counts.items())),
        }

    semantic_overlap = {}
    for label in ("Draft", "Improve"):
        outer_parents = {
            (row["task"], row["parent"])
            for row in outer
            if labels[identity(row)] == label
        }
        test_parents = {
            (row["task"], row["parent"])
            for row in pools["test"]
            if labels[identity(row)] == label
        }
        common = outer_parents & test_parents
        semantic_overlap[label] = {
            "parents": len(common),
            "identity_digest": digest_identities(common),
        }

    endpoint_runs = {
        split: {run_for[row[side]] for row in rows for side in ("better", "worse")}
        for split, rows in pools.items()
    }
    context_runs = {
        split: {run_for[row["parent"]] for row in rows}
        for split, rows in pools.items()
    }
    outer_endpoint_runs = endpoint_runs["train"] | endpoint_runs["dev"]
    outer_context_runs = context_runs["train"] | context_runs["dev"]
    shared_outer_codes = {
        code_digest[row[side]] for row in outer_shared for side in ("better", "worse")
    }
    shared_test_codes = {
        code_digest[row[side]] for row in test_shared for side in ("better", "worse")
    }
    run_overlap = {
        "endpoint_only_outer_train_test": len(outer_endpoint_runs & endpoint_runs["test"]),
        "parent_only_outer_train_test": len(outer_context_runs & context_runs["test"]),
        "endpoint_plus_parent_context_outer_train_test": len(
            (outer_endpoint_runs | outer_context_runs)
            & (endpoint_runs["test"] | context_runs["test"])
        ),
    }
    gates = {
        "endpoint_run_overlap_zero": run_overlap["endpoint_only_outer_train_test"] == 0,
        "outer_test_parent_overlap_nonzero": bool(shared),
        "all_shared_rows_are_draft": shared_labels == {"Draft"},
        "draft_parent_overlap_nonzero": semantic_overlap["Draft"]["parents"] > 0,
        "improve_parent_overlap_zero": semantic_overlap["Improve"]["parents"] == 0,
        "all_shared_parents_resolve_to_cards": all(parent in run_for for _, parent in shared),
        "shared_endpoint_exact_code_overlap_zero": not (shared_outer_codes & shared_test_codes),
        "outcome_aggregates_computed_false": True,
    }
    check(all(gates.values()), "independent fixed gates changed")
    return {
        "protocol": PRODUCER_PROTOCOL,
        "status": "PARENT_CONTEXT_OVERLAP_CONFINED_TO_SYNTHETIC_DRAFT_PENDING_INDEPENDENT_VERIFICATION",
        "inputs": {
            role: {"sha256": EXPECTED[role][0], "bytes": EXPECTED[role][1]}
            for role in paths
        },
        "outcome_fields_used": False,
        "card_inventory": inventory,
        "split_semantic_counts": split_semantics,
        "parent_overlaps": {
            "train_dev": overlap("train", "dev", pools),
            "train_test": overlap("train", "test", pools),
            "dev_test": overlap("dev", "test", pools),
            "outer_train_test": {
                "parents": len(shared),
                "outer_train_rows": len(outer_shared),
                "test_rows": len(test_shared),
                "identity_digest": digest_identities(shared),
            },
        },
        "shared_parent_rows_by_semantic": shared_semantics,
        "same_semantic_parent_overlap": semantic_overlap,
        "shared_parent_characterization": {
            "shared_parents": len(shared),
            "shared_parent_card_presence": sum(parent in run_for for _, parent in shared),
            "outer_train_rows": characterize(outer_shared, run_for, lineage_parent),
            "test_rows": characterize(test_shared, run_for, lineage_parent),
            "exact_endpoint_code_hash_overlap": len(shared_outer_codes & shared_test_codes),
        },
        "run_overlap": run_overlap,
        "gates": gates,
        "pending_independent_verification": True,
        "context_overlap_claim_allowed": False,
    }


def verify(paths: dict[str, Path], producer_path: Path) -> dict[str, Any]:
    expected = independent_summary(paths)
    producer = json.loads(producer_path.read_text(encoding="utf-8"))
    check(isinstance(producer, dict), "producer artifact is not an object")
    check(producer == expected, "producer artifact differs from independent reconstruction")
    return {
        "protocol": PROTOCOL,
        "status": "VERIFIED_PARENT_CONTEXT_OVERLAP_CONFINED_TO_SYNTHETIC_DRAFT",
        "producer_sha256": sha256_file(producer_path),
        "independent_summary_sha256": hashlib.sha256(
            (json.dumps(expected, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
        ).hexdigest(),
        "raw_inputs_recomputed": True,
        "producer_imported": False,
        "outcome_fields_used": False,
        "all_fields_exact_match": True,
        "gates": expected["gates"],
        "context_overlap_claim_allowed": True,
    }


def write_new(path: Path, value: dict[str, Any]) -> None:
    check(not path.exists(), "verification output already exists")
    json.dumps(value, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cards", "train", "dev", "test", "draft", "improve"):
        parser.add_argument(name, type=Path)
    parser.add_argument("producer", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    paths = {name: getattr(args, name) for name in ("cards", "train", "dev", "test", "draft", "improve")}
    receipt = verify(paths, args.producer)
    write_new(args.output, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
