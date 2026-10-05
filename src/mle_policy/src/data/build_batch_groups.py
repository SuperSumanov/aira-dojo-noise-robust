"""Stage 1: group the episodes of one *batch* of runs.

A batch is a directory of runs that belong to the same experiment set -- the
same task, the same model, the same hardware, the same time limits.  Grouping is
done per batch and never across batches, because prompts from different
environments are not the same question even when they look alike.

The output is a dataset directory (see ``groupdata``); one per batch.  Run this
per batch, then merge with ``aggregate_groups``.  ``scripts/data/build_all_batches.sh``
does the looping.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import groupdata
from .journal import (
    CODE_OPERATORS,
    DEFAULT_JOURNAL_GLOB,
    find_run_dir,
    iter_journal_paths,
    iter_episodes,
    read_run_meta,
)


def build_batch(
    batch_dir: Path,
    output_dir: Path,
    batch_key: str | None = None,
    journal_glob: str = DEFAULT_JOURNAL_GLOB,
    normalize_packages: bool = True,
    max_journals: int | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Group every journal below *batch_dir* and write a dataset directory."""
    batch_dir = Path(batch_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_key = batch_key or batch_dir.name

    journals = list(iter_journal_paths(batch_dir, journal_glob))
    if max_journals is not None:
        journals = journals[:max_journals]
    if not journals:
        raise ValueError(f"No journals matching {journal_glob!r} below {batch_dir}")

    group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_tasks: dict[str, str] = {}
    seen_groups: set[str] = set()
    seen_samples: set[str] = set()
    operators = Counter()
    env_signatures: set[str] = set()
    tasks: set[str] = set()
    providers: set[str] = set()
    clients: set[str] = set()
    client_endpoints: set[tuple[str, str]] = set()
    hardware: set[str] = set()
    runs: dict[str, dict[str, Any]] = {}
    episodes_with_result = 0
    episode_ids: set[str] = set()

    with (output_dir / groupdata.SAMPLES_FILE).open("w", encoding="utf-8") as samples_file:
        for journal_path in journals:
            run_dir = find_run_dir(journal_path)
            run_meta = read_run_meta(run_dir)
            # Per-run metadata for aggregate_groups' filters; keyed by the path
            # the episode members use, so a filtered run can be located again.
            runs[str(run_dir.relative_to(batch_dir))] = {
                "run_dir": str(run_dir.relative_to(batch_dir)),
                "run_id": run_meta["run_id"],
                "task": run_meta["task"],
                "seed": run_meta["seed"],
                "launch_time": run_meta["launch_time"],
                "time_limit_secs": run_meta["time_limit_secs"],
                "execution_timeout": run_meta["execution_timeout"],
                "hardware": run_meta["hardware"],
                "clients": run_meta["clients"],
                "client_endpoints": run_meta["client_endpoints"],
            }
            env_signatures.add(run_meta["env_signature"])
            tasks.add(run_meta["task"])
            providers.update(run_meta["providers"])
            clients.update(run_meta["clients"])
            client_endpoints.update(tuple(pair) for pair in run_meta["client_endpoints"])
            if run_meta["hardware"]:
                hardware.add(run_meta["hardware"])
            for episode in iter_episodes(
                journal_path,
                run_meta,
                batch_key=batch_key,
                batch_dir=batch_dir,
                normalize_packages=normalize_packages,
            ):
                for sample in episode["samples"]:
                    if sample["sample_id"] in seen_samples:
                        continue
                    seen_samples.add(sample["sample_id"])
                    groupdata.write_jsonl(samples_file, sample)
                    operators[sample["operator"]] += 1

                episode_id = episode["episode_id"]
                if episode_id in episode_ids:
                    continue
                episode_ids.add(episode_id)
                episodes_with_result += episode["episode_resolved"]

                group_id = episode["group_id"]
                group_members[group_id].append(
                    {
                        "sample_id": episode["root_sample_id"],
                        "root_sample_id": episode["root_sample_id"],
                        "sample_ids": [sample["sample_id"] for sample in episode["samples"]],
                        "operator": episode["root_operator"],
                        "run_dir": episode["run_dir"],
                        "node_step": episode["episode_root_step"],
                        "episode_id": episode_id,
                        "node_has_result": episode["root_node_has_result"],
                        "node_reward": episode["root_node_reward"],
                        "episode_resolved": episode["episode_resolved"],
                        "episode_reward": episode["episode_reward"],
                    }
                )
                if group_id not in seen_groups:
                    seen_groups.add(group_id)
                    group_tasks[group_id] = episode["task"]

    groups: list[dict[str, Any]] = []
    for group_id, members in group_members.items():
        groups.append(
            {
                "group_id": group_id,
                "batch": batch_key,
                "task": group_tasks[group_id],
                "size": len(members),
                "members": sorted(members, key=lambda member: member["sample_id"]),
            }
        )
    groups.sort(key=lambda group: (group["task"], group["group_id"]))
    with (output_dir / groupdata.GROUPS_FILE).open("w", encoding="utf-8") as handle:
        for group in groups:
            groupdata.write_jsonl(handle, group)

    multi = [group for group in groups if group["size"] > 1]
    code_groups = [
        group for group in groups if any(member["operator"] in CODE_OPERATORS for member in group["members"])
    ]
    grpo_ready = [
        group
        for group in code_groups
        if sum(1 for member in group["members"] if member["operator"] in CODE_OPERATORS and member["episode_resolved"])
        >= 2
    ]
    manifest: dict[str, Any] = {
        "kind": "batch",
        "batch": batch_key,
        "batch_dir": str(batch_dir),
        "journals": len(journals),
        "samples": len(seen_samples),
        "groups": len(groups),
        "tasks": sorted(tasks),
        "providers": sorted(providers),
        "clients": sorted(clients),
        "client_endpoints": sorted([base_url, model_id] for base_url, model_id in client_endpoints),
        "runs": sorted(runs.values(), key=lambda run: run["run_dir"]),
        "hardware": sorted(hardware),
        "env_signatures": sorted(env_signatures),
        "environment_mixed": len(env_signatures) > 1,
        "normalize_packages": normalize_packages,
        "operators": {name: count for name, count in operators.most_common()},
        "episodes": len(episode_ids),
        "episodes_resolved": episodes_with_result,
        "multi_member_groups": len(multi),
        "grpo_ready_groups": len(grpo_ready),
        "group_size_histogram": groupdata.group_size_histogram(groups),
    }
    groupdata.write_manifest(output_dir, manifest)
    if verbose:
        if manifest["environment_mixed"]:
            print(
                f"[warn] batch {batch_key} mixes {len(env_signatures)} environments; "
                "groups are still separated by environment signature",
                file=sys.stderr,
            )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-dir", required=True, help="Directory holding the runs of one experiment set.")
    parser.add_argument("--output-dir", required=True, help="Where to write the batch dataset directory.")
    parser.add_argument("--batch-key", default=None, help="Stable name for this batch (default: directory name).")
    parser.add_argument("--journal-glob", default=DEFAULT_JOURNAL_GLOB)
    parser.add_argument("--max-journals", type=int, default=None, help="Read at most N journals (smoke tests).")
    parser.add_argument(
        "--no-package-normalisation",
        dest="normalize_packages",
        action="store_false",
        help="Hash prompts exactly, without sorting the shuffled package list.",
    )
    args = parser.parse_args()

    build_batch(
        batch_dir=Path(args.batch_dir),
        output_dir=Path(args.output_dir),
        batch_key=args.batch_key,
        journal_glob=args.journal_glob,
        normalize_packages=args.normalize_packages,
        max_journals=args.max_journals,
    )


if __name__ == "__main__":
    main()
