"""Which LLM endpoint and model each run in a journal tree actually used.

The data-collection runs under ``data/augmented_mle_critic/raw_journal`` were
driven by many different models across many different API vendors, and the
quality of the resulting trajectories depends on which one ran the run.  Before
trusting a task-level result it is worth asking: for this task, which
endpoints/models did we actually run, and how many runs each?

The field called ``provider`` in ``dojo_config.json`` does **not** answer that.
It is the litellm client protocol and is ``openai`` for every run under
``raw_journal`` -- it only says the endpoints speak the OpenAI chat-completions
format.  The thing that varies is the pair of ``base_url`` (the vendor) and
``model_id`` (the model on that vendor).  So this tool reports
``(base_url, model_id)`` by default, and can also group by ``base_url`` or
``model_id`` alone.

Layout it understands (``comparison/`` is skipped by default, see ``--skip``):

    raw_journal/<date>/<user>_issue_<issue>/<run>/dojo_config.json
    raw_journal/<date>/<user>_issue_<issue>/<run>/checkpoint/journal.jsonl

A run without ``checkpoint/journal.jsonl`` was killed before it wrote anything
and is reported with ``has_journal=False``, counted but flagged; pass
``--require-journal`` to drop those runs entirely.

Usage::

    python -m src.data.run_inventory --root <journal-root> --list-tasks
    python -m src.data.run_inventory --root <journal-root> --task <task> [--task <task> ...]
    python -m src.data.run_inventory --root <journal-root> --task <task> --runs
    python -m src.data.run_inventory --root <journal-root> --task <task> --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .journal import read_run_meta

# Directory names skipped when walking unless the caller overrides --skip.
DEFAULT_SKIP_DIRS = ("comparison",)

_RUN_NAME_RE = re.compile(r"^user_(?P<user>.+?)_issue_(?P<issue>.+)$")

CONFIG_NAME = "dojo_config.json"
JOURNAL_REL = Path("checkpoint") / "journal.jsonl"


@dataclass(frozen=True)
class OperatorClient:
    """One operator's LLM client, as recorded in the run config."""

    operator: str
    model_id: str
    provider: str
    base_url: str

    @property
    def key(self) -> tuple[str, str]:
        """The rule that decides whether two runs used the "same provider"."""
        return (self.base_url, self.model_id)


@dataclass
class RunRecord:
    """Everything about one run that the inventory queries need."""

    run_dir: Path
    rel_dir: str
    task: str
    seed: int | None
    clients: list[OperatorClient] = field(default_factory=list)
    has_journal: bool = False

    @property
    def date(self) -> str:
        return self.rel_dir.split("/", 1)[0] if "/" in self.rel_dir else ""

    @property
    def user(self) -> str:
        return self._name_parts()[0]

    @property
    def issue(self) -> str:
        return self._name_parts()[1]

    def _name_parts(self) -> tuple[str, str]:
        """``(user, issue)`` parsed from the run dir or, for ``raw_journal``,
        from its parent: the dir holding the seeds is named ``user_<u>_issue_<i>``."""
        for candidate in (self.run_dir.parent.name, self.run_dir.name):
            match = _RUN_NAME_RE.match(candidate)
            if match:
                return match.group("user"), match.group("issue")
        return "", self.run_dir.name

    @property
    def model_keys(self) -> tuple[tuple[str, str], ...]:
        """Distinct ``(base_url, model_id)`` used across this run's operators."""
        return tuple(sorted({client.key for client in self.clients}))

    @property
    def is_mixed(self) -> bool:
        """True when operators of one run used different endpoints/models."""
        return len(self.model_keys) > 1


def iter_run_dirs(root: Path, skip: Iterable[str] = DEFAULT_SKIP_DIRS) -> Iterator[Path]:
    """Yield every run directory (a dir holding ``dojo_config.json``) below *root*.

    A run directory may sit at any depth, so match on the config file and skip
    any path that passes through one of *skip*'s components (``comparison`` by
    default).  Nothing below a run directory is walked into: a run holds
    checkpoints and results, never another run, and pruning there keeps the
    walk over a tree of tens of GB to a few seconds.
    """
    skip = tuple(part for part in skip if part)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in skip)
        if CONFIG_NAME in filenames:
            dirnames[:] = []
            yield Path(dirpath)


def read_run_clients(run_dir: Path) -> list[OperatorClient]:
    """Read one operator per solver operator from ``dojo_config.json``."""
    config = json.loads((run_dir / CONFIG_NAME).read_text(encoding="utf-8"))
    operators = (config.get("solver") or {}).get("operators") or {}
    clients: list[OperatorClient] = []
    for operator, spec in operators.items():
        client = ((spec or {}).get("llm") or {}).get("client") or {}
        clients.append(
            OperatorClient(
                operator=operator,
                model_id=str(client.get("model_id") or ""),
                provider=str(client.get("provider") or ""),
                base_url=str(client.get("base_url") or ""),
            )
        )
    return clients


def read_run_record(run_dir: Path, root: Path) -> RunRecord:
    """Build the record for a single run."""
    meta = read_run_meta(run_dir)
    return RunRecord(
        run_dir=run_dir,
        rel_dir=run_dir.relative_to(root).as_posix(),
        task=meta["task"],
        seed=meta.get("seed"),
        clients=read_run_clients(run_dir),
        has_journal=(run_dir / JOURNAL_REL).is_file(),
    )


def collect_inventory(
    root: Path,
    skip: Iterable[str] = DEFAULT_SKIP_DIRS,
    tasks: Iterable[str] | None = None,
) -> list[RunRecord]:
    """Walk *root* and return one record per run, optionally filtered by task."""
    wanted = set(tasks) if tasks else None
    records: list[RunRecord] = []
    for run_dir in iter_run_dirs(root, skip=skip):
        try:
            record = read_run_record(run_dir, root)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"[warn] skipping {run_dir}: {error}")
            continue
        if wanted is not None and record.task not in wanted:
            continue
        records.append(record)
    return records


def filter_records(records: Iterable[RunRecord], require_journal: bool = False) -> list[RunRecord]:
    return [record for record in records if record.has_journal] if require_journal else list(records)


def group_records(records: Iterable[RunRecord], group_by: str = "endpoint_model") -> dict[str, list[RunRecord]]:
    """Bucket records by task, then by provider key.

    ``group_by`` decides the key:

    ``endpoint_model`` (default)  ``base_url`` + ``model_id`` -- the real axis.
    ``endpoint``                  ``base_url`` only (vendor / API endpoint).
    ``model``                     ``model_id`` only.
    ``provider``                  the config's ``provider`` field (always ``openai``).
    """
    if group_by not in ("endpoint_model", "endpoint", "model", "provider"):
        raise ValueError(f"Unsupported group_by: {group_by}")

    def key_for(client: OperatorClient) -> str:
        if group_by == "endpoint":
            return client.base_url or "<none>"
        if group_by == "model":
            return client.model_id or "<none>"
        if group_by == "provider":
            return client.provider or "<none>"
        return f"{client.base_url or '<none>'} :: {client.model_id or '<none>'}"

    per_task: dict[str, dict[str, list[RunRecord]]] = {}
    for record in records:
        bucket = per_task.setdefault(record.task, {})
        keys = {key_for(client) for client in record.clients}
        for key in keys:
            bucket.setdefault(key, []).append(record)
    return per_task


def list_tasks(records: Iterable[RunRecord]) -> dict[str, int]:
    """Task name -> number of runs collected."""
    return dict(Counter(record.task for record in records))


def _print_table(records: list[RunRecord], group_by: str, show_runs: bool) -> None:
    by_task = group_records(records, group_by=group_by)
    for task in sorted(by_task):
        task_records = {record.rel_dir: record for record in records if record.task == task}
        with_journal = sum(1 for record in task_records.values() if record.has_journal)
        print(f"\n{task}  ({len(task_records)} runs, {with_journal} with journal)")
        print(f"  {'provider key':58s} {'runs':>5s}  {'journal':>7s}")
        for key, bucket in sorted(by_task[task].items(), key=lambda kv: (-len(kv[1]), kv[0])):
            runs = {record.rel_dir: record for record in bucket}
            journals = sum(1 for record in runs.values() if record.has_journal)
            print(f"  {key:58s} {len(runs):5d}  {journals:7d}")
            if show_runs:
                for rel_dir in sorted(runs):
                    marker = " " if runs[rel_dir].has_journal else "!"
                    mixed = " [mixed operators]" if runs[rel_dir].is_mixed else ""
                    print(f"      {marker} {rel_dir}{mixed}")
        mixed = [record.rel_dir for record in task_records.values() if record.is_mixed]
        if mixed:
            print(f"  [warn] {len(mixed)} run(s) used different models across operators:")
            for rel_dir in sorted(mixed):
                print(f"      {rel_dir}")


def _as_json(records: list[RunRecord], group_by: str) -> dict[str, Any]:
    by_task = group_records(records, group_by=group_by)
    tasks: dict[str, Any] = {}
    for task in sorted(by_task):
        groups = {
            key: {
                "runs": len({record.rel_dir for record in bucket}),
                "with_journal": sum(
                    1 for record in {r.rel_dir: r for r in bucket}.values() if record.has_journal
                ),
                "run_dirs": sorted({record.rel_dir for record in bucket}),
            }
            for key, bucket in sorted(by_task[task].items())
        }
        tasks[task] = {"groups": groups}
    return {"group_by": group_by, "tasks": tasks}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="Journal root, e.g. data/augmented_mle_critic/raw_journal.")
    parser.add_argument("--task", action="append", default=None, help="Task name to include; repeatable.")
    parser.add_argument("--group-by", choices=("endpoint_model", "endpoint", "model", "provider"), default="endpoint_model")
    parser.add_argument("--runs", action="store_true", help="Also list the run directory of every count.")
    parser.add_argument("--list-tasks", action="store_true", help="Print task names and run counts, then stop.")
    parser.add_argument("--require-journal", action="store_true", help="Drop runs that never wrote checkpoint/journal.jsonl.")
    parser.add_argument("--skip", action="append", default=None, help=f"Path component to skip (default: {DEFAULT_SKIP_DIRS[0]}).")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a table.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    skip = tuple(args.skip) if args.skip is not None else DEFAULT_SKIP_DIRS
    records = collect_inventory(root, skip=skip, tasks=args.task)

    if args.list_tasks:
        for task, count in sorted(list_tasks(records).items()):
            print(f"{count:5d}  {task}")
        return

    records = filter_records(records, require_journal=args.require_journal)
    if args.json:
        print(json.dumps(_as_json(records, args.group_by), indent=2))
    else:
        _print_table(records, args.group_by, args.runs)


if __name__ == "__main__":
    main()
