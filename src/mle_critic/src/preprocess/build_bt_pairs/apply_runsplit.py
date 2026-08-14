"""Apply a frozen physical-run split to raw Bradley-Terry pair records.

The Card file is the run-grouped JSON produced by ``build_cards``.  The split
file is produced by ``download_and_resolve.build_runsplit`` and has the form
``{"hold": [...], "all": [...]}``.

Both pair endpoints must belong to assigned runs.  A pair is marked ``test``
when both endpoint runs are held out, marked ``train`` when neither is held
out, and dropped when it crosses the boundary.

Usage:
    python -m src.preprocess.build_bt_pairs.build_runsplit \
        CARDS.json RUNSPLIT.json RAW_PAIRS.jsonl OUT_PAIRS.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

from ..download_and_resolve.cards import Card, load_cards


def index_run_by_card_id(
    cards_by_run_id: Mapping[str, Sequence[Card]],
) -> dict[str, str]:
    """Build a strict Card ID to physical run ID lookup table."""
    run_id_by_card_id: dict[str, str] = {}
    for run_id, run_cards in cards_by_run_id.items():
        for card in run_cards:
            if card.id in run_id_by_card_id:
                raise ValueError(
                    f"Duplicate Card ID {card.id!r} in runs "
                    f"{run_id_by_card_id[card.id]!r} and {run_id!r}"
                )
            run_id_by_card_id[card.id] = run_id
    return run_id_by_card_id


def load_frozen_split(split_path: Path) -> tuple[set[str], set[str]]:
    """Read and validate ``(held_out_runs, assigned_runs)``."""
    with split_path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a split JSON object: {split_path}")
    if not isinstance(payload.get("hold"), list) or not isinstance(
        payload.get("all"), list
    ):
        raise ValueError(f"Split file {split_path} must contain list fields hold/all")

    held_out_runs = set(payload["hold"])
    assigned_runs = set(payload["all"])
    if not all(isinstance(run_id, str) for run_id in held_out_runs | assigned_runs):
        raise ValueError(f"Split file {split_path} contains a non-string run ID")
    if not held_out_runs <= assigned_runs:
        raise ValueError("Every held-out run must also appear in split field 'all'")
    return held_out_runs, assigned_runs


def assign_pair_split(
    pair: Mapping,
    run_id_by_card_id: Mapping[str, str],
    held_out_runs: set[str],
    assigned_runs: set[str],
) -> str | None:
    """Return train/test for a pair, or ``None`` when it straddles the split."""
    try:
        better_id = pair["better"]
        worse_id = pair["worse"]
    except KeyError as error:
        raise ValueError("Pair record must contain better and worse Card IDs") from error

    missing_card_ids = [
        card_id
        for card_id in (better_id, worse_id)
        if card_id not in run_id_by_card_id
    ]
    if missing_card_ids:
        raise ValueError(f"Pair references unknown Card IDs: {missing_card_ids}")

    endpoint_runs = {
        run_id_by_card_id[better_id],
        run_id_by_card_id[worse_id],
    }
    unassigned_runs = endpoint_runs - assigned_runs
    if unassigned_runs:
        raise ValueError(
            "Pair references runs absent from the frozen split: "
            f"{sorted(unassigned_runs)}. Update the runsplit before building pairs."
        )

    endpoint_is_test = {run_id in held_out_runs for run_id in endpoint_runs}
    if len(endpoint_is_test) > 1:
        return None
    return "test" if endpoint_is_test.pop() else "train"


def apply_runsplit(
    raw_pairs_path: Path,
    output_path: Path,
    run_id_by_card_id: Mapping[str, str],
    held_out_runs: set[str],
    assigned_runs: set[str],
) -> Counter[str]:
    """Assign every raw pair and atomically write the non-straddling records."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = Path(output_file.name)
            with raw_pairs_path.open(encoding="utf-8") as input_file:
                for line_number, line in enumerate(input_file, start=1):
                    if not line.strip():
                        continue
                    try:
                        pair = json.loads(line)
                        split = assign_pair_split(
                            pair,
                            run_id_by_card_id,
                            held_out_runs,
                            assigned_runs,
                        )
                    except (json.JSONDecodeError, ValueError) as error:
                        raise ValueError(
                            f"Invalid pair at {raw_pairs_path}:{line_number}: {error}"
                        ) from error

                    if split is None:
                        counts["dropped_straddling"] += 1
                        continue
                    pair["intask_split"] = split
                    output_file.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    counts[split] += 1

        os.replace(temporary_path, output_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", type=Path, help="run-grouped Card JSON")
    parser.add_argument("runsplit", type=Path, help="frozen runsplit JSON")
    parser.add_argument("raw_pairs", type=Path, help="raw pair JSONL")
    parser.add_argument("out", type=Path, help="split-assigned pair JSONL")
    return parser.parse_args()


def main() -> None:
    arguments = parse_args()
    cards_by_run_id = load_cards(str(arguments.cards))
    run_id_by_card_id = index_run_by_card_id(cards_by_run_id)
    held_out_runs, assigned_runs = load_frozen_split(arguments.runsplit)

    current_runs = set(cards_by_run_id)
    missing_current_runs = current_runs - assigned_runs
    if missing_current_runs:
        raise ValueError(
            f"Frozen split is missing {len(missing_current_runs)} current runs. "
            "Run download_and_resolve.build_runsplit first."
        )

    counts = apply_runsplit(
        arguments.raw_pairs,
        arguments.out,
        run_id_by_card_id,
        held_out_runs,
        assigned_runs,
    )
    print(f"[runsplit] {arguments.raw_pairs} -> {arguments.out}: {dict(counts)}")


if __name__ == "__main__":
    main()
