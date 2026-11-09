"""Convert already prepared datasets without downloading or changing source data."""

import random
from pathlib import Path

import pandas as pd


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"id": str, "example_id": str}, keep_default_na=False)


def check_ids(values) -> list[str]:
    identifiers = [str(value) for value in values]
    if not identifiers or "" in identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError("Expected nonempty, unique sample IDs")
    return identifiers


def sample_groups(frame, group_column, strata_column, count, seed):
    """Select whole groups, balancing strata against their original proportions."""
    groups = []
    for _, group in frame.groupby(group_column, sort=True):
        strata = set(group[strata_column])
        if len(strata) != 1:
            raise ValueError("A sampling group spans multiple strata")
        groups.append((group.index.tolist(), next(iter(strata))))
    random.Random(seed).shuffle(groups)
    proportions = frame[strata_column].value_counts(normalize=True).to_dict()
    selected = []
    selected_counts = {stratum: 0 for stratum in proportions}
    while len(selected) < count:
        candidates = [group for group in groups if len(group[0]) <= count - len(selected)]
        if not candidates:
            break
        indices, stratum = max(
            candidates,
            key=lambda group: proportions[group[1]] * count - selected_counts[group[1]],
        )
        groups.remove((indices, stratum))
        selected.extend(indices)
        selected_counts[stratum] += len(indices)
    if not selected or len(selected) >= len(frame):
        raise ValueError("No usable whole-group split; specify a task-specific count")
    return frame.loc[selected].copy()


def check_images(directory: Path, identifiers: list[str], suffix: str):
    actual = {path.stem for path in directory.glob(f"*{suffix}")}
    if actual != set(identifiers):
        raise ValueError(f"Image IDs do not match metadata: {directory}")
