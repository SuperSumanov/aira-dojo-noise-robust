from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scipy.stats import nct, t


class PowerEnvelopeError(RuntimeError):
    pass


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PowerEnvelopeError(message)


def power(delta: float, q: float, tau: float, rho: float, seeds: int, tasks: int,
          mean_inverse_n: float, level: float) -> float:
    require(0 < delta < q <= 1, "require 0 < delta < discordance <= 1")
    require(tau >= 0 and 0 <= rho <= 1 and seeds >= 1 and tasks >= 2, "invalid nuisance parameter")
    factor = (1.0 + (seeds - 1) * rho) / seeds
    task_variance = tau * tau + (q - delta * delta) * factor * mean_inverse_n
    require(task_variance > 0 and math.isfinite(task_variance), "invalid task variance")
    critical = float(t.ppf(1.0 - (1.0 - level) / 2.0, tasks - 1))
    noncentrality = delta * math.sqrt(tasks / task_variance)
    value = float(nct.sf(critical, tasks - 1, noncentrality))
    require(math.isfinite(value) and 0 <= value <= 1, "invalid power")
    return value


def mde(q: float, tau: float, rho: float, seeds: int, tasks: int, mean_inverse_n: float,
        level: float, target: float) -> float | None:
    low, high = 1e-9, min(q - 1e-9, 0.25)
    if power(high, q, tau, rho, seeds, tasks, mean_inverse_n, level) < target:
        return None
    for _ in range(80):
        mid = (low + high) / 2.0
        if power(mid, q, tau, rho, seeds, tasks, mean_inverse_n, level) >= target:
            high = mid
        else:
            low = mid
    return high


def required_tasks(delta: float, q: float, tau: float, rho: float, seeds: int,
                   mean_inverse_n: float, level: float, target: float, maximum: int) -> int | None:
    for tasks in range(2, maximum + 1):
        if power(delta, q, tau, rho, seeds, tasks, mean_inverse_n, level) >= target:
            return tasks
    return None


def run(protocol_path: Path, input_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source = json.loads(input_path.read_text(encoding="utf-8"))
    expected = protocol["input"]["sha256"]
    require(expected != "TO_BE_BOUND_BEFORE_EXECUTION", "input SHA is not bound")
    require(sha256(input_path) == expected, "input SHA mismatch")
    rows = source["metrics"]["arms"]["full"]["anonymous_task_rows"]
    require(isinstance(rows, list) and len(rows) >= 2, "anonymous task rows missing")
    counts = []
    for row in rows:
        require(isinstance(row, dict) and "local_pairs" in row, "local_pairs missing")
        value = row["local_pairs"]
        require(isinstance(value, int) and not isinstance(value, bool) and value > 0, "invalid local_pairs")
        counts.append(value)
    require(sum(counts) == source["metrics"]["arms"]["full"]["local_pairs"], "pair total mismatch")
    cfg = protocol["estimand"]
    seeds, level, target = cfg["training_seeds"], cfg["two_sided_ci_level"], cfg["target_power"]
    mean_inverse_n = sum(1.0 / value for value in counts) / len(counts)
    grid = []
    for delta in cfg["delta_grid"]:
        for q in cfg["paired_discordance_grid"]:
            if delta >= q:
                continue
            for tau in cfg["between_task_sd_grid"]:
                for rho in cfg["seed_correlation_grid"]:
                    grid.append({
                        "between_task_sd": tau,
                        "delta": delta,
                        "paired_discordance": q,
                        "power": power(delta, q, tau, rho, seeds, len(counts), mean_inverse_n, level),
                        "seed_correlation": rho,
                    })
    named = {}
    for name, scenario in protocol["named_scenarios"].items():
        q, tau, rho = scenario["paired_discordance"], scenario["between_task_sd"], scenario["seed_correlation"]
        delta = 0.02
        named[name] = {
            **scenario,
            "power_at_0_02": power(delta, q, tau, rho, seeds, len(counts), mean_inverse_n, level),
            "mde_at_target_power": mde(q, tau, rho, seeds, len(counts), mean_inverse_n, level, target),
            "tasks_required_at_0_02": required_tasks(delta, q, tau, rho, seeds, mean_inverse_n, level, target,
                                                     cfg["maximum_required_tasks_search"]),
        }
    return {
        "classification": "SENSITIVITY_ONLY_NOT_POWER_GUARANTEE",
        "design_warning": named["reference"]["power_at_0_02"] < protocol["classification"]["warning_if_reference_power_at_2pp_below"],
        "input_sha256": expected,
        "protocol_sha256": sha256(protocol_path),
        "structure": {
            "harmonic_mean_pairs_per_task": 1.0 / mean_inverse_n,
            "mean_inverse_pairs_per_task": mean_inverse_n,
            "pairs": sum(counts),
            "tasks": len(counts),
        },
        "named_scenarios": named,
        "grid": grid,
        "resources": {"gpu_jobs": 0, "model_fits": 0, "paid_api_calls": 0, "protected_values_read": 0},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(canonical(run(args.protocol, args.input)), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
