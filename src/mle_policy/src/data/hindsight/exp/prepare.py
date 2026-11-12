"""Prepare selected experiment cases and historical controls for GPU evaluation.

Input --generation: experiment.py output with */metadata.json and */nodes.json.
Output --output: manifest.json listing source files and every run's artifact
paths, plus runs/<name>/solution.py and runs/<name>/metadata.json. evaluate.py
consumes manifest.json; it never calls prepare.
"""

import argparse
import json
from pathlib import Path

from ..helper import write_json
from ..tree import episodes


def prepare(generation: Path, output: Path) -> None:
    """Collect generated cases, add their controls, and write an execution manifest."""
    candidates = []
    paths = sorted(generation.glob("*/metadata.json"))
    first = json.loads(paths[0].read_text())
    source = {"journal": first["source_journal"], "config": first["source_config"]}
    for path in paths:
        metadata = json.loads(path.read_text())
        if metadata["source_journal"] != source["journal"] or metadata["source_config"] != source["config"]:
            raise ValueError("An experiment must use one source journal and config")
        stage, target, donor = metadata["case"].split(":")
        rewritten = json.loads((path.parent / "nodes.json").read_text())[-1]
        candidates.append((path.parent.name, stage, int(target), int(donor), metadata["include_code"], rewritten))
    nodes = {
        row["data"]["step"]: row["data"] for row in map(json.loads, Path(source["journal"]).read_text().splitlines())
    }
    episode_map = {episode.root: episode for episode in episodes(list(nodes.values()))}
    records = []
    roots = set()
    debug_roots = set()
    donors = {}
    for name, stage, target, donor, include_code, rewritten in candidates:
        records.append(
            {
                "name": name,
                "stage": stage,
                "target_root": target,
                "donor_root": donor,
                "variant": "with-code" if include_code else "hint-only",
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
        record["solution"] = f"runs/{record['name']}/solution.py"
        record["metadata"] = f"runs/{record['name']}/metadata.json"
        record["result"] = f"runs/{record['name']}/result.json"
        record["worker_log"] = f"runs/{record['name']}/worker-0.log"
        (output / record["solution"]).write_text(record.pop("code"), encoding="utf-8")
        write_json(output / record["metadata"], record)
    write_json(output / "manifest.json", {"source": source, "runs": records})
    print(f"Prepared {len(records)} solutions in {output / 'runs'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, required=True, help="experiment.py output directory")
    parser.add_argument("--output", type=Path, required=True, help="Write manifest.json and runs/ here")
    args = parser.parse_args()
    prepare(args.generation, args.output)
