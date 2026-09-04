from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from scipy.stats import nct, t


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calc(delta: float, q: float, tau: float, rho: float, seeds: int, tasks: int,
         inverse_mean: float, level: float) -> float:
    seed_multiplier = rho + (1.0 - rho) / seeds
    variance = tau ** 2 + (q - delta ** 2) * seed_multiplier * inverse_mean
    cutoff = t.ppf((1.0 + level) / 2.0, df=tasks - 1)
    lam = delta / math.sqrt(variance / tasks)
    return float(1.0 - nct.cdf(cutoff, df=tasks - 1, nc=lam))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    source = json.loads(args.input.read_text(encoding="utf-8"))
    result = json.loads(args.result.read_text(encoding="utf-8"))
    assert digest(args.protocol) == result["protocol_sha256"]
    assert digest(args.input) == result["input_sha256"] == protocol["input"]["sha256"]
    rows = source["metrics"]["arms"]["full"]["anonymous_task_rows"]
    counts = [row["local_pairs"] for row in rows]
    assert all(type(value) is int and value > 0 for value in counts)
    assert len(counts) == result["structure"]["tasks"]
    assert sum(counts) == result["structure"]["pairs"]
    inverse_mean = sum(1.0 / value for value in counts) / len(counts)
    cfg = protocol["estimand"]
    by_key = {(x["delta"], x["paired_discordance"], x["between_task_sd"], x["seed_correlation"]): x["power"] for x in result["grid"]}
    expected = 0
    max_diff = 0.0
    for delta in cfg["delta_grid"]:
        for q in cfg["paired_discordance_grid"]:
            if delta >= q:
                continue
            for tau in cfg["between_task_sd_grid"]:
                for rho in cfg["seed_correlation_grid"]:
                    value = calc(delta, q, tau, rho, cfg["training_seeds"], len(counts), inverse_mean,
                                 cfg["two_sided_ci_level"])
                    max_diff = max(max_diff, abs(value - by_key[(delta, q, tau, rho)]))
                    expected += 1
    assert expected == len(result["grid"])
    assert max_diff <= 1e-12
    receipt = {
        "classification": result["classification"],
        "grid_rows_verified": expected,
        "input_sha256": digest(args.input),
        "maximum_power_difference": max_diff,
        "protocol_sha256": digest(args.protocol),
        "status": "INDEPENDENT_VERIFICATION_PASS",
    }
    args.output.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
