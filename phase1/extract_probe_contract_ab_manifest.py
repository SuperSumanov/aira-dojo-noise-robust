#!/usr/bin/env python3
"""Freeze every A/B leaf for one independent continuous replay."""

from __future__ import annotations

import argparse
import ast
import json
import os
import tempfile
from pathlib import Path

from phase1.build_schema_probe_repair_manifest import validate_topology
from phase1.extract_schema_probe_manifest import static_contract
from phase1.probe_contract_ab_common import MATRIX, SEED, atomic_json, row_for_index, sha256_file, sha256_text


def atomic_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.audit.exists():
        raise RuntimeError("refusing existing A/B extraction outputs")
    generation = json.loads(args.generation_manifest.read_text(encoding="utf-8"))
    source_rows = generation.get("rows")
    if (
        generation.get("experiment") != "probe_contract_ab_safety_v1"
        or generation.get("seed") != SEED
        or not isinstance(source_rows, list)
        or len(source_rows) != len(MATRIX)
    ):
        raise RuntimeError("generation manifest identity/grid mismatch")

    replay_rows: list[dict] = []
    audit_rows: list[dict] = []
    for source in sorted(source_rows, key=lambda row: row.get("index", -1)):
        index = int(source.get("index", -1))
        expected = row_for_index(index)
        if any(source.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"generation row differs from frozen matrix: {index}")
        export_path = Path(source["source_export"])
        if sha256_file(export_path) != source["source_export_sha256"]:
            raise RuntimeError(f"source export hash drift: {index}")
        experiment_dir = Path(source["experiment_dir"])
        journals = sorted(experiment_dir.glob("checkpoint/journal.jsonl"))
        states = sorted(experiment_dir.glob("checkpoint/state.json"))
        if len(journals) != 1 or len(states) != 1:
            raise RuntimeError(f"missing generation checkpoint: {index}")
        export = json.loads(export_path.read_text(encoding="utf-8"))
        state = json.loads(states[0].read_text(encoding="utf-8"))
        journal_lines = sum(bool(line.strip()) for line in journals[0].read_text(encoding="utf-8").splitlines())
        mode, code_nodes, selected = validate_topology(
            export.get("nodes") if isinstance(export, dict) else None,
            journal_lines=journal_lines,
            current_step=int(state.get("current_step", -1)),
        )
        if mode != source["topology_mode"] or str(selected.get("id", "")) != source["selected_node_id"]:
            raise RuntimeError(f"selected topology drift: {index}")
        code = str(selected["code"])
        code_sha = sha256_text(code)
        syntax_valid = True
        try:
            ast.parse(code)
        except SyntaxError:
            syntax_valid = False
        contract_checks = static_contract(code)
        audit_rows.append(
            {
                **expected,
                "source_export": str(export_path),
                "source_export_sha256": source["source_export_sha256"],
                "topology_mode": mode,
                "code_nodes": len(code_nodes),
                "selected_node_id": source["selected_node_id"],
                "selected_node_is_buggy": selected.get("is_buggy"),
                "code_sha256": code_sha,
                "code_bytes": len(code.encode("utf-8")),
                "python_ast_parse": syntax_valid,
                "static_contract": contract_checks,
            }
        )
        replay_rows.append(
            {
                "schema_version": 1,
                "card_id": (
                    f"probe_contract_ab|{expected['task']}|{expected['arm']}|"
                    f"seed={SEED}|node={source['selected_node_id']}"
                ),
                **expected,
                "competition": expected["task"],
                "code": code,
                "code_sha256": code_sha,
                "generation_topology_mode": mode,
                "generation_node_is_buggy": selected.get("is_buggy"),
                "source_task_id": source["task_id"],
                "source_export": str(export_path),
                "source_export_sha256": source["source_export_sha256"],
                "source_generation_manifest": str(args.generation_manifest),
                "source_generation_manifest_sha256": sha256_file(args.generation_manifest),
            }
        )

    if [row["index"] for row in replay_rows] != list(range(len(MATRIX))):
        raise RuntimeError("replay row ordering mismatch")
    atomic_jsonl(args.out, replay_rows)
    audit = {
        "schema_version": 1,
        "experiment": "probe_contract_ab_safety_v1",
        "seed": SEED,
        "source_generation_manifest": str(args.generation_manifest),
        "source_generation_manifest_sha256": sha256_file(args.generation_manifest),
        "rows": audit_rows,
        "python_ast_parse_rows": sum(row["python_ast_parse"] for row in audit_rows),
        "contract_static_pass_rows": sum(
            row["arm"] == "contract" and row["static_contract"].get("required_pass") is True
            for row in audit_rows
        ),
        "replay_manifest": str(args.out),
        "replay_manifest_sha256": sha256_file(args.out),
    }
    atomic_json(args.audit, audit)
    print(
        "PROBE_CONTRACT_AB_EXTRACTION_PASS "
        f"rows={len(replay_rows)} ast={audit['python_ast_parse_rows']} "
        f"contract_static={audit['contract_static_pass_rows']}/{len(MATRIX) // 2} "
        f"manifest_sha256={audit['replay_manifest_sha256']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
