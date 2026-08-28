#!/usr/bin/env python3
"""Build the frozen, identity-private full-context historical judge panel.

The builder consumes only credential-scanned historical inputs.  The row-level
panel is sensitive: it contains pair orientation and full code, is created with
mode 0600, and must never be committed.  The separate receipt is aggregate-only.
No network request, model call, prospective outcome, or predictor output is used.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterator, TextIO


PROTOCOL_NAME = "openrouter-full-context-judge-v1"
PROTOCOL_STATUS = "FROZEN_BEFORE_PANEL_MATERIALIZATION_OR_API_CALLS"
RECEIPT_NAME = "openrouter-full-context-panel-receipt-v1"
PANELS = ("value_hardware_time", "decision_direct_sibling")


class PanelError(RuntimeError):
    """Raised when an immutable binding or frozen eligibility rule fails."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PanelError(message)


def sha256_file(path: Path) -> str:
    require(path.is_file() and not path.is_symlink(), f"unsafe input: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise PanelError("non-canonical JSON value") from error


class JsonObjectStream:
    """Incrementally yield key/value pairs from one top-level JSON object."""

    def __init__(self, path: Path, chunk_size: int = 1 << 20) -> None:
        require(path.is_file() and not path.is_symlink(), f"unsafe JSON object: {path}")
        self.handle: TextIO = path.open(encoding="utf-8")
        self.chunk_size = chunk_size
        self.buffer = ""
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def close(self) -> None:
        self.handle.close()

    def _fill(self) -> None:
        if self.position:
            self.buffer = self.buffer[self.position :]
            self.position = 0
        text = self.handle.read(self.chunk_size)
        if text:
            self.buffer += text
        else:
            self.eof = True

    def _skip_space(self) -> None:
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position < len(self.buffer) or self.eof:
                return
            self._fill()

    def _peek(self) -> str:
        self._skip_space()
        require(self.position < len(self.buffer), "unexpected JSON EOF")
        return self.buffer[self.position]

    def _consume(self, token: str) -> None:
        require(self._peek() == token, f"expected JSON token {token!r}")
        self.position += 1

    def _decode(self) -> Any:
        while True:
            self._skip_space()
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError as error:
                require(not self.eof, f"invalid streamed JSON: {error}")
                self._fill()
                continue
            self.position = end
            return value

    def __iter__(self) -> Iterator[tuple[str, Any]]:
        self._fill()
        self._consume("{")
        first = True
        while True:
            if self._peek() == "}":
                self.position += 1
                break
            if not first:
                self._consume(",")
            key = self._decode()
            require(isinstance(key, str) and key, "invalid physical-run identity")
            self._consume(":")
            yield key, self._decode()
            first = False
        self._skip_space()
        while not self.eof:
            self._fill()
            self._skip_space()
        require(self.position == len(self.buffer), "trailing Cards JSON content")


@dataclass(frozen=True)
class Card:
    identity: str
    run: str
    task_name: str
    task_description: str
    metric: str
    higher_is_better: bool
    client: str
    hardware: str
    time_limit: int | float
    execution_timeout: int | float
    parent: str | None
    code: str

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
    def run(self) -> str:
        return self.better.run

    @property
    def task(self) -> str:
        return self.better.task_name

    @property
    def stratum(self) -> tuple[str, str]:
        return self.panel, self.gap_bin


def load_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    observed = sha256_file(path)
    require(observed == expected_sha256, "protocol SHA mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "protocol object required")
    require(value.get("protocol") == PROTOCOL_NAME, "protocol name mismatch")
    require(value.get("status") == PROTOCOL_STATUS, "protocol status mismatch")
    require(value["security"]["live_calls_authorized_by_this_freeze"] is False, "live-call drift")
    require(value["selection"]["posthoc_rebalancing_forbidden"] is True, "selection drift")
    return value, observed


def verify_inputs(protocol: dict[str, Any], paths: dict[str, Path]) -> dict[str, str]:
    observed = {}
    for name, path in paths.items():
        digest = sha256_file(path)
        binding = protocol["immutable_inputs"][name]
        expected = binding.get("sha256", binding.get("lfs_oid_sha256"))
        require(digest == expected, f"input SHA mismatch: {name}")
        require(path.stat().st_size == binding["bytes"], f"input size mismatch: {name}")
        observed[name] = digest
    return observed


def load_run_split(path: Path, protocol: dict[str, Any]) -> tuple[set[str], set[str]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict) and set(value) == {"all", "hold"}, "run-split schema")
    all_rows, held_rows = value["all"], value["hold"]
    require(isinstance(all_rows, list) and isinstance(held_rows, list), "run-split lists")
    require(all(isinstance(item, str) and item for item in all_rows + held_rows), "run IDs")
    all_runs, held_runs = set(all_rows), set(held_rows)
    binding = protocol["immutable_inputs"]["run_split"]
    require(len(all_runs) == len(all_rows) == binding["all_runs"], "all-run count")
    require(len(held_runs) == len(held_rows) == binding["held_runs"], "held-run count")
    require(held_runs <= all_runs, "held run outside all runs")
    return all_runs, held_runs


def load_gap_filter(path: Path) -> dict[str, float]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict) and value, "task-unit-gap object")
    result: dict[str, float] = {}
    for task, raw_gap in value.items():
        require(isinstance(task, str) and task, "task-unit-gap task")
        gap = float(raw_gap)
        require(math.isfinite(gap) and gap > 0, f"invalid task unit gap: {task}")
        result[task] = gap
    return result


def read_pair_file(
    path: Path, expected_rows: int, expected_test_rows: int, panel: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    test_rows: list[dict[str, Any]] = []
    rows = 0
    split_counts: Counter[str] = Counter()
    seen_unordered: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            require(bool(line.strip()), f"blank pair row: {panel}:{number}")
            value = json.loads(line)
            require(isinstance(value, dict), f"pair object: {panel}:{number}")
            for field in ("better", "worse", "task", "loto_fold", "intask_split", "gap_raw"):
                require(field in value, f"missing {field}: {panel}:{number}")
            better, worse = value["better"], value["worse"]
            require(
                isinstance(better, str) and better and isinstance(worse, str) and worse,
                f"pair endpoints: {panel}:{number}",
            )
            require(better != worse, f"self pair: {panel}:{number}")
            split = value["intask_split"]
            require(split in {"train", "test"}, f"pair split: {panel}:{number}")
            split_counts[split] += 1
            rows += 1
            if split == "test":
                unordered = tuple(sorted((better, worse)))
                require(unordered not in seen_unordered, f"duplicate test pair: {panel}")
                seen_unordered.add(unordered)
                test_rows.append(value)
    require(rows == expected_rows, f"pair row count: {panel}")
    require(split_counts["test"] == expected_test_rows, f"pair test count: {panel}")
    return test_rows, dict(split_counts)


def parse_card(identity: str, run: str, value: Any) -> Card:
    require(isinstance(value, dict), "Card object")
    require(value.get("id") == identity, "Card identity mismatch")
    task = value.get("task")
    lineage = value.get("lineage")
    require(isinstance(task, dict) and isinstance(lineage, dict), "Card nested schema")
    code = value.get("code")
    parent = lineage.get("parent_id")
    require(parent is None or (isinstance(parent, str) and parent), "Card parent")
    require(isinstance(code, str), "Card code")
    require(isinstance(task.get("name"), str) and task["name"], "Card task name")
    require(isinstance(task.get("desc"), str) and task["desc"], "Card task description")
    require(isinstance(task.get("metric"), str) and task["metric"], "Card metric")
    require(isinstance(task.get("higher_is_better"), bool), "Card metric direction")
    require(isinstance(value.get("client"), str) and value["client"], "Card client")
    require(isinstance(value.get("hardware"), str) and value["hardware"], "Card hardware")
    for field in ("time_limit", "execution_timeout"):
        require(
            isinstance(value.get(field), (int, float))
            and not isinstance(value.get(field), bool)
            and math.isfinite(float(value[field]))
            and float(value[field]) > 0,
            f"Card {field}",
        )
    return Card(
        identity=identity,
        run=run,
        task_name=task["name"],
        task_description=task["desc"],
        metric=task["metric"],
        higher_is_better=task["higher_is_better"],
        client=value["client"],
        hardware=value["hardware"],
        time_limit=value["time_limit"],
        execution_timeout=value["execution_timeout"],
        parent=parent,
        code=code,
    )


def load_needed_cards(
    path: Path, all_runs: set[str], needed: set[str]
) -> tuple[dict[str, Card], dict[str, int]]:
    selected: dict[str, Card] = {}
    seen: set[str] = set()
    run_count = 0
    card_count = 0
    streamed = JsonObjectStream(path)
    try:
        for run, rows in streamed:
            require(run in all_runs, "Cards run outside frozen manifest")
            run_count += 1
            require(isinstance(rows, list) and rows, "Cards run must be nonempty list")
            for value in rows:
                require(isinstance(value, dict), "Card object required")
                identity = value.get("id")
                require(isinstance(identity, str) and identity, "Card identity")
                require(identity not in seen, "duplicate Card identity")
                seen.add(identity)
                card_count += 1
                if identity in needed:
                    selected[identity] = parse_card(identity, run, value)
    finally:
        streamed.close()
    require(run_count == len(all_runs), "Cards do not exactly cover frozen runs")
    require(set(selected) == needed, "pair endpoint or parent missing from Cards")
    return selected, {"physical_runs": run_count, "cards": card_count, "retained": len(selected)}


def gap_bin(value: float, bins: list[dict[str, Any]]) -> str | None:
    for item in bins:
        lower = float(item["lower_inclusive"])
        upper = item["upper_exclusive"]
        if value >= lower and (upper is None or value < float(upper)):
            return str(item["name"])
    return None


def eligible_candidates(
    panel: str,
    rows: list[dict[str, Any]],
    cards: dict[str, Card],
    held_runs: set[str],
    gap_filter: dict[str, float],
    bins: list[dict[str, Any]],
) -> tuple[list[Candidate], dict[str, int]]:
    candidates: list[Candidate] = []
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
        if better.run != worse.run:
            rejected["cross_run"] += 1
            continue
        if better.run not in held_runs:
            rejected["run_split_mismatch"] += 1
            continue
        if better.stratum != worse.stratum:
            rejected["resource_stratum_mismatch"] += 1
            continue
        if not better.code.strip() or not worse.code.strip():
            rejected["empty_code"] += 1
            continue
        if task not in gap_filter:
            raise PanelError(f"missing task-unit-gap: {task}")
        try:
            raw_gap = float(row["gap_raw"])
        except (TypeError, ValueError) as error:
            raise PanelError("invalid raw gap") from error
        if not math.isfinite(raw_gap) or raw_gap <= 0:
            rejected["nonpositive_gap"] += 1
            continue
        normalized = raw_gap / gap_filter[task]
        selected_bin = gap_bin(normalized, bins)
        if selected_bin is None:
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
        candidates.append(
            Candidate(
                panel=panel,
                gap_bin=selected_bin,
                better=better,
                worse=worse,
                parent=parent,
                gap_raw=raw_gap,
                normalized_gap=normalized,
            )
        )
    return candidates, dict(sorted(rejected.items()))


def candidate_order(seed: int, candidate: Candidate) -> str:
    payload = "\0".join(
        (str(seed), candidate.panel, candidate.gap_bin, *candidate.unordered)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def select_panel(
    candidates: list[Candidate], protocol: dict[str, Any]
) -> tuple[int, list[tuple[Candidate, str, int]]]:
    selection = protocol["selection"]
    bins = [item["name"] for item in selection["gap_bins"]]
    quota = int(selection["pairs_per_panel_bin"])
    max_task = int(selection["global_max_pairs_per_task"])
    start, stop = selection["deterministic_seed_search"]["first_seed_in_half_open_range"]
    strata = [(panel, gap) for gap in bins for panel in PANELS]
    grouped: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.stratum].append(candidate)
    require(all(len(grouped[key]) >= quota for key in strata), "insufficient eligible stratum")

    for seed in range(int(start), int(stop)):
        queues = {
            key: sorted(grouped[key], key=lambda item: candidate_order(seed, item))
            for key in strata
        }
        positions = {key: 0 for key in strata}
        used_runs: set[str] = set()
        used_endpoints: set[str] = set()
        task_counts: Counter[str] = Counter()
        selected: list[tuple[Candidate, str, int]] = []
        failed = False
        for rank in range(1, quota + 1):
            for key in strata:
                queue = queues[key]
                chosen: Candidate | None = None
                while positions[key] < len(queue):
                    candidate = queue[positions[key]]
                    positions[key] += 1
                    endpoints = set(candidate.unordered)
                    if candidate.run in used_runs:
                        continue
                    if endpoints & used_endpoints:
                        continue
                    if task_counts[candidate.task] >= max_task:
                        continue
                    chosen = candidate
                    break
                if chosen is None:
                    failed = True
                    break
                used_runs.add(chosen.run)
                used_endpoints.update(chosen.unordered)
                task_counts[chosen.task] += 1
                selected.append((chosen, candidate_order(seed, chosen), rank))
            if failed:
                break
        if not failed and len(selected) == len(strata) * quota:
            return seed, selected
    raise PanelError("no deterministic seed yields a complete frozen selection")


def card_payload(card: Card) -> dict[str, Any]:
    return {
        "id": card.identity,
        "run": card.run,
        "task": {
            "name": card.task_name,
            "desc": card.task_description,
            "metric": card.metric,
            "higher_is_better": card.higher_is_better,
        },
        "client": card.client,
        "hardware": card.hardware,
        "time_limit": card.time_limit,
        "execution_timeout": card.execution_timeout,
        "code": card.code,
    }


def panel_rows(
    selected: list[tuple[Candidate, str, int]], protocol_sha256: str
) -> list[dict[str, Any]]:
    rows = []
    for candidate, order_hash, rank in selected:
        private_identity = hashlib.sha256(
            "\0".join((protocol_sha256, candidate.panel, *candidate.unordered)).encode()
        ).hexdigest()
        rows.append(
            {
                "schema": "openrouter-full-context-private-panel-row-v1",
                "protocol_sha256": protocol_sha256,
                "pair_private_id": private_identity,
                "panel": candidate.panel,
                "gap_bin": candidate.gap_bin,
                "gap_raw": candidate.gap_raw,
                "normalized_gap": candidate.normalized_gap,
                "selection_order_sha256": order_hash,
                "selection_rank_within_stratum": rank,
                "smoke": rank == 1,
                "better": card_payload(candidate.better),
                "worse": card_payload(candidate.worse),
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


def secure_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(canonical_json(row) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def nearest_rank(values: list[int], fraction: float) -> int:
    require(values, "empty nearest-rank input")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def aggregate_receipt(
    protocol_sha256: str,
    input_sha256: dict[str, str],
    input_splits: dict[str, dict[str, int]],
    inventory: dict[str, int],
    candidates: list[Candidate],
    rejected: dict[str, dict[str, int]],
    seed: int,
    rows: list[dict[str, Any]],
    panel_sha256: str,
) -> dict[str, Any]:
    candidate_counts = Counter((item.panel, item.gap_bin) for item in candidates)
    selected_counts = Counter((row["panel"], row["gap_bin"]) for row in rows)
    tasks = Counter(row["better"]["task"]["name"] for row in rows)
    runs = Counter(row["better"]["run"] for row in rows)
    endpoints = {
        endpoint["id"] for row in rows for endpoint in (row["better"], row["worse"])
    }
    code_bytes = [
        len(endpoint["code"].encode("utf-8"))
        for row in rows
        for endpoint in (row["better"], row["worse"])
    ]
    strata = sorted({(item.panel, item.gap_bin) for item in candidates})
    return {
        "protocol": RECEIPT_NAME,
        "status": "HISTORICAL_PRIVATE_PANEL_MATERIALIZATION_COMPLETE",
        "protocol_sha256": protocol_sha256,
        "input_sha256": input_sha256,
        "input_split_counts": input_splits,
        "card_inventory": inventory,
        "eligible_candidate_counts": {
            f"{panel}:{gap}": candidate_counts[(panel, gap)] for panel, gap in strata
        },
        "aggregate_rejections": rejected,
        "selection": {
            "first_feasible_seed": seed,
            "pairs": len(rows),
            "smoke_pairs": sum(bool(row["smoke"]) for row in rows),
            "selected_counts": {
                f"{panel}:{gap}": selected_counts[(panel, gap)] for panel, gap in strata
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
        "private_panel_sha256": panel_sha256,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--run-split", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--value-hardware-time", type=Path, required=True)
    parser.add_argument("--task-unit-gap", type=Path, required=True)
    parser.add_argument("--panel-out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    return parser.parse_args()


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol, protocol_sha256 = load_protocol(args.protocol.resolve(), args.protocol_sha256)
    paths = {
        "cards": args.cards.resolve(),
        "run_split": args.run_split.resolve(),
        "decision": args.decision.resolve(),
        "value_hardware_time": args.value_hardware_time.resolve(),
        "task_unit_gap": args.task_unit_gap.resolve(),
    }
    input_sha256 = verify_inputs(protocol, paths)
    all_runs, held_runs = load_run_split(paths["run_split"], protocol)
    unit_gaps = load_gap_filter(paths["task_unit_gap"])
    pair_rows: dict[str, list[dict[str, Any]]] = {}
    input_splits: dict[str, dict[str, int]] = {}
    for panel, role in (
        ("value_hardware_time", "value_hardware_time"),
        ("decision_direct_sibling", "decision"),
    ):
        binding = protocol["immutable_inputs"][role]
        pair_rows[panel], input_splits[panel] = read_pair_file(
            paths[role], binding["rows"], binding["test_rows"], panel
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
    cards, inventory = load_needed_cards(paths["cards"], all_runs, needed)
    bins = protocol["selection"]["gap_bins"]
    candidates: list[Candidate] = []
    rejected: dict[str, dict[str, int]] = {}
    for panel in PANELS:
        eligible, rejected[panel] = eligible_candidates(
            panel, pair_rows[panel], cards, held_runs, unit_gaps, bins
        )
        candidates.extend(eligible)
    seed, selected = select_panel(candidates, protocol)
    rows = panel_rows(selected, protocol_sha256)
    secure_write_jsonl(args.panel_out.resolve(), rows)
    panel_digest = sha256_file(args.panel_out.resolve())
    receipt = aggregate_receipt(
        protocol_sha256,
        input_sha256,
        input_splits,
        inventory,
        candidates,
        rejected,
        seed,
        rows,
        panel_digest,
    )
    secure_write_jsonl(args.receipt_out.resolve(), [receipt])
    return receipt


def main() -> None:
    receipt = build(parse_args())
    print(canonical_json(receipt))


if __name__ == "__main__":
    main()
