"""Synthetic-only contract checks of pinned senior export code, not training.

Execute the unmodified AST of reward_from_score/group_advantages and the
converter's first pass. No real samples, private trainer, model, or network.
The first-pass extraction stops before reading samples or writing GRPO rows.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
from types import SimpleNamespace
from typing import Any

REV = "8d39164c5b4c2c1c304fc28801e60467e0ad5de5"
PINS = {
    "src/mle_policy/src/data/journal.py": "e4b1dd9e1e3c6719321995094758a08c952a9f6b836994b5f8507ed007a9fe00",
    "src/mle_policy/src/data/to_grpo.py": "d18676dc1ce6064cf6e8f7361d3931abf3575f630a72f0a5095f97caeeb9b565",
    "src/mle_policy/src/data/selection.py": "2d1675754657b733f7f4d98f6a466b08549806ff7f4f891c9cbf215e48fab4f9",
}
SECRET = re.compile(r"sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|bearer\s+\S{12,}", re.I)


def load_contract():
    trees = {}
    for path, expected in PINS.items():
        raw = subprocess.check_output(["git", "show", f"{REV}:{path}"])
        if hashlib.sha256(raw).hexdigest() != expected or SECRET.search(raw.decode()):
            raise ValueError("source pin or credential gate failed")
        trees[path] = ast.parse(raw)
    chosen = []
    names = {"reward_from_score", "group_advantages", "eligible_members"}
    for tree in trees.values():
        chosen.extend(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names)
    tree = trees["src/mle_policy/src/data/to_grpo.py"]
    chosen.extend(n for n in tree.body if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id in {"UNRESOLVED_REWARD_GAP", "MIN_REWARD_SPREAD"} for t in n.targets))
    original = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "to_grpo")
    start = next(i for i, n in enumerate(original.body) if isinstance(n, ast.AnnAssign)
                 and isinstance(n.target, ast.Name) and n.target.id == "plan")
    end = next(i for i, n in enumerate(original.body) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "wanted_episodes" for t in n.targets))
    args = ast.parse("def first_pass(groups, operators, use_metric_reward=False, unresolved_reward=None, norm_by_std=True, reward_clip=None): pass").body[0].args
    chosen.append(ast.FunctionDef(name="first_pass", args=args,
                  body=original.body[start:end] + ast.parse("return plan, skipped").body,
                  decorator_list=[]))
    ns = {"math": math, "statistics": statistics, "Any": Any}
    exec(compile(ast.fix_missing_locations(ast.Module(body=chosen, type_ignores=[])), "<pinned-source-contract>", "exec"), ns)
    return SimpleNamespace(**{name: ns[name] for name in names | {"first_pass"}})


def run_checks():
    c = load_contract()

    def first(score, metric=None, **kwargs):
        metric = score if metric is None else metric
        assert len(score) == len(metric)
        members = [{"sample_id": str(i), "operator": "improve", "episode_reward": s,
                    "episode_metric_reward": m} for i, (s, m) in enumerate(zip(score, metric))]
        return c.first_pass([{"group_id": "synthetic", "members": members}], {"improve"}, **kwargs)

    def adv(rewards):
        return first(rewards)[0]["synthetic"]["advantages"]

    cases = []
    a, b = adv([0, 1, 2]), adv([7, 7.01, 7.02])
    assert max(abs(x-y) for x, y in zip(a, b)) < 1e-10
    cases.append({"name": "resolved_positive_affine_invariance", "passed": True})
    a, b = adv([0, 2, None]), adv([0, .02, None])
    assert a[0] < 0 < b[0] and a[1] > 0 and b[1] > 0 and a[2] < 0 and b[2] < 0
    cases.append({"name": "fixed_failure_gap_can_flip_valid_advantage_sign", "passed": True,
                  "synthetic_advantages_before": a, "synthetic_advantages_after": b})
    p, s = first([0, 1e-7])
    q, _ = first([0, 1e-5])
    assert not p and s["no_contrast"] == 1 and q
    cases.append({"name": "absolute_contrast_gate_not_scale_invariant", "passed": True})
    p, s = first([2, 3], reward_clip=(0, 1))
    assert not p and s["no_contrast"] == 1
    cases.append({"name": "optional_clipping_can_remove_contrast", "passed": True})
    p, _ = first([0, 1, 2], [0, None, 2], use_metric_reward=True)
    assert p["synthetic"]["rewards"] == [0, -1, 2]
    cases.append({"name": "missing_selected_reward_uses_failure_floor", "passed": True})
    assert c.reward_from_score(.7, {}) is None
    cases.append({"name": "metric_transform_still_requires_threshold_metadata", "passed": True})
    thresholds = {"median_threshold": .5, "gold_threshold": .1, "is_lower_better": True}
    assert c.reward_from_score(.9, thresholds) < c.reward_from_score(.8, thresholds)
    cases.append({"name": "official_lower_direction_not_internal_metric_direction", "passed": True,
                  "condition": "Only a risk if internal metric is higher-better; no real mismatch measured."})
    raw = c.group_advantages([0, 1, 2], False)
    scaled = c.group_advantages([0, 2, 4], False)
    assert scaled == [2*x for x in raw]
    cases.append({"name": "no_std_mode_preserves_reward_scale", "passed": True})
    return {"schema": 1, "source_commit": REV, "source_sha256": PINS,
            "scope": "synthetic pinned exporter first-pass AST; not private trainer or checkpoint provenance",
            "tests_passed": len(cases), "cases": cases, "real_data_rows_read": 0,
            "gpu_jobs": 0, "model_calls": 0, "training_updates": 0,
            "interpretation": "Boundary checks, not proof of production misconfiguration or model-quality causality."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_checks()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
    print(encoded)
