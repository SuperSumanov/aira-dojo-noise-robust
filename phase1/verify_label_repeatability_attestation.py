#!/usr/bin/env python3
"""Independent verifier for label_repeatability_attestation_v2.

The verifier intentionally does not import the producer.  It rebuilds the
regrade records, dyadic labels, PAVA curve, target transports, retry
sensitivities, and task-cluster bootstrap from the hash-bound inputs.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import random
from pathlib import Path
from typing import Any, Iterable, Sequence


PROTOCOL = "label_repeatability_attestation_v2"
DECISION_PROTOCOL = "decision_corpus_audit_v1"
HASH_MODE = "normalized_utf8_lf_v1"
EDGES = (0.0, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1, math.inf)
MODES = ("all_successful_records", "first_success_per_card_rep", "last_success_per_card_rep")
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 20260814
MODEL_ASSUMPTION = (
    "conditional_on_gap_two_label_errors_are_independent_exchangeable_and_"
    "symmetric_about_the_latent_pair_order"
)


class VerificationError(RuntimeError):
    pass


def digest(path: Path) -> str:
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"non-UTF-8 input: {path}") from exc
    canonical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical).hexdigest()


def location(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def objects(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise VerificationError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(value, dict):
                raise VerificationError(f"non-object JSON at {path}:{line_number}")
            yield line_number, value


def gap_bin(value: float) -> int:
    if not math.isfinite(value) or value < 0:
        raise VerificationError("invalid gap")
    for index in range(len(EDGES) - 1):
        if EDGES[index] <= value < EDGES[index + 1]:
            return index
    raise VerificationError("gap outside frozen bins")


def read_regrades(paths: Sequence[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    successful: list[dict[str, Any]] = []
    tasks: dict[str, set[str]] = collections.defaultdict(set)
    originals: dict[str, set[float]] = collections.defaultdict(set)
    total_rows = 0
    for file_order, path in enumerate(paths):
        for line_number, row in objects(path):
            total_rows += 1
            card = str(row.get("card_id") or "")
            task = str(row.get("competition") or "")
            if not card or not task:
                raise VerificationError("regrade row lacks card/task")
            tasks[card].add(task)
            original = number(row.get("orig_graded"))
            if original is not None:
                originals[card].add(original)
            score = number(row.get("score"))
            if score is not None:
                successful.append(
                    {
                        "card": card,
                        "task": task,
                        "score": score,
                        "rep": json.dumps(row.get("rep"), sort_keys=True, ensure_ascii=False),
                        "position": (file_order, line_number),
                    }
                )
    if any(len(values) != 1 for values in tasks.values()):
        raise VerificationError("inconsistent task metadata")
    if any(len(values) != 1 for values in originals.values()):
        raise VerificationError("inconsistent original grade metadata")
    duplicates: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in successful:
        duplicates[(row["card"], row["rep"])].append(row)
    repeated = [rows for rows in duplicates.values() if len(rows) > 1]
    conflicts = [rows for rows in repeated if len({row["score"] for row in rows}) > 1]
    metadata = {
        "parsed_rows": total_rows,
        "finite_successful_records": len(successful),
        "cards_with_any_success": len({row["card"] for row in successful}),
        "duplicate_card_rep_groups": len(repeated),
        "conflicting_duplicate_card_rep_groups": len(conflicts),
        "task": {card: next(iter(values)) for card, values in tasks.items()},
        "original": {card: next(iter(values)) for card, values in originals.items() if values},
    }
    return successful, metadata


def choose(successful: Sequence[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode == MODES[0]:
        return sorted(successful, key=lambda row: row["position"])
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in successful:
        grouped[(row["card"], row["rep"])].append(row)
    answer: list[dict[str, Any]] = []
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda row: row["position"])
        answer.append(ordered[0] if mode == MODES[1] else ordered[-1])
    return sorted(answer, key=lambda row: row["position"])


def card_table(
    rows: Sequence[dict[str, Any]], metadata: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[row["card"]].append(row)
    answer: dict[str, dict[str, Any]] = {}
    for card, members in groups.items():
        if card not in metadata["original"] or len(members) < 2:
            continue
        ordered = sorted(members, key=lambda row: row["position"])
        scores = [float(row["score"]) for row in ordered]
        answer[card] = {
            "task": metadata["task"][card],
            "original": float(metadata["original"][card]),
            "scores": scores,
            "mean": sum(scores) / len(scores),
            "stratification_mean": sum(scores[1:]) / (len(scores) - 1),
        }
    return answer


def rank_label(left: float, right: float) -> int | None:
    if left == right:
        return None
    return int(left > right)


def comparisons(
    cards: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    task_cards: dict[str, list[str]] = collections.defaultdict(list)
    for card, row in cards.items():
        task_cards[row["task"]].append(card)
    original_first: list[dict[str, Any]] = []
    original_mean: list[dict[str, Any]] = []
    rerepeat: list[dict[str, Any]] = []
    for task in sorted(task_cards):
        identifiers = sorted(task_cards[task])
        for position, left_id in enumerate(identifiers):
            for right_id in identifiers[position + 1 :]:
                left, right = cards[left_id], cards[right_id]
                bin_id = gap_bin(
                    abs(left["stratification_mean"] - right["stratification_mean"])
                )
                original = rank_label(left["original"], right["original"])
                first_repeat = rank_label(left["scores"][0], right["scores"][0])
                repeat_mean = rank_label(left["mean"], right["mean"])
                if original is not None and first_repeat is not None:
                    original_first.append(
                        {"task": task, "bucket": bin_id, "agrees": int(original == first_repeat)}
                    )
                if original is not None and repeat_mean is not None:
                    original_mean.append(
                        {"task": task, "bucket": bin_id, "agrees": int(original == repeat_mean)}
                    )
                first = rank_label(left["scores"][0], right["scores"][0])
                second = rank_label(left["scores"][1], right["scores"][1])
                if first is not None and second is not None:
                    rerepeat.append(
                        {"task": task, "bucket": bin_id, "agrees": int(first == second)}
                    )
    return original_first, original_mean, rerepeat


def monotone_fit(success: Sequence[int], trials: Sequence[int]) -> list[float]:
    pooled: list[list[Any]] = []
    for index, denominator in enumerate(trials):
        if denominator == 0:
            continue
        pooled.append([[index], int(success[index]), int(denominator)])
        while len(pooled) > 1:
            left, right = pooled[-2], pooled[-1]
            if left[1] / left[2] <= right[1] / right[2]:
                break
            pooled[-2:] = [[left[0] + right[0], left[1] + right[1], left[2] + right[2]]]
    observed: dict[int, float] = {}
    for indices, numerator, denominator in pooled:
        for index in indices:
            observed[index] = numerator / denominator
    fitted: list[float] = []
    carry = 0.5
    for index in range(len(EDGES) - 1):
        if index in observed:
            carry = max(0.5, observed[index])
        fitted.append(carry)
    return fitted


def model_accuracy(reliability: float) -> float:
    return (1 + math.sqrt(max(0.0, 2 * reliability - 1))) / 2


def summarize(
    rows: Sequence[dict[str, Any]], *, include_model_inference: bool = True
) -> dict[str, Any]:
    success = [0] * (len(EDGES) - 1)
    trials = [0] * (len(EDGES) - 1)
    for row in rows:
        index = row["bucket"]
        success[index] += row["agrees"]
        trials[index] += 1
    fitted = monotone_fit(success, trials)
    labels = [
        f"[{EDGES[index]:.12g},{'inf' if math.isinf(EDGES[index + 1]) else f'{EDGES[index + 1]:.12g}'})"
        for index in range(len(EDGES) - 1)
    ]
    return {
        "successes": sum(success),
        "trials": sum(trials),
        "raw_agreement": sum(success) / sum(trials) if sum(trials) else None,
        "tasks": len({row["task"] for row in rows}),
        "bins": [
            {
                "bucket": labels[index],
                "successes": success[index],
                "trials": trials[index],
                "raw_agreement": success[index] / trials[index] if trials[index] else None,
                "pava_repeat_agreement": fitted[index],
                **(
                    {"model_inferred_single_label_accuracy": model_accuracy(fitted[index])}
                    if include_model_inference
                    else {}
                ),
            }
            for index in range(len(fitted))
        ],
    }


def target_tables(
    provenance: dict[str, Any], root: Path, measured_tasks: set[str]
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, record in sorted(provenance.items()):
        path = location(root, str(record["path"]))
        if record.get("hash_mode") != HASH_MODE or digest(path) != record.get("sha256_normalized_lf"):
            raise VerificationError(f"target hash mismatch: {name}")
        counts = [0] * (len(EDGES) - 1)
        covered = [0] * (len(EDGES) - 1)
        tasks: collections.Counter[str] = collections.Counter()
        rows = 0
        for _, row in objects(path):
            task = str(row.get("task") or "")
            gap = number(row.get("gap_raw"))
            if not task or gap is None or gap < 0:
                raise VerificationError(f"invalid target row: {name}")
            index = gap_bin(gap)
            counts[index] += 1
            if task in measured_tasks:
                covered[index] += 1
            tasks[task] += 1
            rows += 1
        if rows != int(record["rows"]):
            raise VerificationError(f"target row mismatch: {name}")
        output[name] = {
            "rows": rows,
            "counts": counts,
            "covered": covered,
            "task_counts": dict(sorted(tasks.items())),
        }
    return output


def average(values: Sequence[float], counts: Sequence[int]) -> float | None:
    denominator = sum(counts)
    if denominator == 0:
        return None
    return sum(value * count for value, count in zip(values, counts)) / denominator


def transports(
    targets: dict[str, Any], summary: dict[str, Any], measured_tasks: set[str]
) -> dict[str, Any]:
    repeat = [row["pava_repeat_agreement"] for row in summary["bins"]]
    accuracy = [row["model_inferred_single_label_accuracy"] for row in summary["bins"]]
    answer: dict[str, Any] = {}
    for name, target in sorted(targets.items()):
        covered_pairs = sum(target["covered"])
        answer[name] = {
            "pairs": target["rows"],
            "tasks": len(target["task_counts"]),
            "measured_task_pairs": covered_pairs,
            "measured_task_pair_share": covered_pairs / target["rows"],
            "task_extrapolation": covered_pairs != target["rows"],
            "all_pairs": {
                "transported_repeat_agreement": average(repeat, target["counts"]),
                "model_inferred_single_label_accuracy": average(accuracy, target["counts"]),
            },
            "measured_task_pairs_only": {
                "transported_repeat_agreement": average(repeat, target["covered"]),
                "model_inferred_single_label_accuracy": average(accuracy, target["covered"]),
            },
        }
    return answer


def percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    left, right = math.floor(position), math.ceil(position)
    if left == right:
        return float(ordered[left])
    weight = position - left
    return float(ordered[left] * (1 - weight) + ordered[right] * weight)


def resample_tasks(
    rows: Sequence[dict[str, Any]], targets: dict[str, Any], repetitions: int, seed: int
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[row["task"]].append(row)
    tasks = sorted(groups)
    generator = random.Random(seed)
    raw_values: list[float] = []
    values = {
        name: {key: [] for key in ("all_repeat", "all_accuracy", "covered_repeat", "covered_accuracy")}
        for name in targets
    }
    for _ in range(repetitions):
        sampled: list[dict[str, Any]] = []
        for _task in range(len(tasks)):
            sampled += groups[generator.choice(tasks)]
        fitted = summarize(sampled)
        raw_values.append(fitted["raw_agreement"])
        repeat = [item["pava_repeat_agreement"] for item in fitted["bins"]]
        accuracy = [item["model_inferred_single_label_accuracy"] for item in fitted["bins"]]
        for name, target in targets.items():
            values[name]["all_repeat"].append(average(repeat, target["counts"]))
            values[name]["all_accuracy"].append(average(accuracy, target["counts"]))
            values[name]["covered_repeat"].append(average(repeat, target["covered"]))
            values[name]["covered_accuracy"].append(average(accuracy, target["covered"]))

    def ci(data: Sequence[float]) -> list[float]:
        return [percentile(data, 0.025), percentile(data, 0.975)]

    return {
        "unit": "task",
        "repetitions": repetitions,
        "seed": seed,
        "raw_original_vs_first_repeat_agreement_ci95": ci(raw_values),
        "targets": {
            name: {
                "all_pairs": {
                    "transported_repeat_agreement_ci95": ci(item["all_repeat"]),
                    "model_inferred_single_label_accuracy_ci95": ci(item["all_accuracy"]),
                },
                "measured_task_pairs_only": {
                    "transported_repeat_agreement_ci95": ci(item["covered_repeat"]),
                    "model_inferred_single_label_accuracy_ci95": ci(item["covered_accuracy"]),
                },
            }
            for name, item in values.items()
        },
    }


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def verify(attestation_path: Path, root: Path) -> dict[str, Any]:
    published = json.loads(attestation_path.read_text(encoding="utf-8"))
    if published.get("protocol") != PROTOCOL or published.get("status") != "VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2":
        raise VerificationError("unexpected attestation protocol/status")
    expected_scope = {
        "reads_endpoint_code": False,
        "reads_endpoint_observation": False,
        "reads_pair_winner_orientation": False,
        "reads_task_orientation": False,
        "trains_predictor": False,
        "gpu": 0,
        "api_calls": 0,
    }
    if published.get("scope") != expected_scope:
        raise VerificationError("scope declaration mismatch")
    estimand = published.get("estimand", {})
    if (
        estimand.get("observed")
        != "pair_order_agreement_between_original_grade_and_first_successful_independent_regrade"
        or estimand.get("model_inferred_quantity")
        != "single_label_accuracy_against_latent_pair_order"
        or estimand.get("model_assumption") != MODEL_ASSUMPTION
        or estimand.get("is_empirical_predictor_ceiling") is not False
        or estimand.get("gap_definition")
        != "absolute_difference_between_means_of_successful_regrades_after_excluding_the_first_label_measurement"
        or estimand.get("transport_assumption")
        != "reference_gap_repeatability_curve_applies_to_target_observed_gap_distribution"
        or estimand.get("gap_edges")
        != [None if math.isinf(value) else value for value in EDGES]
    ):
        raise VerificationError("estimand declaration mismatch")
    if published.get("primary_mode") != MODES[0] or set(published.get("sensitivity_modes", {})) != set(MODES):
        raise VerificationError("sensitivity mode declaration mismatch")
    provenance = published.get("provenance", {})
    script_record = provenance.get("producer_script", {})
    script = location(root, str(script_record.get("path", "")))
    if script_record.get("hash_mode") != HASH_MODE or digest(script) != script_record.get("sha256_normalized_lf"):
        raise VerificationError("producer provenance mismatch")
    regrade_paths: list[Path] = []
    for record in provenance.get("regrades", []):
        path = location(root, str(record.get("path", "")))
        if record.get("hash_mode") != HASH_MODE or digest(path) != record.get("sha256_normalized_lf"):
            raise VerificationError("regrade provenance mismatch")
        regrade_paths.append(path)
    successful, metadata = read_regrades(regrade_paths)
    expected_log = {key: value for key, value in metadata.items() if key not in {"task", "original"}}
    if expected_log != published.get("regrade_log_audit"):
        raise VerificationError("regrade log audit mismatch")

    decision_record = provenance.get("decision_audit_card", {})
    decision_path = location(root, str(decision_record.get("path", "")))
    if decision_record.get("hash_mode") != HASH_MODE or digest(decision_path) != decision_record.get("sha256_normalized_lf"):
        raise VerificationError("decision audit card provenance mismatch")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("protocol") != DECISION_PROTOCOL or decision.get("status") != "VERIFIED_DECISION_CORPUS_AUDIT":
        raise VerificationError("linked decision audit card is not verified")
    decision_targets = {
        name: record for name, record in decision.get("inputs", {}).items() if name != "run_map"
    }
    published_targets = provenance.get("target_pair_sets", {})
    if set(decision_targets) != set(published_targets):
        raise VerificationError("target pair-set names differ from decision audit card")
    for name, record in published_targets.items():
        linked = decision_targets[name]
        if (
            record.get("hash_mode") != linked.get("hash_mode")
            or record.get("sha256_normalized_lf") != linked.get("sha256_normalized_lf")
            or int(record.get("rows", -1)) != int(decision.get("sets", {}).get(name, {}).get("pairs", -2))
        ):
            raise VerificationError(f"target provenance differs from decision audit card: {name}")

    rebuilt_modes: dict[str, Any] = {}
    primary_rows: list[dict[str, Any]] | None = None
    primary_targets: dict[str, Any] | None = None
    for mode in MODES:
        selected = choose(successful, mode)
        cards = card_table(selected, metadata)
        original_first, original_mean, rerepeat = comparisons(cards)
        primary_summary = summarize(original_first)
        measured = {row["task"] for row in original_first}
        targets = target_tables(provenance["target_pair_sets"], root, measured)
        rebuilt_modes[mode] = {
            "selected_successful_records": len(selected),
            "usable_cards": len(cards),
            "measured_tasks": sorted(measured),
            "original_vs_first_repeat": primary_summary,
            "original_vs_repeat_mean": summarize(
                original_mean, include_model_inference=False
            ),
            "first_repeat_vs_second_repeat": summarize(rerepeat),
            "targets": transports(targets, primary_summary, measured),
        }
        if mode == MODES[0]:
            primary_rows = original_first
            primary_targets = targets
    assert primary_rows is not None and primary_targets is not None
    per_task_trials = collections.Counter(row["task"] for row in primary_rows)
    per_task_success = collections.Counter(row["task"] for row in primary_rows if row["agrees"])
    per_task = {
        task: per_task_success[task] / trials for task, trials in sorted(per_task_trials.items())
    }
    rebuilt_modes[MODES[0]]["original_vs_first_repeat"]["per_task_agreement"] = per_task
    rebuilt_modes[MODES[0]]["original_vs_first_repeat"]["task_macro_agreement"] = sum(per_task.values()) / len(per_task)
    bootstrap_published = published["sensitivity_modes"][MODES[0]]["task_cluster_bootstrap"]
    if (
        int(bootstrap_published.get("repetitions", -1)) != BOOTSTRAP_REPETITIONS
        or int(bootstrap_published.get("seed", -1)) != BOOTSTRAP_SEED
        or bootstrap_published.get("unit") != "task"
    ):
        raise VerificationError("bootstrap protocol mismatch")
    rebuilt_modes[MODES[0]]["task_cluster_bootstrap"] = resample_tasks(
        primary_rows,
        primary_targets,
        BOOTSTRAP_REPETITIONS,
        BOOTSTRAP_SEED,
    )
    if rebuilt_modes != published.get("sensitivity_modes"):
        raise VerificationError("published scientific quantities differ from independent rebuild")
    return {
        "protocol": "independent_label_repeatability_attestation_verifier_v2",
        "status": "INDEPENDENTLY_VERIFIED_LABEL_REPEATABILITY_ATTESTATION_V2",
        "source_attestation": {
            "path": attestation_path.as_posix(),
            "hash_mode": HASH_MODE,
            "sha256_normalized_lf": digest(attestation_path),
        },
        "verified_modes": len(rebuilt_modes),
        "verified_pair_sets": len(primary_targets),
        "verified_regrade_files": len(regrade_paths),
        "imports_producer": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    result = verify(Path(arguments.attestation), Path(arguments.root))
    atomic_json(Path(arguments.output), result)
    print(result["status"])
    print(
        f"modes={result['verified_modes']} pair_sets={result['verified_pair_sets']} "
        f"regrade_files={result['verified_regrade_files']}"
    )


if __name__ == "__main__":
    main()
