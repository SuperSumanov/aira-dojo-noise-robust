"""Check the pinned senior current-score target on synthetic Cards only.

This is a source-contract check, not a data builder or a lookahead experiment.
Only budget_steps=-1 is executed. No corpus, private config, model, or outcome
is opened. The source is credential-scanned before parsing; its CLI and data
loader are not compiled. Nothing here certifies a published data artifact.
"""
from __future__ import annotations

import ast
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace


REPO = "/research/d7/spc/yzyang4/aira-dojo-reproduce"
COMMIT = "b8d095180415957aa1bab31fa53ead1bba261c03"
SOURCE = "src/mle_critic/src/preprocess/build_bt_pairs/build_subtree_pairs.py"
SOURCE_SHA = "3121b14703bcb67007c8070adb6e7a7dd8d4844c00a9d7de8621161fce7a73cf"
SECRET = re.compile(
    rb"(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    rb"hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
DEFINITIONS = {
    "Descendant", "NodeValue", "flatten_runs", "build_children_index",
    "runtime_seconds", "find_descendants", "is_within_budget", "graded_score",
    "compute_node_values", "validate_task_directions", "current_quality_agreement",
    "make_pair_record", "build_value_pairs",
}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def load_pinned_functions():
    raw = subprocess.check_output(["git", "-C", REPO, "show", COMMIT + ":" + SOURCE])
    require(hashlib.sha256(raw).hexdigest() == SOURCE_SHA, "pinned_source_drift")
    require(not SECRET.search(raw), "credential_shape_source_withheld")
    tree = ast.parse(raw)
    definitions = [node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in DEFINITIONS]
    require({node.name for node in definitions} == DEFINITIONS, "source_definitions_missing")
    # Import only stdlib dependencies of the exact function/class bodies. Never
    # import the upstream Cards loader or compile its main()/argument parser.
    imports = ast.parse(
        "from __future__ import annotations\n"
        "import itertools, math, random\n"
        "from collections import defaultdict\n"
        "from dataclasses import dataclass\n"
        "from typing import Iterable, Mapping, Sequence\n"
    ).body
    namespace = {"__name__": __name__}
    exec(compile(ast.Module(body=imports + definitions, type_ignores=[]), SOURCE, "exec"), namespace)
    return namespace


def card(name, task, higher, grade, parent=None):
    return SimpleNamespace(
        id=name, task=SimpleNamespace(name=task, higher_is_better=higher),
        label=SimpleNamespace(graded=grade), lineage=SimpleNamespace(parent_id=parent),
        obs=SimpleNamespace(runtime_s=1.0),
    )


def fixture():
    # Deliberately stronger descendants cannot alter a parent's -1 target.
    # A leaf, an unlabelled connector, ties and a nonfinite label are included.
    runs = {}
    for task, higher, values in (
        ("synthetic-max", True, (0.2, 0.8, 0.95, 0.1)),
        ("synthetic-min", False, (0.8, 0.2, 0.05, 0.9)),
    ):
        a, b, c, d = (task + suffix for suffix in ("-a", "-b", "-c", "-d"))
        connector = task + "-unlabelled"
        runs[task + "-run-a"] = [
            card(a, task, higher, values[0]),
            card(connector, task, higher, None, a),
            card(c, task, higher, values[2], connector),
        ]
        runs[task + "-run-b"] = [
            card(b, task, higher, values[1]), card(d, task, higher, values[3], b),
            card(task + "-tie", task, higher, values[1]),
            card(task + "-nan", task, higher, float("nan")),
        ]
    return runs


def independent_current_pairs(runs):
    # Deliberately independent of the upstream grading, tree and orientation
    # helpers: direct current-score comparisons on this finite synthetic set.
    eligible = [c for rows in runs.values() for c in rows
                if c.label.graded is not None and c.label.graded == c.label.graded]
    result = set()
    for left, right in itertools.combinations(eligible, 2):
        if left.task.name != right.task.name or left.label.graded == right.label.graded:
            continue
        left_wins = ((left.label.graded > right.label.graded) if left.task.higher_is_better
                     else (left.label.graded < right.label.graded))
        better, worse = (left, right) if left_wins else (right, left)
        result.add((better.task.name, better.id, worse.id))
    return result, {c.id: c.label.graded for c in eligible}


def check():
    source = load_pinned_functions()
    runs = fixture()
    expected, current_grades = independent_current_pairs(runs)
    semantic_receipts = []
    for variant in (runs, {k: list(reversed(v)) for k, v in reversed(list(runs.items()))}):
        index, _ = source["flatten_runs"](variant)
        values = source["compute_node_values"](
            index, source["build_children_index"](index), budget_steps=-1, budget_seconds=0.0)
        require(set(values) == set(current_grades), "current_grade_support_mismatch")
        require(all(v.best_subtree_grade == current_grades[k] and v.steps_to_best == 0
                    and v.reachable_descendant_count == 0 for k, v in values.items()),
                "current_score_target_mismatch")
        rows, _ = source["build_value_pairs"](variant, cap_per_task=1000, seed=7,
                                              budget_steps=-1, budget_seconds=0.0)
        oriented = {(r["task"], r["better"], r["worse"]) for r in rows}
        require(len(rows) == len(oriented) and oriented == expected, "current_ordering_mismatch")
        require(all(r["budget_steps"] == -1 and r["budget_secs"] == 0.0
                    and r["subtree_sizes"] == [0, 0] and r["steps_to_best"] == [0, 0]
                    and r["agrees_with_quality"] is True and r["intask_split"] == "unassigned"
                    for r in rows), "pair_target_metadata_mismatch")
        semantic_receipts.append(hashlib.sha256(json.dumps(sorted(oriented)).encode()).hexdigest())
    require(semantic_receipts[0] == semantic_receipts[1], "source_order_semantics_changed")
    rejected = []
    duplicate = fixture()
    duplicate["duplicate-run"] = [next(iter(duplicate.values()))[0]]
    cross_run = fixture()
    cross_run["synthetic-max-run-b"][0].lineage.parent_id = "synthetic-max-a"
    for name, malformed in (("duplicate_card", duplicate), ("cross_run_parent", cross_run)):
        try:
            source["flatten_runs"](malformed)
        except ValueError:
            rejected.append(name)
        else:
            raise RuntimeError("malformed_identity_accepted")
    return {
        "status": "PINNED_CURRENT_SCORE_SOURCE_SEMANTICS_VERIFIED_SYNTHETIC_ONLY",
        "source_commit": COMMIT, "source_path": SOURCE, "source_sha256": SOURCE_SHA,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "credential_shape_hits": 0, "executed_budget_steps": [-1],
        "variants": len(semantic_receipts), "tasks": len({r[0] for r in expected}),
        "synthetic_eligible_nodes": len(current_grades), "synthetic_pairs": len(expected),
        "independent_current_score_orientation_equal": True,
        "order_reversal_semantics_equal": True, "identity_negative_controls_rejected": rejected,
        "leaves_included": True, "source_still_traverses_synthetic_lineage_before_filtering": True,
        "real_payloads_read": 0, "lookahead_runs": 0, "model_fits": 0, "gpu_jobs": 0,
        "actual_published_build_parameters_verified": False, "training_source_qualified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(check(), sort_keys=True) + "\n"
    if args.output is not None:
        # Own synthetic aggregate receipt only; preserve every earlier run.
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(result)
    print(result, end="")
