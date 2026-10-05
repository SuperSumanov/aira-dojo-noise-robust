"""Stage 2: merge the per-batch dataset directories into one.

Grouping already happened inside each batch, so this is a plain concatenation:
the merged dataset keeps every batch's groups intact and adds nothing across
batches.  It writes ``samples.jsonl``, ``groups.jsonl`` and a manifest that
summarises which batches went in.

No train/val split is decided here -- that is ``assign_splits``.

Runs can be dropped before merging, with the same filters as ``mle_critic``'s
``build_cards`` plus one: ``--client``, ``--base-url``, ``--tasks``,
``--hardware``, ``--time-limit``, ``--execution-timeout``, ``--date``.  The
extra ``--base-url`` exists because a run is identified by its
``(base_url, model_id)`` pair -- the ``provider`` field in ``dojo_config.json``
is the litellm protocol (always ``openai``) and says nothing about the vendor.

``--client`` and ``--base-url`` take a ``+``-separated list (``--client
a+b``), and a run survives when it has one pair matching any value from each
list.  Combining several models this way is the point: a single model often has
too few runs to be useful on its own.

Filtering works on *runs*, never on single samples: a dropped run's samples are
not written, and a group keeps only its surviving members (a group with none
left is dropped).  Groups never mix environments, and the environment includes
task, hardware, limits and client, so those filters cannot split a group; only
``--date`` and ``--base-url`` could, and both are uniform within a batch in
practice.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import groupdata

_LAUNCH_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T]")


def find_batch_dirs(paths: Iterable[Path]) -> list[Path]:
    """Resolve each input to batch dataset directories.

    An input that is itself a dataset directory is used directly; anything else
    is treated as a parent whose immediate subdirectories are batches.
    """
    batches: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).resolve()
        if (path / groupdata.MANIFEST_FILE).is_file():
            batches.append(path)
            continue
        if not path.is_dir():
            raise ValueError(f"Batch input does not exist: {path}")
        batches.extend(sorted(child for child in path.iterdir() if (child / groupdata.MANIFEST_FILE).is_file()))
    if not batches:
        raise ValueError("No batch dataset directories found")
    return batches


def parse_patterns(value: str | None) -> tuple[str, ...] | None:
    """Split a ``+``-separated filter value; ``None`` stays ``None``."""
    if value is None:
        return None
    patterns = tuple(part for part in value.split("+") if part)
    return patterns or None


def _in_range(value: Any, bounds: tuple[float, float]) -> bool:
    """Bounds are inclusive, like ``build_cards``; non-numbers never match."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    return bounds[0] <= value <= bounds[1]


def _launch_date(run: dict[str, Any]) -> datetime.date:
    """The ``YYYY-MM-DD`` part of a run's ``metadata.launch_time``."""
    match = _LAUNCH_DATE_RE.match(str(run.get("launch_time") or ""))
    if match is None:
        raise ValueError(
            f"Run {run.get('run_dir')} has no usable launch_time for the date filter: "
            f"{run.get('launch_time')!r}"
        )
    return datetime.date.fromisoformat(match.group(1))


@dataclass(frozen=True)
class RunFilters:
    """The selection applied to runs before merging, mirroring ``build_cards``.

    ``client`` and ``base_url`` are lists of substrings matched against the
    *same* ``(base_url, model_id)`` pair; a run survives when one of its pairs
    contains any ``client`` value and any ``base_url`` value.  So
    ``client=("kimi",)`` + ``base_url=("openrouter",)`` keeps the run that is
    kimi on OpenRouter, never a run that merely has each separately.
    ``time_limit`` / ``execution_timeout`` are inclusive ``(min, max)`` pairs,
    ``date`` an inclusive ``(start, end)`` of ``datetime.date``.
    """

    client: tuple[str, ...] | None = None
    base_url: tuple[str, ...] | None = None
    tasks: tuple[str, ...] | None = None
    hardware: str | None = None
    time_limit: tuple[int, int] | None = None
    execution_timeout: tuple[int, int] | None = None
    date: tuple[datetime.date, datetime.date] | None = None

    def is_active(self) -> bool:
        return any(
            value is not None
            for value in (self.client, self.base_url, self.tasks, self.hardware, self.time_limit, self.execution_timeout, self.date)
        )

    def matches(self, run: dict[str, Any]) -> bool:
        if self.tasks is not None and run.get("task") not in self.tasks:
            return False
        if self.hardware is not None and self.hardware not in str(run.get("hardware") or ""):
            return False
        if self.time_limit is not None and not _in_range(run.get("time_limit_secs"), self.time_limit):
            return False
        if self.execution_timeout is not None and not _in_range(run.get("execution_timeout"), self.execution_timeout):
            return False
        if not self._matches_client_endpoint(run):
            return False
        if self.date is not None and not (self.date[0] <= _launch_date(run) <= self.date[1]):
            return False
        return True

    def _matches_client_endpoint(self, run: dict[str, Any]) -> bool:
        if not self.client and not self.base_url:
            return True
        for endpoint, model_id in run.get("client_endpoints") or []:
            if self.base_url and not any(pattern in endpoint for pattern in self.base_url):
                continue
            if self.client and not any(pattern in model_id for pattern in self.client):
                continue
            return True
        return False

    def as_manifest(self) -> dict[str, Any]:
        """JSON-friendly copy for the output manifest."""
        return {
            "client": list(self.client) if self.client is not None else None,
            "base_url": list(self.base_url) if self.base_url is not None else None,
            "tasks": list(self.tasks) if self.tasks is not None else None,
            "hardware": self.hardware,
            "time_limit": list(self.time_limit) if self.time_limit is not None else None,
            "execution_timeout": list(self.execution_timeout) if self.execution_timeout is not None else None,
            "date": [day.isoformat() for day in self.date] if self.date is not None else None,
        }


def aggregate(
    batch_dirs: list[Path],
    output_dir: Path,
    filters: RunFilters | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Concatenate the (filtered) batches and write a merged dataset directory."""
    filters = filters or RunFilters()

    selected: list[tuple[Path, dict[str, Any], list[dict[str, Any]] | None, set[str] | None]] = []
    skipped_batches: list[str] = []
    runs_kept = 0
    runs_dropped = 0
    for batch_dir in batch_dirs:
        manifest = groupdata.read_manifest(batch_dir)
        runs = manifest.get("runs")
        kept: set[str] | None = None
        if filters.is_active():
            if runs is None:
                raise ValueError(
                    f"{batch_dir} has no per-run metadata in its manifest; "
                    "rebuild the batches with the current build_batch_groups before filtering"
                )
            kept = {run["run_dir"] for run in runs if filters.matches(run)}
            runs_kept += len(kept)
            runs_dropped += len(runs) - len(kept)
            if not kept:
                skipped_batches.append(manifest.get("batch", batch_dir.name))
                continue
        selected.append((batch_dir, manifest, runs, kept))
    if not selected:
        raise ValueError(f"No runs matched the filter (dropped {runs_dropped}): {skipped_batches}")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = 0
    groups = 0
    groups_dropped = 0
    seen_group_ids: set[str] = set()
    operators: Counter[str] = Counter()
    per_batch: list[dict[str, Any]] = []
    group_size_histogram: dict[str, int] = defaultdict(int)
    tasks: set[str] = set()
    providers: set[str] = set()
    clients: set[str] = set()
    client_endpoints: set[tuple[str, str]] = set()
    env_signatures: set[str] = set()
    resolved_episodes = 0
    episodes: set[str] = set()
    normalize_packages: set[bool] = set()

    with (
        (output_dir / groupdata.SAMPLES_FILE).open("w", encoding="utf-8") as samples_file,
        (output_dir / groupdata.GROUPS_FILE).open("w", encoding="utf-8") as groups_file,
    ):
        for batch_dir, manifest, runs, kept in selected:
            normalize_packages.add(bool(manifest.get("normalize_packages", True)))
            batch_samples = 0
            for sample in groupdata.iter_samples(batch_dir):
                if kept is not None and sample["run_dir"] not in kept:
                    continue
                groupdata.write_jsonl(samples_file, sample)
                batch_samples += 1
                samples += 1
                operators[sample["operator"]] += 1
                tasks.add(sample["task"])
                providers.update(sample["providers"])
                clients.update(sample["clients"])
                env_signatures.add(sample["env_signature"])
                if sample["episode_id"] not in episodes:
                    episodes.add(sample["episode_id"])
                    resolved_episodes += sample["episode_terminal_step"] is not None
            if runs is None:
                client_endpoints.update(tuple(pair) for pair in manifest.get("client_endpoints") or [])
            else:
                for run in runs:
                    if kept is None or run["run_dir"] in kept:
                        client_endpoints.update(tuple(pair) for pair in run.get("client_endpoints") or [])
            batch_groups = 0
            for group in groupdata.read_groups(batch_dir):
                if kept is not None:
                    members = [member for member in group["members"] if member["run_dir"] in kept]
                    if not members:
                        groups_dropped += 1
                        continue
                    group = {**group, "size": len(members), "members": members}
                if group["group_id"] in seen_group_ids:
                    raise ValueError(
                        f"Group {group['group_id']} appears in more than one batch "
                        f"({batch_dir}); batches must be disjoint"
                    )
                seen_group_ids.add(group["group_id"])
                groupdata.write_jsonl(groups_file, group)
                batch_groups += 1
                groups += 1
                group_size_histogram[str(group["size"])] += 1
            per_batch.append(
                {
                    "batch": manifest.get("batch", batch_dir.name),
                    "batch_dir": str(batch_dir),
                    "journals": manifest.get("journals"),
                    "samples": batch_samples,
                    "groups": batch_groups,
                }
            )

    size_histogram = dict(sorted(group_size_histogram.items(), key=lambda item: int(item[0])))
    if len(normalize_packages) != 1:
        raise ValueError(f"Batches disagree about normalize_packages: {sorted(normalize_packages)}")
    manifest = {
        "kind": "aggregate",
        "normalize_packages": normalize_packages.pop(),
        "filters": filters.as_manifest(),
        "skipped_batches": skipped_batches,
        "runs_kept": runs_kept,
        "runs_dropped": runs_dropped,
        "groups_dropped": groups_dropped,
        "batches": per_batch,
        "journals": sum(batch["journals"] or 0 for batch in per_batch),
        "samples": samples,
        "groups": groups,
        "tasks": sorted(tasks),
        "providers": sorted(providers),
        "clients": sorted(clients),
        "client_endpoints": sorted([base_url, model_id] for base_url, model_id in client_endpoints),
        "env_signatures": sorted(env_signatures),
        "environments": len(env_signatures),
        "episodes": len(episodes),
        "episodes_resolved": resolved_episodes,
        "operators": {name: count for name, count in operators.most_common()},
        "group_size_histogram": size_histogram,
    }
    groupdata.write_manifest(output_dir, manifest)
    if verbose:
        summary = {key: value for key, value in manifest.items() if key not in ("batches", "group_size_histogram")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return manifest


def _validate_integer_range(name: str, value_range: tuple[int, int] | None) -> tuple[int, int] | None:
    if value_range is None:
        return None
    lower, upper = value_range
    if lower > upper:
        raise ValueError(f"{name} lower bound must not exceed its upper bound")
    return (lower, upper)


def _validate_date_range(value_range: tuple[str, str] | None) -> tuple[datetime.date, datetime.date] | None:
    if value_range is None:
        return None
    try:
        lower, upper = (datetime.date.fromisoformat(value) for value in value_range)
    except ValueError as error:
        raise ValueError("date values must use YYYY-MM-DD format") from error
    if lower > upper:
        raise ValueError("date lower bound must not exceed its upper bound")
    return (lower, upper)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="Batch dataset directories, or parents whose immediate subdirectories are batches.",
    )
    parser.add_argument("--output-dir", required=True, help="Where to write the merged dataset directory.")
    parser.add_argument("--client", help="Keep runs whose model_id contains any of these '+'-separated strings.")
    parser.add_argument("--base-url", help="Keep runs whose base_url contains any of these '+'-separated strings.")
    parser.add_argument("--tasks", help="Comma-separated competition names to keep.")
    parser.add_argument("--hardware", help="Keep runs whose hardware contains this string.")
    parser.add_argument(
        "--time-limit",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="Keep runs whose solver time limit is in the inclusive range.",
    )
    parser.add_argument(
        "--execution-timeout",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        help="Keep runs whose execution timeout is in the inclusive range.",
    )
    parser.add_argument(
        "--date",
        "--date-range",
        dest="date",
        nargs=2,
        metavar=("START", "END"),
        help="Keep runs whose launch date is in the inclusive YYYY-MM-DD range.",
    )
    args = parser.parse_args()

    filters = RunFilters(
        client=parse_patterns(args.client),
        base_url=parse_patterns(args.base_url),
        tasks=tuple(args.tasks.split(",")) if args.tasks else None,
        hardware=args.hardware,
        time_limit=_validate_integer_range("time_limit", tuple(args.time_limit) if args.time_limit else None),
        execution_timeout=(
            _validate_integer_range("execution_timeout", tuple(args.execution_timeout) if args.execution_timeout else None)
        ),
        date=_validate_date_range(tuple(args.date) if args.date else None),
    )
    aggregate(
        find_batch_dirs([Path(path) for path in args.input]),
        Path(args.output_dir),
        filters=filters,
    )


if __name__ == "__main__":
    main()
