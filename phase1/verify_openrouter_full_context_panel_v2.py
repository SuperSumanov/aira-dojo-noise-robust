#!/usr/bin/env python3
"""Independent verifier for the private metric-independent historical API panel.

The verifier does not import the builder or judge.  It reconstructs eligibility,
the frozen deterministic selection, every private row, and the aggregate receipt
from immutable historical inputs.  Only an aggregate verification object is printed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from phase1.audit_senior_0819_pair_benchmark_integrity import JsonObjectStream


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class Card:
    identity: str
    run: str
    task_name: str | None
    task_description: str | None
    metric: str | None
    higher_is_better: bool | None
    client: str | None
    hardware: str | None
    time_limit: int | float | None
    execution_timeout: int | float | None
    parent: str | None
    code: str | None

    @property
    def complete(self) -> bool:
        return (
            isinstance(self.task_name, str)
            and bool(self.task_name)
            and isinstance(self.task_description, str)
            and bool(self.task_description)
            and isinstance(self.higher_is_better, bool)
            and isinstance(self.client, str)
            and bool(self.client)
            and isinstance(self.hardware, str)
            and bool(self.hardware)
            and self.time_limit is not None
            and self.execution_timeout is not None
            and isinstance(self.code, str)
            and bool(self.code.strip())
        )

    @property
    def stratum(self) -> tuple[Any, ...]:
        return (
            self.task_name,
            self.client,
            self.hardware,
            self.time_limit,
            self.execution_timeout,
        )


@dataclass(frozen=True)
class Candidate:
    panel: str
    gap_bin: str
    better: Card
    worse: Card
    parent: str | None
    gap_raw: float
    normalized_gap: float

    @property
    def unordered(self) -> tuple[str, str]:
        return tuple(sorted((self.better.identity, self.worse.identity)))

    @property
    def key(self) -> tuple[str, str]:
        return self.panel, self.gap_bin


def finite_positive(value: Any) -> int | float | None:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
    ):
        return value
    return None


def parse_card(identity: str, run: str, value: dict[str, Any]) -> Card:
    require(value.get("id") == identity, "Card identity mismatch")
    task, lineage = value.get("task"), value.get("lineage")
    require(isinstance(task, dict) and isinstance(lineage, dict), "Card nested schema")
    parent = lineage.get("parent_id")
    require(parent is None or (isinstance(parent, str) and parent), "Card parent")
    task_name, description = task.get("name"), task.get("desc")
    metric, direction = task.get("metric"), task.get("higher_is_better")
    client, hardware, code = value.get("client"), value.get("hardware"), value.get("code")
    return Card(
        identity,
        run,
        task_name if isinstance(task_name, str) and task_name else None,
        description if isinstance(description, str) and description else None,
        metric if isinstance(metric, str) and metric else None,
        direction if isinstance(direction, bool) else None,
        client if isinstance(client, str) and client else None,
        hardware if isinstance(hardware, str) and hardware else None,
        finite_positive(value.get("time_limit")),
        finite_positive(value.get("execution_timeout")),
        parent,
        code if isinstance(code, str) else None,
    )


def read_pairs(
    path: Path, expected_rows: int, expected_test: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = 0
    splits: Counter[str] = Counter()
    test_rows: list[dict[str, Any]] = []
    unordered: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank pair row: {number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"pair object: {number}")
            split = value.get("intask_split")
            require(split in {"train", "test"}, f"split: {number}")
            for field in ("better", "worse", "task", "loto_fold", "gap_raw"):
                require(field in value, f"pair field {field}: {number}")
            better, worse = value["better"], value["worse"]
            require(
                isinstance(better, str)
                and bool(better)
                and isinstance(worse, str)
                and bool(worse)
                and better != worse,
                f"pair endpoints: {number}",
            )
            rows += 1
            splits[split] += 1
            if split == "test":
                key = tuple(sorted((value["better"], value["worse"])))
                require(key not in unordered, "duplicate test unordered pair")
                unordered.add(key)
                test_rows.append(value)
    require(rows == expected_rows and len(test_rows) == expected_test, "pair counts")
    return test_rows, dict(splits)


def assign_gap_bin(value: float, bins: list[dict[str, Any]]) -> str | None:
    for item in bins:
        lower, upper = float(item["lower_inclusive"]), item["upper_exclusive"]
        if value >= lower and (upper is None or value < float(upper)):
            return str(item["name"])
    return None


def eligible(
    panel: str,
    rows: list[dict[str, Any]],
    cards: dict[str, Card],
    held_runs: set[str],
    gaps: dict[str, float],
    bins: list[dict[str, Any]],
) -> tuple[list[Candidate], dict[str, int]]:
    result: list[Candidate] = []
    rejected: Counter[str] = Counter()
    for row in rows:
        better, worse = cards[row["better"]], cards[row["worse"]]
        task = row["task"]
        if not isinstance(task, str) or not task or row["loto_fold"] != task:
            rejected["pair_task_schema"] += 1
            continue
        if better.task_name != task or worse.task_name != task:
            rejected["card_task_mismatch"] += 1
            continue
        if not (better.complete and worse.complete):
            rejected["missing_prompt_metadata"] += 1
            continue
        if better.run != worse.run:
            rejected["cross_run"] += 1
            continue
        if better.run not in held_runs:
            rejected["run_split_mismatch"] += 1
            continue
        if better.stratum != worse.stratum:
            rejected["resource_stratum_mismatch"] += 1
            continue
        require(task in gaps, "missing task-unit gap")
        raw_gap = float(row["gap_raw"])
        require(math.isfinite(raw_gap), "nonfinite gap")
        if raw_gap <= 0:
            rejected["nonpositive_gap"] += 1
            continue
        normalized = raw_gap / gaps[task]
        gap_bin = assign_gap_bin(normalized, bins)
        if gap_bin is None:
            rejected["gap_outside_frozen_bins"] += 1
            continue
        parent: str | None = None
        if panel == "decision_direct_sibling":
            parent = row.get("parent")
            if not isinstance(parent, str) or parent not in cards:
                rejected["missing_parent"] += 1
                continue
            parent_card = cards[parent]
            if not (
                better.parent == worse.parent == parent
                and parent_card.run == better.run
                and parent_card.task_name == task
            ):
                rejected["not_verified_direct_sibling"] += 1
                continue
        result.append(Candidate(panel, gap_bin, better, worse, parent, raw_gap, normalized))
    return result, dict(sorted(rejected.items()))


def order_hash(seed: int, candidate: Candidate) -> str:
    value = "\0".join((str(seed), candidate.panel, candidate.gap_bin, *candidate.unordered))
    return hashlib.sha256(value.encode()).hexdigest()


def frozen_select(
    candidates: list[Candidate], protocol: dict[str, Any]
) -> tuple[int, list[tuple[Candidate, str, int]]]:
    panels = ("value_hardware_time", "decision_direct_sibling")
    bins = [item["name"] for item in protocol["selection"]["gap_bins"]]
    strata = [(panel, gap) for gap in bins for panel in panels]
    quota = int(protocol["selection"]["pairs_per_panel_bin"])
    task_cap = int(protocol["selection"]["global_max_pairs_per_task"])
    start, stop = protocol["selection"]["deterministic_seed_search"][
        "first_seed_in_half_open_range"
    ]
    grouped: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    for item in candidates:
        grouped[item.key].append(item)
    require(all(len(grouped[key]) >= quota for key in strata), "infeasible candidate stratum")
    for seed in range(int(start), int(stop)):
        queues = {
            key: sorted(grouped[key], key=lambda item: order_hash(seed, item))
            for key in strata
        }
        positions = {key: 0 for key in strata}
        used_runs: set[str] = set()
        used_endpoints: set[str] = set()
        tasks: Counter[str] = Counter()
        selected: list[tuple[Candidate, str, int]] = []
        failed = False
        for rank in range(1, quota + 1):
            for key in strata:
                chosen = None
                while positions[key] < len(queues[key]):
                    candidate = queues[key][positions[key]]
                    positions[key] += 1
                    if candidate.better.run in used_runs:
                        continue
                    if set(candidate.unordered) & used_endpoints:
                        continue
                    require(isinstance(candidate.better.task_name, str), "candidate task")
                    if tasks[candidate.better.task_name] >= task_cap:
                        continue
                    chosen = candidate
                    break
                if chosen is None:
                    failed = True
                    break
                used_runs.add(chosen.better.run)
                used_endpoints.update(chosen.unordered)
                tasks[chosen.better.task_name] += 1
                selected.append((chosen, order_hash(seed, chosen), rank))
            if failed:
                break
        if not failed and len(selected) == len(strata) * quota:
            return seed, selected
    raise VerificationError("no feasible frozen seed")


def endpoint_payload(card: Card) -> dict[str, Any]:
    require(card.complete, "selected incomplete Card")
    return {
        "id": card.identity,
        "run": card.run,
        "task": {
            "name": card.task_name,
            "desc": card.task_description,
            "higher_is_better": card.higher_is_better,
        },
        "client": card.client,
        "hardware": card.hardware,
        "time_limit": card.time_limit,
        "execution_timeout": card.execution_timeout,
        "code": card.code,
    }


def expected_private_rows(
    selected: list[tuple[Candidate, str, int]], protocol_sha: str, amendment_sha: str
) -> list[dict[str, Any]]:
    rows = []
    for candidate, selection_hash, rank in selected:
        private_id = hashlib.sha256(
            "\0".join((protocol_sha, candidate.panel, *candidate.unordered)).encode()
        ).hexdigest()
        rows.append(
            {
                "schema": "openrouter-full-context-private-panel-row-v1",
                "protocol_sha256": protocol_sha,
                "representation_contract": {
                    "kind": "metric_omission_amendment_v2",
                    "sha256": amendment_sha,
                    "separate_metric_name_required": False,
                },
                "pair_private_id": private_id,
                "panel": candidate.panel,
                "gap_bin": candidate.gap_bin,
                "gap_raw": candidate.gap_raw,
                "normalized_gap": candidate.normalized_gap,
                "selection_order_sha256": selection_hash,
                "selection_rank_within_stratum": rank,
                "smoke": rank == 1,
                "better": endpoint_payload(candidate.better),
                "worse": endpoint_payload(candidate.worse),
                "declared_parent_id": candidate.parent,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["panel"],
            row["gap_bin"],
            row["selection_rank_within_stratum"],
            row["selection_order_sha256"],
        ),
    )


def nearest_rank(values: list[int], fraction: float) -> int:
    require(bool(values), "empty nearest-rank input")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def expected_receipt(
    protocol_sha: str,
    amendment_sha: str,
    observed_inputs: dict[str, str],
    split_counts: dict[str, dict[str, int]],
    inventory: dict[str, int],
    candidates: list[Candidate],
    rejections: dict[str, dict[str, int]],
    seed: int,
    rows: list[dict[str, Any]],
    panel_sha: str,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    candidate_counts = Counter((item.panel, item.gap_bin) for item in candidates)
    selected_counts = Counter((row["panel"], row["gap_bin"]) for row in rows)
    expected_strata = [
        (panel, str(gap["name"]))
        for gap in protocol["selection"]["gap_bins"]
        for panel in ("value_hardware_time", "decision_direct_sibling")
    ]
    tasks = Counter(row["better"]["task"]["name"] for row in rows)
    runs = Counter(row["better"]["run"] for row in rows)
    endpoints = {
        endpoint["id"]
        for row in rows
        for endpoint in (row["better"], row["worse"])
    }
    code_bytes = [
        len(endpoint["code"].encode("utf-8"))
        for row in rows
        for endpoint in (row["better"], row["worse"])
    ]
    return {
        "protocol": "openrouter-full-context-panel-receipt-v1",
        "status": "HISTORICAL_PRIVATE_PANEL_MATERIALIZATION_COMPLETE",
        "protocol_sha256": protocol_sha,
        "representation_contract": {
            "kind": "metric_omission_amendment_v2",
            "sha256": amendment_sha,
            "separate_metric_name_required": False,
        },
        "input_sha256": observed_inputs,
        "input_split_counts": split_counts,
        "card_inventory": inventory,
        "eligible_candidate_counts": {
            f"{panel}:{gap}": candidate_counts[(panel, gap)]
            for panel, gap in expected_strata
        },
        "aggregate_rejections": rejections,
        "selection": {
            "first_feasible_seed": seed,
            "pairs": len(rows),
            "smoke_pairs": sum(bool(row["smoke"]) for row in rows),
            "selected_counts": {
                f"{panel}:{gap}": selected_counts[(panel, gap)]
                for panel, gap in expected_strata
            },
            "tasks": len(tasks),
            "physical_runs": len(runs),
            "endpoints": len(endpoints),
            "maximum_pairs_per_task": max(tasks.values()),
            "maximum_pairs_per_run": max(runs.values()),
            "endpoint_duplicate_excess": 2 * len(rows) - len(endpoints),
        },
        "full_code_utf8_bytes": {
            "minimum": min(code_bytes),
            "median_nearest_rank": nearest_rank(code_bytes, 0.5),
            "p90_nearest_rank": nearest_rank(code_bytes, 0.9),
            "maximum": max(code_bytes),
            "total": sum(code_bytes),
        },
        "private_panel_sha256": panel_sha,
        "security": {
            "row_level_pair_card_task_run_parent_identities_emitted": False,
            "raw_code_emitted": False,
            "pair_orientation_or_gap_values_emitted": False,
            "private_panel_mode_required": "0600",
            "prospective_values_read": False,
            "api_calls": 0,
            "model_fits": 0,
            "base_llm_updates": 0,
        },
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    protocol_path, amendment_path = args.protocol.resolve(), args.amendment.resolve()
    require(sha256(protocol_path) == args.protocol_sha256, "protocol SHA")
    require(sha256(amendment_path) == args.amendment_sha256, "amendment SHA")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    require(protocol.get("protocol") == "openrouter-full-context-judge-v1", "protocol name")
    require(
        protocol.get("status") == "FROZEN_BEFORE_PANEL_MATERIALIZATION_OR_API_CALLS",
        "protocol status",
    )
    require(protocol["security"]["live_calls_authorized_by_this_freeze"] is False, "live calls")
    require(protocol["selection"]["posthoc_rebalancing_forbidden"] is True, "selection drift")
    require(
        amendment.get("protocol") == "openrouter-full-context-metric-omission-amendment-v2",
        "amendment name",
    )
    require(
        amendment.get("status")
        == "FROZEN_AFTER_V1_SCHEMA_KILL_BEFORE_METRIC_INDEPENDENT_ELIGIBILITY_READOUT",
        "amendment status",
    )
    require(amendment["parent_protocol"]["sha256"] == args.protocol_sha256, "parent binding")
    change = amendment["fixed_representation_change"]
    require(change["remove_separate_metric_name_line"] is True, "metric omission drift")
    require(change["retain_full_task_description"] is True, "task-description drift")
    require(
        change["retain_higher_or_lower_is_better_direction"] is True,
        "direction drift",
    )
    require(amendment["unchanged_parent_contract"]["live_calls_authorized"] is False, "live drift")
    paths = {
        "cards": args.cards.resolve(),
        "run_split": args.run_split.resolve(),
        "decision": args.decision.resolve(),
        "value_hardware_time": args.value_hardware_time.resolve(),
        "task_unit_gap": args.task_unit_gap.resolve(),
    }
    observed = {}
    for role, path in paths.items():
        binding = protocol["immutable_inputs"][role]
        observed[role] = sha256(path)
        require(observed[role] == binding.get("sha256", binding.get("lfs_oid_sha256")), f"SHA {role}")
        require(path.stat().st_size == binding["bytes"], f"size {role}")
    split = json.loads(paths["run_split"].read_text(encoding="utf-8"))
    require(isinstance(split, dict) and set(split) == {"all", "hold"}, "run split schema")
    require(isinstance(split["all"], list) and isinstance(split["hold"], list), "run split lists")
    require(
        all(isinstance(item, str) and item for item in split["all"] + split["hold"]),
        "run IDs",
    )
    all_runs, held_runs = set(split["all"]), set(split["hold"])
    split_binding = protocol["immutable_inputs"]["run_split"]
    require(
        len(all_runs) == len(split["all"]) == split_binding["all_runs"]
        and len(held_runs) == len(split["hold"]) == split_binding["held_runs"],
        "run split counts",
    )
    require(held_runs <= all_runs, "held run outside all runs")
    gaps_raw = json.loads(paths["task_unit_gap"].read_text(encoding="utf-8"))
    require(isinstance(gaps_raw, dict) and bool(gaps_raw), "task-unit gap object")
    gaps: dict[str, float] = {}
    for key, value in gaps_raw.items():
        require(isinstance(key, str) and bool(key), "task-unit gap task")
        gap = float(value)
        require(math.isfinite(gap) and gap > 0, f"invalid task-unit gap: {key}")
        gaps[key] = gap

    pair_rows = {}
    split_counts = {}
    for panel, role in (
        ("value_hardware_time", "value_hardware_time"),
        ("decision_direct_sibling", "decision"),
    ):
        binding = protocol["immutable_inputs"][role]
        pair_rows[panel], split_counts[panel] = read_pairs(
            paths[role], binding["rows"], binding["test_rows"]
        )
    needed = {
        identity
        for rows in pair_rows.values()
        for row in rows
        for identity in (row["better"], row["worse"])
    }
    needed.update(
        row["parent"]
        for row in pair_rows["decision_direct_sibling"]
        if isinstance(row.get("parent"), str)
    )
    cards: dict[str, Card] = {}
    seen: set[str] = set()
    seen_runs: set[str] = set()
    metric_values: dict[tuple[str, str], set[str]] = defaultdict(set)
    stream = JsonObjectStream(paths["cards"])
    try:
        for run, rows in stream:
            require(
                run in all_runs
                and run not in seen_runs
                and isinstance(rows, list)
                and bool(rows),
                "Cards run",
            )
            seen_runs.add(run)
            for value in rows:
                require(isinstance(value, dict), "Card object")
                identity = value.get("id")
                require(isinstance(identity, str) and identity not in seen, "Card ID")
                seen.add(identity)
                task = value.get("task")
                if isinstance(task, dict):
                    task_name, metric = task.get("name"), task.get("metric")
                    if (
                        isinstance(task_name, str)
                        and bool(task_name)
                        and isinstance(metric, str)
                        and bool(metric)
                    ):
                        metric_values[(run, task_name)].add(metric)
                if identity in needed:
                    cards[identity] = parse_card(identity, run, value)
    finally:
        stream.close()
    require(seen_runs == all_runs and set(cards) == needed, "Cards coverage")
    consensus_counts: Counter[str] = Counter()
    for card in cards.values():
        values = metric_values.get((card.run, card.task_name or ""), set())
        if len(values) == 0:
            status = "missing"
        elif len(values) > 1:
            status = "ambiguous"
        else:
            consensus = next(iter(values))
            status = "unique" if card.metric in {None, consensus} else "inconsistent"
        if status == "unique" and card.metric is None:
            consensus_counts["metric_recovered_from_run_task_consensus"] += 1
        else:
            consensus_counts[f"metric_consensus_{status}"] += 1
    inventory = {
        "physical_runs": len(seen_runs),
        "cards": len(seen),
        "retained": len(cards),
        **dict(sorted(consensus_counts.items())),
    }

    candidates: list[Candidate] = []
    rejections = {}
    for panel in ("value_hardware_time", "decision_direct_sibling"):
        values, rejections[panel] = eligible(
            panel,
            pair_rows[panel],
            cards,
            held_runs,
            gaps,
            protocol["selection"]["gap_bins"],
        )
        candidates.extend(values)
    seed, selected = frozen_select(candidates, protocol)
    expected_rows = expected_private_rows(
        selected, args.protocol_sha256, args.amendment_sha256
    )
    panel_path, receipt_path = args.panel.resolve(), args.receipt.resolve()
    require(sha256(panel_path) == args.panel_sha256, "private panel SHA")
    require(sha256(receipt_path) == args.receipt_sha256, "aggregate receipt SHA")
    observed_rows = [json.loads(line) for line in panel_path.read_text(encoding="utf-8").splitlines()]
    require(observed_rows == expected_rows, "private panel differs from independent reconstruction")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    reconstructed_receipt = expected_receipt(
        args.protocol_sha256,
        args.amendment_sha256,
        observed,
        split_counts,
        inventory,
        candidates,
        rejections,
        seed,
        expected_rows,
        args.panel_sha256,
        protocol,
    )
    require(receipt == reconstructed_receipt, "aggregate receipt differs from reconstruction")
    return {
        "protocol": "openrouter-full-context-private-panel-independent-verifier-v2",
        "status": "PRIVATE_PANEL_INDEPENDENT_RECONSTRUCTION_EXACT",
        "protocol_sha256": args.protocol_sha256,
        "amendment_sha256": args.amendment_sha256,
        "private_panel_sha256": args.panel_sha256,
        "aggregate_receipt_sha256": args.receipt_sha256,
        "eligible_candidate_counts": receipt["eligible_candidate_counts"],
        "selection": {
            "first_feasible_seed": seed,
            "pairs": len(observed_rows),
            "tasks": len({row["better"]["task"]["name"] for row in observed_rows}),
            "physical_runs": len({row["better"]["run"] for row in observed_rows}),
            "endpoints": len(
                {
                    endpoint["id"]
                    for row in observed_rows
                    for endpoint in (row["better"], row["worse"])
                }
            ),
            "selected_counts": receipt["selection"]["selected_counts"],
        },
        "security": {
            "identities_or_code_emitted": False,
            "prospective_values_read": False,
            "api_calls": 0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--amendment", type=Path, required=True)
    parser.add_argument("--amendment-sha256", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--run-split", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--value-hardware-time", type=Path, required=True)
    parser.add_argument("--task-unit-gap", type=Path, required=True)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--panel-sha256", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--receipt-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    print(json.dumps(verify(parse_args()), ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
