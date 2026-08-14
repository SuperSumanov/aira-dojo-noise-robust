#!/usr/bin/env python3
"""Build a gap-transported label-repeatability attestation.

This is deliberately not called an empirical predictor ceiling.  The observed
quantity is agreement between an original grade ordering and the first
successful independent regrade ordering.  A single-label accuracy is also reported,
but only under the explicit exchangeable, independent, symmetric-error model
recorded in the output.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import random
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "label_repeatability_attestation_v2"
DECISION_PROTOCOL = "decision_corpus_audit_v1"
HASH_MODE = "normalized_utf8_lf_v1"
EDGES = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
PRIMARY_MODE = "all_successful_records"
SENSITIVITY_MODES = (PRIMARY_MODE, "first_success_per_card_rep", "last_success_per_card_rep")
MODEL_ASSUMPTION = (
    "conditional_on_gap_two_label_errors_are_independent_exchangeable_and_"
    "symmetric_about_the_latent_pair_order"
)
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 20260814


class AttestationError(RuntimeError):
    pass


def finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def normalized_lf_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AttestationError(f"expected UTF-8 input: {path}") from exc
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def normalized_lf_sha256(path: Path) -> str:
    return hashlib.sha256(normalized_lf_bytes(path)).hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def locate(root: Path, published: str) -> Path:
    candidate = Path(published)
    return candidate if candidate.is_absolute() else root / candidate


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
    )


def bucket_label(left: float, right: float) -> str:
    return f"[{left:.12g},{'inf' if math.isinf(right) else f'{right:.12g}'})"


BUCKET_LABELS = tuple(bucket_label(left, right) for left, right in zip(EDGES, EDGES[1:]))


def bucket_index(gap: float) -> int:
    if not math.isfinite(gap) or gap < 0:
        raise AttestationError(f"invalid nonnegative finite gap: {gap!r}")
    for index, (left, right) in enumerate(zip(EDGES, EDGES[1:])):
        if left <= gap < right:
            return index
    raise AttestationError(f"gap did not enter a frozen bucket: {gap}")


def parse_json_lines(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AttestationError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise AttestationError(f"expected JSON object at {path}:{line_number}")
            yield line_number, value


def load_regrades(paths: Sequence[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    task_values: dict[str, set[str]] = collections.defaultdict(set)
    original_values: dict[str, set[float]] = collections.defaultdict(set)
    parsed_rows = 0
    for input_order, path in enumerate(paths):
        for line_number, row in parse_json_lines(path):
            parsed_rows += 1
            card = str(row.get("card_id") or "")
            task = str(row.get("competition") or "")
            if not card or not task:
                raise AttestationError(f"missing card/task at {path}:{line_number}")
            task_values[card].add(task)
            original = finite(row.get("orig_graded"))
            if original is not None:
                original_values[card].add(original)
            score = finite(row.get("score"))
            if score is None:
                continue
            rep = row.get("rep")
            rep_key = json.dumps(rep, sort_keys=True, ensure_ascii=False)
            records.append(
                {
                    "card": card,
                    "task": task,
                    "score": score,
                    "rep_key": rep_key,
                    "order": (input_order, line_number),
                }
            )
    if not records:
        raise AttestationError("no finite successful regrade records")
    for card, tasks in task_values.items():
        if len(tasks) != 1:
            raise AttestationError(f"card has inconsistent tasks: {card}")
    for card, values in original_values.items():
        if len(values) != 1:
            raise AttestationError(f"card has inconsistent original grades: {card}")

    by_card_rep: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        by_card_rep[(record["card"], record["rep_key"])].append(record)
    duplicate_groups = [members for members in by_card_rep.values() if len(members) > 1]
    conflicting_groups = [
        members for members in duplicate_groups if len({item["score"] for item in members}) > 1
    ]
    metadata = {
        "parsed_rows": parsed_rows,
        "finite_successful_records": len(records),
        "cards_with_any_success": len({item["card"] for item in records}),
        "duplicate_card_rep_groups": len(duplicate_groups),
        "conflicting_duplicate_card_rep_groups": len(conflicting_groups),
        "task_by_card": {card: next(iter(values)) for card, values in task_values.items()},
        "original_by_card": {
            card: next(iter(values)) for card, values in original_values.items() if values
        },
    }
    return records, metadata


def select_records(records: Sequence[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == PRIMARY_MODE:
        return sorted(records, key=lambda item: item["order"])
    if mode not in SENSITIVITY_MODES:
        raise AttestationError(f"unsupported sensitivity mode: {mode}")
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        grouped[(record["card"], record["rep_key"])].append(record)
    selected: list[dict[str, Any]] = []
    for members in grouped.values():
        ordered = sorted(members, key=lambda item: item["order"])
        selected.append(ordered[0] if mode.startswith("first_") else ordered[-1])
    return sorted(selected, key=lambda item: item["order"])


def usable_cards(
    selected: Sequence[dict[str, Any]], metadata: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in selected:
        grouped[record["card"]].append(record)
    output: dict[str, dict[str, Any]] = {}
    for card, members in grouped.items():
        original = metadata["original_by_card"].get(card)
        if original is None or len(members) < 2:
            continue
        ordered = sorted(members, key=lambda item: item["order"])
        output[card] = {
            "task": metadata["task_by_card"][card],
            "original": float(original),
            "scores": [float(item["score"]) for item in ordered],
            "repeat_mean": sum(float(item["score"]) for item in ordered) / len(ordered),
            "stratification_mean": (
                sum(float(item["score"]) for item in ordered[1:]) / (len(ordered) - 1)
            ),
        }
    if not output:
        raise AttestationError("no cards have an original grade and at least two repeats")
    return output


def order_label(first: float, second: float) -> int | None:
    if first == second:
        return None
    return int(first > second)


def build_pair_observations(
    cards: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    by_task: dict[str, list[str]] = collections.defaultdict(list)
    for card, item in cards.items():
        task = item["task"]
        by_task[task].append(card)
    original_first: list[dict[str, Any]] = []
    original_mean: list[dict[str, Any]] = []
    repeat_repeat: list[dict[str, Any]] = []
    for task, identifiers in sorted(by_task.items()):
        ordered = sorted(identifiers)
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                first, second = cards[left], cards[right]
                gap = abs(first["stratification_mean"] - second["stratification_mean"])
                original_label = order_label(first["original"], second["original"])
                first_repeat_label = order_label(first["scores"][0], second["scores"][0])
                repeat_mean_label = order_label(first["repeat_mean"], second["repeat_mean"])
                if original_label is not None and first_repeat_label is not None:
                    original_first.append(
                        {
                            "task": task,
                            "bucket": bucket_index(gap),
                            "agrees": int(original_label == first_repeat_label),
                        }
                    )
                if original_label is not None and repeat_mean_label is not None:
                    original_mean.append(
                        {
                            "task": task,
                            "bucket": bucket_index(gap),
                            "agrees": int(original_label == repeat_mean_label),
                        }
                    )
                first_label = order_label(first["scores"][0], second["scores"][0])
                second_label = order_label(first["scores"][1], second["scores"][1])
                if first_label is not None and second_label is not None:
                    repeat_repeat.append(
                        {
                            "task": task,
                            "bucket": bucket_index(gap),
                            "agrees": int(first_label == second_label),
                        }
                    )
    return original_first, original_mean, repeat_repeat


def bin_totals(observations: Sequence[dict[str, Any]]) -> tuple[list[int], list[int]]:
    successes = [0] * len(BUCKET_LABELS)
    trials = [0] * len(BUCKET_LABELS)
    for item in observations:
        index = int(item["bucket"])
        successes[index] += int(item["agrees"])
        trials[index] += 1
    return successes, trials


def fitted_agreement(successes: Sequence[int], trials: Sequence[int]) -> list[float]:
    if len(successes) != len(BUCKET_LABELS) or len(trials) != len(BUCKET_LABELS):
        raise AttestationError("bucket vector length mismatch")
    blocks: list[dict[str, Any]] = []
    for index, (success, trial) in enumerate(zip(successes, trials)):
        if trial <= 0:
            continue
        block = {"indices": [index], "success": int(success), "trial": int(trial)}
        blocks.append(block)
        while len(blocks) >= 2:
            previous, current = blocks[-2], blocks[-1]
            previous_rate = previous["success"] / previous["trial"]
            current_rate = current["success"] / current["trial"]
            if previous_rate <= current_rate:
                break
            blocks[-2:] = [
                {
                    "indices": previous["indices"] + current["indices"],
                    "success": previous["success"] + current["success"],
                    "trial": previous["trial"] + current["trial"],
                }
            ]
    observed_fit: dict[int, float] = {}
    for block in blocks:
        rate = block["success"] / block["trial"]
        for index in block["indices"]:
            observed_fit[index] = rate
    output: list[float] = []
    previous = 0.5
    for index in range(len(BUCKET_LABELS)):
        if index in observed_fit:
            previous = max(0.5, float(observed_fit[index]))
        output.append(previous)
    return output


def inferred_accuracy(repeat_agreement: float) -> float:
    return (1.0 + math.sqrt(max(0.0, 2.0 * repeat_agreement - 1.0))) / 2.0


def curve_summary(
    observations: Sequence[dict[str, Any]], *, include_model_inference: bool = True
) -> dict[str, Any]:
    successes, trials = bin_totals(observations)
    fitted = fitted_agreement(successes, trials)
    return {
        "successes": sum(successes),
        "trials": sum(trials),
        "raw_agreement": sum(successes) / sum(trials) if sum(trials) else None,
        "tasks": len({item["task"] for item in observations}),
        "bins": [
            {
                "bucket": label,
                "successes": successes[index],
                "trials": trials[index],
                "raw_agreement": successes[index] / trials[index] if trials[index] else None,
                "pava_repeat_agreement": fitted[index],
                **(
                    {"model_inferred_single_label_accuracy": inferred_accuracy(fitted[index])}
                    if include_model_inference
                    else {}
                ),
            }
            for index, label in enumerate(BUCKET_LABELS)
        ],
    }


def load_targets(card_path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    if card.get("protocol") != DECISION_PROTOCOL or card.get("status") != "VERIFIED_DECISION_CORPUS_AUDIT":
        raise AttestationError("decision audit card is not a verified v1 card")
    inputs = card.get("inputs")
    if not isinstance(inputs, dict):
        raise AttestationError("decision audit card has no input manifest")
    targets: dict[str, Any] = {}
    for name, record in sorted(inputs.items()):
        if name == "run_map":
            continue
        path = locate(root, str(record.get("path", "")))
        if record.get("hash_mode") != HASH_MODE:
            raise AttestationError(f"unsupported pair hash mode: {name}")
        if normalized_lf_sha256(path) != record.get("sha256_normalized_lf"):
            raise AttestationError(f"pair input hash mismatch: {name}")
        counts = [0] * len(BUCKET_LABELS)
        tasks: collections.Counter[str] = collections.Counter()
        rows = 0
        for line_number, row in parse_json_lines(path):
            task = str(row.get("task") or "")
            gap = finite(row.get("gap_raw"))
            if not task or gap is None or gap < 0:
                raise AttestationError(f"invalid target task/gap at {path}:{line_number}")
            counts[bucket_index(gap)] += 1
            tasks[task] += 1
            rows += 1
        expected = card.get("sets", {}).get(name, {}).get("pairs")
        if rows != expected:
            raise AttestationError(f"target row count differs from audit card: {name}")
        targets[name] = {
            "path": portable_path(path),
            "sha256_normalized_lf": normalized_lf_sha256(path),
            "rows": rows,
            "bin_counts": counts,
            "task_counts": dict(sorted(tasks.items())),
        }
    if not targets:
        raise AttestationError("decision audit card contains no pair targets")
    return card, targets


def weighted(values: Sequence[float], counts: Sequence[int]) -> float | None:
    total = sum(counts)
    return sum(value * count for value, count in zip(values, counts)) / total if total else None


def target_transport(
    target: dict[str, Any], curve: dict[str, Any], measured_tasks: set[str]
) -> dict[str, Any]:
    agreements = [float(item["pava_repeat_agreement"]) for item in curve["bins"]]
    accuracies = [float(item["model_inferred_single_label_accuracy"]) for item in curve["bins"]]
    covered_counts = [0] * len(BUCKET_LABELS)
    covered_pairs = 0
    for task, count in target["task_counts"].items():
        if task in measured_tasks:
            covered_pairs += int(count)
    # Re-read-free covered bin counts are supplied by the caller when present.
    if "covered_bin_counts" in target:
        covered_counts = [int(value) for value in target["covered_bin_counts"]]
    return {
        "pairs": target["rows"],
        "tasks": len(target["task_counts"]),
        "measured_task_pairs": covered_pairs,
        "measured_task_pair_share": covered_pairs / target["rows"],
        "task_extrapolation": covered_pairs != target["rows"],
        "all_pairs": {
            "transported_repeat_agreement": weighted(agreements, target["bin_counts"]),
            "model_inferred_single_label_accuracy": weighted(accuracies, target["bin_counts"]),
        },
        "measured_task_pairs_only": {
            "transported_repeat_agreement": weighted(agreements, covered_counts),
            "model_inferred_single_label_accuracy": weighted(accuracies, covered_counts),
        },
    }


def add_covered_target_bins(targets: dict[str, Any], root: Path, measured_tasks: set[str]) -> None:
    for target in targets.values():
        path = locate(root, target["path"])
        counts = [0] * len(BUCKET_LABELS)
        for _, row in parse_json_lines(path):
            if str(row["task"]) in measured_tasks:
                gap = finite(row["gap_raw"])
                if gap is None:
                    raise AttestationError(f"nonfinite target gap in {path}")
                counts[bucket_index(gap)] += 1
        target["covered_bin_counts"] = counts


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise AttestationError("cannot take quantile of empty sequence")
    position = (len(ordered) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[low])
    fraction = position - low
    return float(ordered[low] * (1.0 - fraction) + ordered[high] * fraction)


def bootstrap(
    observations: Sequence[dict[str, Any]],
    targets: dict[str, Any],
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    if repetitions <= 0:
        raise AttestationError("bootstrap repetitions must be positive")
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in observations:
        grouped[item["task"]].append(item)
    tasks = sorted(grouped)
    if not tasks:
        raise AttestationError("bootstrap has no task clusters")
    rng = random.Random(seed)
    raw_draws: list[float] = []
    draws: dict[str, dict[str, list[float]]] = {
        name: {
            "all_repeat": [],
            "all_accuracy": [],
            "covered_repeat": [],
            "covered_accuracy": [],
        }
        for name in targets
    }
    for _ in range(repetitions):
        sampled: list[dict[str, Any]] = []
        for _cluster in range(len(tasks)):
            sampled.extend(grouped[rng.choice(tasks)])
        curve = curve_summary(sampled)
        raw_draws.append(float(curve["raw_agreement"]))
        agreements = [float(item["pava_repeat_agreement"]) for item in curve["bins"]]
        accuracies = [float(item["model_inferred_single_label_accuracy"]) for item in curve["bins"]]
        for name, target in targets.items():
            draws[name]["all_repeat"].append(float(weighted(agreements, target["bin_counts"])))
            draws[name]["all_accuracy"].append(float(weighted(accuracies, target["bin_counts"])))
            covered_repeat = weighted(agreements, target["covered_bin_counts"])
            covered_accuracy = weighted(accuracies, target["covered_bin_counts"])
            if covered_repeat is not None and covered_accuracy is not None:
                draws[name]["covered_repeat"].append(float(covered_repeat))
                draws[name]["covered_accuracy"].append(float(covered_accuracy))

    def interval(values: Sequence[float]) -> list[float]:
        return [quantile(values, 0.025), quantile(values, 0.975)]

    return {
        "unit": "task",
        "repetitions": repetitions,
        "seed": seed,
        "raw_original_vs_first_repeat_agreement_ci95": interval(raw_draws),
        "targets": {
            name: {
                "all_pairs": {
                    "transported_repeat_agreement_ci95": interval(item["all_repeat"]),
                    "model_inferred_single_label_accuracy_ci95": interval(item["all_accuracy"]),
                },
                "measured_task_pairs_only": {
                    "transported_repeat_agreement_ci95": interval(item["covered_repeat"]),
                    "model_inferred_single_label_accuracy_ci95": interval(item["covered_accuracy"]),
                },
            }
            for name, item in draws.items()
        },
    }


def build_attestation(
    regrade_paths: Sequence[Path],
    decision_card_path: Path,
    root: Path,
    bootstrap_repetitions: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    if len({path.resolve() for path in regrade_paths}) != len(regrade_paths):
        raise AttestationError("duplicate regrade path")
    records, metadata = load_regrades(regrade_paths)
    decision_card, targets = load_targets(decision_card_path, root)

    mode_payloads: dict[str, Any] = {}
    primary_observations: list[dict[str, Any]] | None = None
    primary_measured_tasks: set[str] | None = None
    for mode in SENSITIVITY_MODES:
        selected = select_records(records, mode)
        cards = usable_cards(selected, metadata)
        original_first, original_mean, repeat_repeat = build_pair_observations(cards)
        primary_curve = curve_summary(original_first)
        measured_tasks = {item["task"] for item in original_first}
        targets_for_mode = json.loads(json.dumps(targets))
        add_covered_target_bins(targets_for_mode, root, measured_tasks)
        mode_payloads[mode] = {
            "selected_successful_records": len(selected),
            "usable_cards": len(cards),
            "measured_tasks": sorted(measured_tasks),
            "original_vs_first_repeat": primary_curve,
            "original_vs_repeat_mean": curve_summary(
                original_mean, include_model_inference=False
            ),
            "first_repeat_vs_second_repeat": curve_summary(repeat_repeat),
            "targets": {
                name: target_transport(target, primary_curve, measured_tasks)
                for name, target in sorted(targets_for_mode.items())
            },
        }
        if mode == PRIMARY_MODE:
            primary_observations = original_first
            primary_measured_tasks = measured_tasks
            targets = targets_for_mode
    assert primary_observations is not None and primary_measured_tasks is not None
    primary_bootstrap = bootstrap(
        primary_observations, targets, bootstrap_repetitions, bootstrap_seed
    )
    primary_task_trials = collections.Counter(item["task"] for item in primary_observations)
    primary_task_success = collections.Counter(
        item["task"] for item in primary_observations if item["agrees"]
    )
    task_agreements = {
        task: primary_task_success[task] / trials
        for task, trials in sorted(primary_task_trials.items())
    }
    mode_payloads[PRIMARY_MODE]["original_vs_first_repeat"]["per_task_agreement"] = task_agreements
    mode_payloads[PRIMARY_MODE]["original_vs_first_repeat"]["task_macro_agreement"] = (
        sum(task_agreements.values()) / len(task_agreements)
    )
    mode_payloads[PRIMARY_MODE]["task_cluster_bootstrap"] = primary_bootstrap

    return {
        "protocol": PROTOCOL,
        "status": "VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2",
        "estimand": {
            "observed": "pair_order_agreement_between_original_grade_and_first_successful_independent_regrade",
            "model_inferred_quantity": "single_label_accuracy_against_latent_pair_order",
            "model_assumption": MODEL_ASSUMPTION,
            "is_empirical_predictor_ceiling": False,
            "gap_definition": "absolute_difference_between_means_of_successful_regrades_after_excluding_the_first_label_measurement",
            "transport_assumption": "reference_gap_repeatability_curve_applies_to_target_observed_gap_distribution",
            "gap_edges": [None if math.isinf(value) else value for value in EDGES],
            "pava": "trial_weighted_nondecreasing_repeat_agreement; empty bins carry previous; leading empty bins=0.5; fitted values floored at 0.5",
        },
        "scope": {
            "reads_endpoint_code": False,
            "reads_endpoint_observation": False,
            "reads_pair_winner_orientation": False,
            "reads_task_orientation": False,
            "trains_predictor": False,
            "gpu": 0,
            "api_calls": 0,
        },
        "provenance": {
            "producer_script": {
                "path": portable_path(Path(__file__)),
                "hash_mode": HASH_MODE,
                "sha256_normalized_lf": normalized_lf_sha256(Path(__file__)),
            },
            "python": platform.python_version(),
            "regrades": [
                {
                    "path": portable_path(path),
                    "hash_mode": HASH_MODE,
                    "sha256_normalized_lf": normalized_lf_sha256(path),
                }
                for path in regrade_paths
            ],
            "decision_audit_card": {
                "path": portable_path(decision_card_path),
                "hash_mode": HASH_MODE,
                "sha256_normalized_lf": normalized_lf_sha256(decision_card_path),
                "protocol": decision_card["protocol"],
                "status": decision_card["status"],
            },
            "target_pair_sets": {
                name: {
                    "path": item["path"],
                    "hash_mode": HASH_MODE,
                    "sha256_normalized_lf": item["sha256_normalized_lf"],
                    "rows": item["rows"],
                }
                for name, item in sorted(targets.items())
            },
        },
        "regrade_log_audit": {
            key: value
            for key, value in metadata.items()
            if key not in {"task_by_card", "original_by_card"}
        },
        "primary_mode": PRIMARY_MODE,
        "sensitivity_modes": mode_payloads,
    }


def render_datasheet(result: dict[str, Any]) -> str:
    primary = result["sensitivity_modes"][PRIMARY_MODE]
    cross = primary["original_vs_first_repeat"]
    lines = [
        "# Label repeatability attestation v2",
        "",
        f"- Status: `{result['status']}`",
        f"- Usable cards: {primary['usable_cards']}",
        f"- Measured tasks: {len(primary['measured_tasks'])}",
        f"- Original-vs-first-repeat pair observations: {cross['trials']}",
        f"- Raw original-vs-first-repeat agreement: {cross['raw_agreement']:.12f}",
        f"- Task-macro original-vs-first-repeat agreement: {cross['task_macro_agreement']:.12f}",
        "- Predictor ceiling measured directly: no",
        "",
        "The inferred single-label quantity requires the independent, exchangeable, symmetric-error model stated in `attestation.json`.",
        "",
        "| target | pairs | measured-task share | repeat agreement | inferred single-label accuracy | extrapolates tasks |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, item in sorted(primary["targets"].items()):
        lines.append(
            f"| {name} | {item['pairs']} | {item['measured_task_pair_share']:.6f} | "
            f"{item['all_pairs']['transported_repeat_agreement']:.6f} | "
            f"{item['all_pairs']['model_inferred_single_label_accuracy']:.6f} | "
            f"{str(item['task_extrapolation']).lower()} |"
        )
    lines.extend(
        [
            "",
            "Primary uncertainty is a 2,000-repetition task-cluster bootstrap. Pair-i.i.d. binomial intervals are not used.",
            "Duplicate `(card, rep)` successful records are retained in the primary physical-record estimand and audited with first/last sensitivity modes.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regrade", action="append", required=True)
    parser.add_argument("--decision-audit-card", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--bootstrap", type=int, default=BOOTSTRAP_REPETITIONS)
    parser.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    if arguments.bootstrap != BOOTSTRAP_REPETITIONS or arguments.seed != BOOTSTRAP_SEED:
        raise AttestationError(
            f"v2 freezes bootstrap={BOOTSTRAP_REPETITIONS} seed={BOOTSTRAP_SEED}"
        )
    result = build_attestation(
        [Path(value) for value in arguments.regrade],
        Path(arguments.decision_audit_card),
        Path(arguments.root),
        arguments.bootstrap,
        arguments.seed,
    )
    output = Path(arguments.out_dir)
    atomic_json(output / "attestation.json", result)
    atomic_text(output / "DATASHEET.md", render_datasheet(result))
    primary = result["sensitivity_modes"][PRIMARY_MODE]
    print(result["status"])
    print(
        f"cards={primary['usable_cards']} tasks={len(primary['measured_tasks'])} "
        f"pairs={primary['original_vs_first_repeat']['trials']} "
        f"raw_agreement={primary['original_vs_first_repeat']['raw_agreement']:.12f}"
    )
    for name, item in sorted(primary["targets"].items()):
        print(
            f"{name} pairs={item['pairs']} measured_task_share={item['measured_task_pair_share']:.12f} "
            f"repeat={item['all_pairs']['transported_repeat_agreement']:.12f} "
            f"inferred={item['all_pairs']['model_inferred_single_label_accuracy']:.12f}"
        )


if __name__ == "__main__":
    main()
