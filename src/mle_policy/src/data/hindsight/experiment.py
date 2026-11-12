"""Compare hint-only and hint-plus-code on selected episodes of one big journal.

Input --journal: <run>/json/JOURNAL.jsonl with <run>/dojo_config.json.
Output --output: <case>-hint-only/ and <case>-with-code/, each containing
metadata.json (source/case/settings), trace.json (hint and regeneration calls),
and nodes.json (rewritten nodes). exp.prepare consumes this directory.
"""

import argparse
import asyncio
import json
from pathlib import Path
from contextlib import AsyncExitStack

from .helper import write_json
from .client import ModelClient
from .regenerate import append_rewrite, extract_hint, generation_options, regenerate
from .tree import episodes, operator, rebuild_links


async def compare(args):
    """Compare hint-only and source-code-assisted regeneration, saving one trace, metadata, and nodes per variant."""
    nodes = {
        row["data"]["step"]: row["data"]
        for row in (json.loads(line) for line in args.journal.read_text().splitlines() if line.strip())
    }
    by_root = {episode.root: episode for episode in episodes(list(nodes.values()))}
    run_dir = next(parent for parent in args.journal.parents if (parent / "dojo_config.json").is_file())
    operators = json.loads((run_dir / "dojo_config.json").read_text())["solver"]["operators"]
    requests = asyncio.Semaphore(args.concurrency)

    async def one(case, include_code, hint, hint_trace, client):
        """Generate one variant from the shared hint and save its traces, response, nodes, and diagnostics."""
        stage, target_root, donor_root = case.split(":")
        target, donor = by_root[int(target_root)], by_root[int(donor_root)]
        generation = generation_options(operators[operator(nodes[target.root])]["llm"].get("generation_kwargs"))
        rewrite_trace = {}
        result = await regenerate(
            stage,
            target,
            donor,
            nodes,
            client,
            include_code=include_code,
            generation=generation,
            hint=hint,
            trace=rewrite_trace,
        )
        name = case.replace(":", "-") + ("-with-code" if include_code else "-hint-only")
        directory = args.output / name
        directory.mkdir(parents=True, exist_ok=True)
        write_json(directory / "trace.json", {"hint": hint_trace, "rewrite": rewrite_trace})
        output = []
        append_rewrite(output, stage, target, donor, nodes, result, str(args.journal))
        write_json(directory / "nodes.json", rebuild_links(output))
        write_json(
            directory / "metadata.json",
            {
                "case": case,
                "include_code": include_code,
                "source_journal": str(args.journal.resolve()),
                "source_config": str((run_dir / "dojo_config.json").resolve()),
                "generation": generation,
            },
        )
        print(f"DONE {name}", flush=True)

    async def pair(case):
        """Validate one case, extract a shared hint, and run both regeneration variants concurrently."""
        stage, target_root, donor_root = case.split(":")
        target, donor = by_root[int(target_root)], by_root[int(donor_root)]
        if target.terminal is None or donor.terminal is None:
            raise ValueError("Experiments require resolved source episodes")
        if stage not in ("debug", "improve") or (stage == "debug" and target != donor):
            raise ValueError(f"Invalid experiment case: {case}")
        client = clients[operator(nodes[target.root])]
        hint_trace = []
        hint = await extract_hint(stage, target, donor, nodes, client, trace=hint_trace)
        await asyncio.gather(*(one(case, include, hint, hint_trace, client) for include in (False, True)))

    async with AsyncExitStack() as stack:
        clients = {}
        for name, settings in operators.items():
            client = ModelClient(settings["llm"]["client"], requests)
            stack.push_async_callback(client.close)
            clients[name] = client
        await asyncio.gather(*(pair(case) for case in args.case))


def main():
    """Parse journal cases and concurrency, then run the comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True, type=Path, help="Source <run>/json/JOURNAL.jsonl")
    parser.add_argument("--case", action="append", required=True, help="stage:target_episode_root:donor_episode_root")
    parser.add_argument("--output", required=True, type=Path, help="Generation directory consumed by exp.prepare")
    parser.add_argument("--concurrency", type=int, default=6, help="Maximum simultaneous model requests")
    args = parser.parse_args()
    asyncio.run(compare(args))


if __name__ == "__main__":
    main()
