#!/usr/bin/env python3
"""Compare two independently executed deployment-cost attestations."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


MODELS = ("static_lr", "static_gbm", "tfidf_lr")


class ComparisonError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def ratio(left: float, right: float) -> float:
    return max(left, right) / max(min(left, right), 1e-15)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", required=True)
    parser.add_argument("--run-b", required=True)
    parser.add_argument("--verification-a", required=True)
    parser.add_argument("--verification-b", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    run_a, run_b = Path(arguments.run_a), Path(arguments.run_b)
    output = Path(arguments.out)
    if output.exists():
        raise ComparisonError(f"output already exists: {output}")
    config_a = json.loads((run_a / "config.json").read_text(encoding="utf-8"))
    config_b = json.loads((run_b / "config.json").read_text(encoding="utf-8"))
    summary_a = json.loads((run_a / "summary.json").read_text(encoding="utf-8"))
    summary_b = json.loads((run_b / "summary.json").read_text(encoding="utf-8"))
    verify_a = json.loads(Path(arguments.verification_a).read_text(encoding="utf-8"))
    verify_b = json.loads(Path(arguments.verification_b).read_text(encoding="utf-8"))
    hardware_a = json.loads((run_a / "hardware_environment.json").read_text(encoding="utf-8"))
    hardware_b = json.loads((run_b / "hardware_environment.json").read_text(encoding="utf-8"))
    if {config_a["run_label"], config_b["run_label"]} != {"A", "B"}:
        raise ComparisonError("expected one A and one B run")
    comparable_a = {key: value for key, value in config_a.items() if key != "run_label"}
    comparable_b = {key: value for key, value in config_b.items() if key != "run_label"}
    if comparable_a != comparable_b:
        raise ComparisonError("run configs differ beyond run_label")
    if verify_a["status"] != "INDEPENDENTLY_VERIFIED_DEPLOYMENT_COST_ATTESTATION":
        raise ComparisonError("run A is not independently verified")
    if verify_b["status"] != "INDEPENDENTLY_VERIFIED_DEPLOYMENT_COST_ATTESTATION":
        raise ComparisonError("run B is not independently verified")
    if summary_a["status"] != summary_b["status"]:
        raise ComparisonError("scientific statuses differ")
    same_platform = hardware_a["platform"] == hardware_b["platform"]
    same_python = hardware_a["python"] == hardware_b["python"]
    same_packages = all(
        hardware_a[name] == hardware_b[name] for name in ("numpy", "scipy", "sklearn")
    )
    model_checks: dict[str, Any] = {}
    for model in MODELS:
        query_ratio = ratio(
            summary_a["models"][model]["single_pair_query_ms"]["p50"],
            summary_b["models"][model]["single_pair_query_ms"]["p50"],
        )
        init_ratio = ratio(
            summary_a["models"][model]["initialization_s"]["p50"],
            summary_b["models"][model]["initialization_s"]["p50"],
        )
        same_decisions = (
            summary_a["models"][model]["sample_decision_sha256_values"]
            == summary_b["models"][model]["sample_decision_sha256_values"]
        )
        model_checks[model] = {
            "single_query_p50_max_min_ratio": query_ratio,
            "init_p50_max_min_ratio": init_ratio,
            "same_decisions": same_decisions,
            "query_ratio_at_most_2": query_ratio <= 2.0,
            "init_ratio_at_most_3": init_ratio <= 3.0,
        }
    checks = {
        "same_platform": same_platform,
        "same_python": same_python,
        "same_packages": same_packages,
        "same_result_status": summary_a["status"] == summary_b["status"],
        "all_models_same_decisions": all(item["same_decisions"] for item in model_checks.values()),
        "all_query_p50_ratios_at_most_2": all(
            item["query_ratio_at_most_2"] for item in model_checks.values()
        ),
        "all_init_p50_ratios_at_most_3": all(
            item["init_ratio_at_most_3"] for item in model_checks.values()
        ),
    }
    status = "CROSS_RUN_STABILITY_VERIFIED" if all(checks.values()) else "CROSS_RUN_STABILITY_FAILED"
    payload = {
        "protocol": "deployment_cost_cross_run_verification_v2",
        "status": status,
        "source_commit": config_a["expected_git_commit"],
        "result_status": summary_a["status"],
        "checks": checks,
        "models": model_checks,
        "artifacts": {
            "run_a_summary_sha256": sha256(run_a / "summary.json"),
            "run_b_summary_sha256": sha256(run_b / "summary.json"),
            "verification_a_sha256": sha256(Path(arguments.verification_a)),
            "verification_b_sha256": sha256(Path(arguments.verification_b)),
        },
    }
    atomic_json(output, payload)
    print(status)
    if status != "CROSS_RUN_STABILITY_VERIFIED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
