"""Build a deterministic six-card manifest for the late-artifact route pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


LOCKS = {
    "manifest": "77f696828010e2d6ae10a9b9de2d9ec05d44975b1285ea763d9850a7f30ca4ef",
    "results": "b1266d04912596b1e37e13f79ce2387a962f5510cfa264aa1a97b7a1c443180d",
    "runtime": "dff8eb88a1db8d63bab17851c1dce2c1bd389a4744a811d65a5ce1fe5a1f55e7",
    "run_map": "3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30",
}
SEED = "late-artifact-v1|"


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="phase1/fidelity_manifest.jsonl")
    p.add_argument("--results", default="phase1/fidelity_results.jsonl")
    p.add_argument("--runtime", default="phase1/fidelity_runtime_v9.jsonl")
    p.add_argument("--run-map", default="phase1/card_run_map.json")
    p.add_argument("--out", default="phase1/late_artifact_pilot_manifest.jsonl")
    p.add_argument("--audit", default="phase1/late_artifact_pilot_manifest.audit.json")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def rank(card_id: str) -> str:
    return hashlib.sha256((SEED + card_id).encode("utf-8")).hexdigest()


def select(eligible: list[dict[str, Any]], count: int = 6) -> list[dict[str, Any]]:
    chosen = []
    tasks: set[str] = set()
    runs: set[str] = set()
    for row in sorted(eligible, key=lambda item: (rank(str(item["card_id"])), str(item["card_id"]))):
        task = str(row["competition"])
        run_id = str(row["run_id"])
        if task in tasks or run_id in runs:
            continue
        chosen.append(row)
        tasks.add(task)
        runs.add(run_id)
        if len(chosen) == count:
            break
    if len(chosen) != count:
        raise RuntimeError(f"only {len(chosen)} task/run-unique eligible cards")
    return chosen


def self_test() -> None:
    data = [
        {"card_id": f"c{i}", "competition": f"t{i % 3}", "run_id": f"r{i}"}
        for i in range(9)
    ]
    first = select(data, 3)
    second = select(list(reversed(data)), 3)
    assert first == second
    assert len({x["competition"] for x in first}) == 3
    assert len({x["run_id"] for x in first}) == 3
    print("LATE_ARTIFACT_MANIFEST_SELF_TEST_PASS")


def main() -> None:
    a = args()
    if a.self_test:
        self_test()
        return
    paths = {
        "manifest": Path(a.manifest),
        "results": Path(a.results),
        "runtime": Path(a.runtime),
        "run_map": Path(a.run_map),
    }
    observed = {name: digest(path) for name, path in paths.items()}
    if observed != LOCKS:
        raise RuntimeError(observed)
    output, audit_path = Path(a.out), Path(a.audit)
    if output.exists() or audit_path.exists():
        raise FileExistsError("refusing to overwrite pilot manifest/audit")
    nodes_raw = rows(paths["manifest"])
    nodes = {str(row["card_id"]): row for row in nodes_raw}
    if len(nodes) != len(nodes_raw):
        raise RuntimeError("duplicate manifest card")
    result_rows = rows(paths["results"])
    result_keys = [(str(row["card_id"]), int(row["cap"])) for row in result_rows]
    if len(result_keys) != len(set(result_keys)):
        raise RuntimeError("duplicate fidelity result key")
    if set(result_keys) != {(card_id, cap) for card_id in nodes for cap in (30, 120)}:
        raise RuntimeError("fidelity result grid mismatch")
    cap120 = {
        str(row["card_id"]): row for row in result_rows if int(row["cap"]) == 120
    }
    if len(cap120) != len(nodes):
        raise RuntimeError("120-second coverage mismatch")
    runtime_rows = rows(paths["runtime"])
    runtime = {str(row["card_id"]): float(row["runtime_s"]) for row in runtime_rows}
    if len(runtime) != len(runtime_rows) or set(runtime) != set(nodes):
        raise RuntimeError("runtime coverage mismatch")
    run_map = json.loads(paths["run_map"].read_text(encoding="utf-8"))
    if not set(nodes).issubset(run_map):
        raise RuntimeError("run-map coverage mismatch")
    eligible = []
    for card_id, node in nodes.items():
        result = cap120[card_id]
        if result.get("competition") != node.get("competition") or result.get("parent") != node.get("parent"):
            raise RuntimeError(f"metadata mismatch {card_id}")
        if finite(result.get("sub_score")) or runtime[card_id] < 600.0:
            continue
        eligible.append(
            {
                "card_id": card_id,
                "competition": str(node["competition"]),
                "run_id": str(run_map[card_id]),
                "historical_runtime_s": runtime[card_id],
                "hash_rank": rank(card_id),
            }
        )
    chosen = select(eligible)
    with output.open("x", encoding="utf-8", newline="") as f:
        for selected in chosen:
            node = nodes[selected["card_id"]]
            public = {
                "card_id": selected["card_id"],
                "competition": selected["competition"],
                "code": str(node.get("code") or ""),
                "parent": node.get("parent"),
                "stratum": node.get("stratum"),
            }
            if not public["code"]:
                raise RuntimeError(f"empty code {selected['card_id']}")
            f.write(json.dumps(public, ensure_ascii=False, sort_keys=True) + "\n")
    audit = {
        "selection_rule": "prior fresh-120 sub_score nonfinite; historical runtime>=600; sha256(late-artifact-v1|card_id); greedy unique task/run",
        "inputs": observed,
        "eligible_cards": len(eligible),
        "selected_cards": chosen,
        "output_manifest_sha256": digest(output),
        "final_grade_used_for_selection": False,
        "stdout_used_for_selection": False,
    }
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "LATE_ARTIFACT_MANIFEST_BUILT",
        f"eligible={len(eligible)}",
        f"selected={len(chosen)}",
        f"sha256={audit['output_manifest_sha256']}",
    )
    for row in chosen:
        print(
            "SELECTED",
            row["card_id"],
            f"run={row['run_id']}",
            f"runtime={row['historical_runtime_s']:.3f}",
            f"rank={row['hash_rank']}",
        )


if __name__ == "__main__":
    main()
