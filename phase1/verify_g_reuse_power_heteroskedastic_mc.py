from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


class VerificationError(RuntimeError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise VerificationError(reason)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independently_compute_wilson(successes: int, trials: int) -> tuple[float, float]:
    z = 1.959963984540054
    observed = successes / trials
    denominator = 1.0 + z * z / trials
    midpoint = (observed + z * z / (2.0 * trials)) / denominator
    radius = z / denominator * math.sqrt(
        observed * (1.0 - observed) / trials + z * z / (4.0 * trials * trials)
    )
    return midpoint - radius, midpoint + radius


def close(left: float, right: float) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= 1e-15


def verify(protocol_path: Path, input_path: Path, result_path: Path) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require(sha256(input_path) == protocol["input"]["sha256"], "input_sha_protocol")
    require(result["input_sha256"] == sha256(input_path), "input_sha_result")
    require(result["protocol_sha256"] == sha256(protocol_path), "protocol_sha_result")
    require(result["classification"] == protocol["classification"], "classification")
    require(result["resources"] == {
        "gpu_jobs": 0, "model_fits": 0, "paid_api_calls": 0, "protected_values_read": 0
    }, "resources")
    require(set(result["scenarios"]) == set(protocol["scenarios"]), "scenario_names")

    fixed = protocol["fixed"]
    verified_scenarios: dict[str, dict] = {}
    aggregate = True
    for name, frozen in protocol["scenarios"].items():
        observed = result["scenarios"][name]
        require(close(observed["analytic_power"], frozen["analytic_power"]), f"{name}_analytic")
        replications = observed["replications"]
        require(len(replications) == len(fixed["simulation_seeds"]) == 2, f"{name}_replications")
        powers = []
        half_widths = []
        for index, row in enumerate(replications):
            successes = row["successes"]
            trials = row["trials"]
            require(isinstance(successes, int) and 0 <= successes <= trials, f"{name}_successes_{index}")
            require(trials == fixed["trials_per_replication"], f"{name}_trials_{index}")
            power = successes / trials
            low, high = independently_compute_wilson(successes, trials)
            half = (high - low) / 2.0
            require(close(row["power"], power), f"{name}_power_{index}")
            require(len(row["wilson_95"]) == 2, f"{name}_wilson_shape_{index}")
            require(close(row["wilson_95"][0], low) and close(row["wilson_95"][1], high),
                    f"{name}_wilson_{index}")
            require(close(row["wilson_95_half_width"], half), f"{name}_half_width_{index}")
            powers.append(power)
            half_widths.append(half)

        mean_power = sum(powers) / 2.0
        expected_gates = {
            "replication_difference": abs(powers[0] - powers[1])
                <= protocol["gates"]["maximum_replication_absolute_difference"],
            "analytic_difference": abs(mean_power - frozen["analytic_power"])
                <= protocol["gates"]["maximum_mean_mc_vs_analytic_absolute_difference"],
            "mc_half_width": all(width <= protocol["gates"]["maximum_wilson_95_half_width"]
                                 for width in half_widths),
        }
        require(close(observed["mean_mc_power"], mean_power), f"{name}_mean")
        require(observed["gates"] == expected_gates, f"{name}_gates")
        aggregate = aggregate and all(expected_gates.values())
        verified_scenarios[name] = {
            "mean_mc_power": mean_power,
            "analytic_absolute_difference": abs(mean_power - frozen["analytic_power"]),
            "gates": expected_gates,
        }

    require(result["all_gates_pass"] is aggregate, "aggregate_gate")
    return {
        "verification_pass": True,
        "all_gates_pass": aggregate,
        "classification": protocol["classification"],
        "input_sha256": sha256(input_path),
        "protocol_sha256": sha256(protocol_path),
        "result_sha256": sha256(result_path),
        "scenarios": verified_scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.protocol, args.input, args.result)
    args.output.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
