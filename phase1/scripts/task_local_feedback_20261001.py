"""Synthetic-only qualification of feedback facts, NOT an MLE effect test.

No file/label ingestion, model calls, training or production hooks. Exact tails
describe one non-adaptive binary-accuracy comparison, not repeated D_search use.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
import csv
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import random
import re
import statistics
import sys
import time

SEEDS = (61001, 61002, 61003, 61004, 61005)
REPLICATES = 2000
GROUPS = 20
N = 64
ALPHA = .05
SCENARIOS = {
    "null": (.5, .5),
    "target_strong": (.7, .5),
    "target_weak": (.55, .5),
    "target_better_global_worse": (.7, .45),
}
RULES = ("posthoc_any_uncorrected", "family_any_bonferroni",
         "predeclared_target_only", "family_target_bonferroni")


@lru_cache(maxsize=None)
def right_tails(n: int) -> tuple[float, ...]:
    """Integer numerator / 2**n; no normal approximation."""
    if type(n) is not int or not 0 <= n <= 4096:
        raise ValueError("unsupported count")
    tail, values = 0, [0.] * (n + 1)
    for k in range(n, -1, -1):
        tail += math.comb(n, k)
        values[k] = tail / (1 << n)
    return tuple(values)


def binomial_cdf(n: int, p: float) -> list[float]:
    probs = [math.comb(n, k) * p**k * (1 - p)**(n-k)
             for k in range(n + 1)]
    result = [math.fsum(probs[:k + 1]) for k in range(n + 1)]
    if abs(result[-1] - 1.) > 1e-12:
        raise ArithmeticError("sampler mass mismatch")
    result[-1] = 1.
    return result


def packet(counts: list[int], *, n: int, target: int,
           role: str = "synthetic", metric: str = "binary_accuracy",
           predeclared: bool = True) -> dict:
    """Toy aggregate packet. A role string is NOT production authorization."""
    if role != "synthetic" or metric != "binary_accuracy":
        raise ValueError("no real-data/metric adapter installed")
    if predeclared is not True:
        raise ValueError("target not predeclared")
    if type(n) is not int or n < 1 or not counts:
        raise ValueError("empty support")
    if type(target) is not int or not 0 <= target < len(counts):
        raise ValueError("target outside fixed family")
    if any(type(k) is not int or not 0 <= k <= n for k in counts):
        raise ValueError("invalid aggregate count")
    if len(counts) * n > 4096:
        raise ValueError("toy support limit")
    tails = right_tails(n)
    rows = [{"group": i, "n": n, "improved": k, "worsened": n-k,
             "accuracy_delta": (2*k-n)/n, "p_right": tails[k],
             "p_right_family": min(1., len(counts)*tails[k])}
            for i, k in enumerate(counts)]
    total = n*len(counts)
    delta = (2*sum(counts)-total)/total
    return {
        "schema": "synthetic-paired-feedback-v1", "role": role,
        "metric": metric, "target_group": target, "alpha": ALPHA,
        "family_size": len(counts), "groups": rows,
        "target_status": ("supported_under_toy_assumptions" if
                          rows[target]["p_right_family"] <= ALPHA else
                          "insufficient_evidence"),
        "overall_accuracy_delta": delta,
        "overall_observed_direction": ("better" if delta > 0 else
                                       "worse" if delta < 0 else "tie"),
        "scope": "Once-only synthetic independent binary comparisons. No causal, adaptive-search or terminal-generalization claim.",
    }


def render_pair(facts: dict) -> dict:
    """Both receive identical facts, including all corrected statistics/status.

    Instructions differ; no claim of equal token counts or validated LLM use.
    """
    shared = json.dumps(facts, sort_keys=True, separators=(",", ":"),
                        allow_nan=False)
    return {
        "B": {"facts": shared, "instruction":
              "Use all supplied execution evidence to reflect critically and propose the next modification. Explain evidence, uncertainty, and tradeoffs; do not claim causal proof or unseen test performance."},
        "C": {"facts": shared, "instruction":
              "For the predeclared target, separate supported observation, unverified explanation, and next modification. Reference supplied group evidence. Preserve whole-task tradeoffs; insufficient evidence is not failure. Do not turn a local gain into a global gain, invent evidence, force candidate rejection, or claim causal proof or unseen test performance."},
        "same_facts_sha256": sha256(shared.encode()).hexdigest(),
    }


def run(output: Path, base_commit: str, protocol: Path) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", base_commit):
        raise ValueError("exact baseline commit required")
    if output.exists():
        raise ValueError("immutable output exists")
    protocol_sha = sha256(protocol.read_bytes()).hexdigest()
    source_sha = sha256(Path(__file__).read_bytes()).hexdigest()
    tails = right_tails(N)
    # Warmup excluded from timing; it uses an isolated PRNG, not a measured seed.
    warm = random.Random(0)
    cdfs = {p: binomial_cdf(N, p) for probs in SCENARIOS.values() for p in probs}
    for _ in range(100):
        bisect_left(cdfs[.5], warm.random())
    start = time.perf_counter()
    rows = []
    for scenario_index, (scenario, (p_target, p_rest)) in enumerate(SCENARIOS.items()):
        for seed in SEEDS:
            # Independent scenarios; all rules within a replicate share the data.
            effective_seed = seed + scenario_index*1000000
            rng = random.Random(effective_seed)
            hits = dict.fromkeys(RULES, 0)
            global_negative = 0
            target_supported_global_negative = 0
            deltas = []
            for rep in range(REPLICATES):
                if rep % 200 == 0 and time.perf_counter()-start > 120:
                    raise TimeoutError("CPU wall limit; no result published")
                counts = [bisect_left(cdfs[p_target if g == 0 else p_rest], rng.random())
                          for g in range(GROUPS)]
                ps = [tails[k] for k in counts]
                flags = (min(ps) <= ALPHA, min(ps) <= ALPHA/GROUPS,
                         ps[0] <= ALPHA, ps[0] <= ALPHA/GROUPS)
                for rule, flag in zip(RULES, flags):
                    hits[rule] += flag
                delta = (2*sum(counts)-N*GROUPS)/(N*GROUPS)
                deltas.append(delta)
                global_negative += delta < 0
                target_supported_global_negative += flags[-1] and delta < 0
            for rule in RULES:
                rows.append(dict(scenario=scenario, seed=seed,
                                 effective_seed=effective_seed, rule=rule,
                                 replicates=REPLICATES, claims=hits[rule],
                                 claim_rate=hits[rule]/REPLICATES,
                                 global_negative=global_negative,
                                 target_supported_global_negative=target_supported_global_negative,
                                 mean_accuracy_delta=statistics.mean(deltas),
                                 median_accuracy_delta=statistics.median(deltas),
                                 base_commit=base_commit, source_sha256=source_sha,
                                 budget_gpu_hours=0, api_calls=0,
                                 n_per_group=N, groups=GROUPS, alpha=ALPHA))
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["scenario"], row["rule"])].append(row)
    summary = []
    for (scenario, rule), group in grouped.items():
        rates = [r["claim_rate"] for r in group]
        summary.append(dict(scenario=scenario, rule=rule,
                            claim_rate_mean=statistics.mean(rates),
                            claim_rate_median=statistics.median(rates),
                            claim_rate_seed_sd=statistics.stdev(rates),
                            claims=sum(r["claims"] for r in group),
                            total_replicates=sum(r["replicates"] for r in group),
                            global_negative_rate=sum(r["global_negative"] for r in group)/(len(SEEDS)*REPLICATES),
                            target_supported_global_negative_rate=sum(r["target_supported_global_negative"] for r in group)/(len(SEEDS)*REPLICATES)))
    # Independent integer combinatorics, not the inverse-CDF generator.
    q = sum(math.comb(N,k) for k in range(N+1) if tails[k] <= ALPHA)/(1 << N)
    qb = sum(math.comb(N,k) for k in range(N+1) if tails[k] <= ALPHA/GROUPS)/(1 << N)
    theory = dict(zip(RULES, (1-(1-q)**GROUPS, 1-(1-qb)**GROUPS, q, qb)))
    checks = []
    for rule, expected in theory.items():
        observed = next(s["claim_rate_mean"] for s in summary
                        if s["scenario"] == "null" and s["rule"] == rule)
        tolerance = 6*math.sqrt(expected*(1-expected)/(len(SEEDS)*REPLICATES)) + 1/(len(SEEDS)*REPLICATES)
        checks.append(dict(rule=rule, expected=expected, observed=observed,
                           tolerance=tolerance, passed=abs(expected-observed) <= tolerance))
    if not all(c["passed"] for c in checks):
        raise AssertionError("null calibration disagrees with exact formula")
    example = render_pair(packet([45] + [28]*19, n=N, target=0))
    if example["B"]["facts"] != example["C"]["facts"]:
        raise AssertionError("information mismatch")
    record = dict(schema="feedback-qualification-synthetic-v1",
                  timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  base_commit=base_commit, source_sha256=source_sha,
                  protocol_sha256=protocol_sha, python=sys.version,
                  platform=platform.platform(), command=sys.argv,
                  seeds=SEEDS, replicates=REPLICATES, groups=GROUPS,
                  n_per_group=N, alpha=ALPHA, measured_wall_seconds=time.perf_counter()-start,
                  warmup_draws=100, checks=checks, summary=summary,
                  gpu_hours=0, api_calls=0, model_fits=0, real_candidate_executions=0,
                  boundary="Known statistical qualification only. No LLM treatment, real MLE data, adaptive validity guarantee or new method benefit.")
    output.mkdir(parents=True)
    with (output/"runs.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for name, value in (("summary.json", record), ("synthetic_feedback_example.json", example)):
        with (output/name).open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--protocol", required=True, type=Path)
    args = parser.parse_args()
    record = run(args.output, args.base_commit, args.protocol)
    print(json.dumps({key: record[key] for key in ("measured_wall_seconds", "checks", "summary", "boundary")}, indent=2))
