"""Rewrite every run under --input into the same relative layout under --output.

Input per run: dojo_config.json, optional env_variables.json, json/JOURNAL.jsonl.
Output per run: copied metadata, json/JOURNAL.jsonl (big journal), and
checkpoint/journal.jsonl (small journal). No other files are written.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from contextlib import AsyncExitStack
import shutil

from .client import ModelClient
from .regenerate import append_rewrite, generation_options, regenerate
from .tree import better, episodes, operator, rebuild_links


async def rewrite(
    nodes: list[dict],
    clients: dict,
    *,
    include_code: bool = False,
    source_journal: str = "",
    generations: dict | None = None,
    mode: str = "debug-improve",
) -> list[dict]:
    """Regenerate resolved debug trajectories and optionally absorb better improvement proposals."""
    if mode not in ("debug", "debug-improve"):
        raise ValueError(f"Unknown hindsight mode: {mode!r}")
    original = {node["step"]: node for node in nodes}
    source_episodes = episodes(nodes)
    debug_episodes = [
        episode for episode in source_episodes if episode.terminal is not None and len(episode.steps) > 1
    ]
    output = []
    generations = generations or {}

    async def generate(stage, target, donor):
        """Read sampling settings from the target operator and regenerate one candidate response."""
        return await regenerate(
            stage,
            target,
            donor,
            original,
            clients[operator(original[target.root])],
            include_code=include_code,
            generation=generation_options(generations.get(operator(original[target.root]))),
        )

    rewritten = await asyncio.gather(*(generate("debug", episode, episode) for episode in debug_episodes))
    for episode, result in zip(debug_episodes, rewritten):
        append_rewrite(output, "debug", episode, episode, original, result, source_journal)

    terminal_episode = {episode.terminal: episode for episode in source_episodes if episode.terminal is not None}
    candidates = []
    for donor in source_episodes if mode == "debug-improve" else ():
        donor_root = original[donor.root]
        if operator(donor_root) != "improve" or donor.terminal is None:
            continue
        parents = donor_root.get("parents", [])
        if not parents or parents[0] not in terminal_episode:
            continue
        parent_episode = terminal_episode[parents[0]]
        if better(original[donor.terminal], original[parent_episode.terminal]):
            candidates.append((parent_episode, donor))
    improvements = await asyncio.gather(*(generate("improve", target, donor) for target, donor in candidates))
    for (target, donor), result in zip(candidates, improvements):
        append_rewrite(output, "improve", target, donor, original, result, source_journal)
    return rebuild_links(output)


def write_lines(path: Path, rows: list[dict]) -> None:
    """Write JSONL rows directly to the destination journal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def checkpoint_node(node: dict) -> dict:
    """Convert flat metric_info/ fields into the nested checkpoint representation."""
    result = {key: value for key, value in node.items() if not key.startswith("metric_info/")}
    info = {key.split("/", 1)[1]: value for key, value in node.items() if key.startswith("metric_info/")}
    if info:
        result["metric_info"] = info
    return result


async def run(args: argparse.Namespace) -> None:
    """Rewrite journals once, copying run metadata and writing both journal formats."""
    source, output = args.input.resolve(), args.output.resolve()
    requests = asyncio.Semaphore(args.concurrency)
    semaphore = asyncio.Semaphore(args.journal_workers)

    async def process(path: Path) -> None:
        async with semaphore:
            relative = path.relative_to(source)
            destination = output / relative
            run_dir = next(parent for parent in path.parents if (parent / "dojo_config.json").is_file())
            config = json.loads((run_dir / "dojo_config.json").read_text(encoding="utf-8"))
            generations = {
                name: settings["llm"].get("generation_kwargs")
                for name, settings in config["solver"]["operators"].items()
            }
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            async with AsyncExitStack() as stack:
                clients = {}
                for name, settings in config["solver"]["operators"].items():
                    client = ModelClient(settings["llm"]["client"], requests)
                    stack.push_async_callback(client.close)
                    clients[name] = client
                rewritten = await rewrite(
                    [row["data"] for row in rows],
                    clients,
                    include_code=args.hint_code == "include",
                    source_journal=str(relative),
                    generations=generations,
                    mode=args.mode,
                )
            target_run = output / run_dir.relative_to(source)
            target_run.mkdir(parents=True, exist_ok=True)
            shutil.copy2(run_dir / "dojo_config.json", target_run / "dojo_config.json")
            if (run_dir / "env_variables.json").is_file():
                shutil.copy2(run_dir / "env_variables.json", target_run / "env_variables.json")
            timestamp = rows[-1]["timestamp"] if rows else None
            # Big journal: each row wraps the node in data, for the big_journal reader.
            write_lines(
                destination,
                [{"timestamp": timestamp, "step": node["step"], "data": node} for node in rewritten],
            )
            # Small journal: each row is a node, for the checkpoint journal reader.
            write_lines(target_run / "checkpoint/journal.jsonl", [checkpoint_node(node) for node in rewritten])
            print(f"DONE {relative}: {len(rows)} -> {len(rewritten)} nodes", flush=True)

    await asyncio.gather(*(process(path) for path in sorted(source.rglob("JOURNAL.jsonl"))))


def main() -> None:
    """Parse batch-generation paths and concurrency, then start generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/augmented_mle_critic/raw_journal/hindsight/1028"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/augmented_mle_critic/raw_journal/hindsight/1028_hindsight_v3")
    )
    parser.add_argument(
        "--concurrency", type=int, default=24, help="Maximum simultaneous model requests across all journals"
    )
    parser.add_argument("--journal-workers", type=int, default=8, help="Maximum journals being rewritten concurrently")
    parser.add_argument(
        "--hint-code",
        choices=("include", "omit"),
        default="omit",
        help="Include or omit the donor terminal code in the regeneration prompt",
    )
    parser.add_argument(
        "--mode",
        choices=("debug", "debug-improve"),
        default="debug-improve",
        help="Generate debug hindsight only, or both debug and improve hindsight",
    )
    args = parser.parse_args()
    if args.concurrency < 1 or args.journal_workers < 1:
        parser.error("Concurrency and journal workers must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
