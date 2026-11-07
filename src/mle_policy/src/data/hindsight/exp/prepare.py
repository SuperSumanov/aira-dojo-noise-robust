"""Collect hindsight rewrites and their controls into a resumable execution manifest."""

import argparse
import hashlib
import json
from pathlib import Path

from ..helper import atomic_json
from ..tree import episodes


def prepare(output: Path) -> None:
    """Prepare debug and improve cases without depending on experiment-specific seeds."""
    source = json.loads((output / "source.json").read_text())
    nodes = {
        row["data"]["step"]: row["data"] for row in map(json.loads, Path(source["journal"]).read_text().splitlines())
    }
    episode_map = {episode.root: episode for episode in episodes(list(nodes.values()))}
    records = []
    roots = set()
    debug_roots = set()
    donors = {}
    for directory in sorted((output / "generation").glob("*/diagnostics.json")):
        diagnostics = json.loads(directory.read_text())
        stage, target, donor = diagnostics["case"].split(":")
        target, donor = int(target), int(donor)
        rewritten = json.loads((directory.parent / "nodes.json").read_text())[-1]
        records.append(
            {
                "name": directory.parent.name,
                "stage": stage,
                "target_root": target,
                "donor_root": donor,
                "variant": "with-code" if diagnostics["include_code"] else "hint-only",
                "code": rewritten["code"],
                "plan": rewritten["plan"],
                "historical_debug_calls": len(episode_map[target].steps) - 1,
            }
        )
        roots.add(target)
        if stage == "debug":
            debug_roots.add(target)
        elif stage == "improve":
            donors[episode_map[donor].terminal] = (target, donor)
        else:
            raise ValueError(f"Unknown generation stage: {stage}")
    if not records:
        raise ValueError("No completed generations found")
    for root in sorted(roots):
        episode = episode_map[root]
        controls = [("terminal-reference", episode.terminal)]
        if root in debug_roots:
            controls.insert(0, ("original", root))
        for variant, step in controls:
            records.append(
                {
                    "name": f"{variant}-{root}",
                    "stage": "reference",
                    "target_root": root,
                    "donor_root": root,
                    "variant": variant,
                    "code": nodes[step]["code"],
                    "plan": nodes[step].get("plan"),
                    "source_step": step,
                    "historical_debug_calls": len(episode.steps) - 1,
                }
            )
    target_terminals = {episode_map[root].terminal for root in roots}
    for step, (target, donor) in sorted(donors.items()):
        if step in target_terminals:
            continue
        records.append(
            {
                "name": f"donor-reference-{step}",
                "stage": "reference",
                "target_root": target,
                "donor_root": donor,
                "variant": "donor-reference",
                "code": nodes[step]["code"],
                "plan": nodes[step].get("plan"),
                "source_step": step,
                "historical_debug_calls": len(episode_map[donor].steps) - 1,
            }
        )
    for record in records:
        history_root = record["donor_root"] if record["variant"] == "donor-reference" else record["target_root"]
        target_episode = episode_map[history_root]
        terminal = nodes[target_episode.terminal]
        record["historical_steps"] = list(target_episode.steps)
        record["historical_cv"] = terminal["metric"]
        record["historical_test"] = terminal.get("metric_info/score")
        record["historical_execution_seconds"] = sum(
            nodes[step].get("exec_time") or 0 for step in target_episode.steps
        )
        directory = output / "runs" / record["name"]
        directory.mkdir(parents=True, exist_ok=True)
        code_path = directory / "attempt-0.py"
        if code_path.exists() and code_path.read_text() != record["code"]:
            raise ValueError(f"Refusing to overwrite different code: {code_path}")
        code_path.write_text(record.pop("code"), encoding="utf-8")
        record["code_sha256"] = hashlib.sha256(code_path.read_bytes()).hexdigest()
        atomic_json(directory / "metadata.json", record)
    atomic_json(output / "manifest.json", {"source": source, "runs": records})
    print(f"Prepared {len(records)} solutions in {output / 'runs'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tmp/examples/hindsight/exp"))
    prepare(parser.parse_args().output)
