"""Compare hint-only and hint-plus-code on explicitly selected source episodes."""

import argparse
import asyncio
import difflib
import json
import os
from pathlib import Path

from .helper import atomic_json, parts
from .client import ModelClient
from .regenerate import append_rewrite, extract_hint, generation_options, regenerate
from .tree import episodes, operator, rebuild_links


async def compare(args):
    """Compare hint-only and source-code-assisted regeneration, saving prompts, responses, nodes, and diagnostics."""
    nodes = {
        row["data"]["step"]: row["data"]
        for row in (json.loads(line) for line in args.journal.read_text().splitlines() if line.strip())
    }
    by_root = {episode.root: episode for episode in episodes(list(nodes.values()))}
    run_dir = next(parent for parent in args.journal.parents if (parent / "dojo_config.json").is_file())
    operators = json.loads((run_dir / "dojo_config.json").read_text())["solver"]["operators"]
    client = ModelClient(args.base_url, args.api_key, args.model, args.output / "cache", args.concurrency)

    async def one(case, include_code, hint, hint_trace):
        """Generate one variant from the shared hint and save its traces, response, nodes, and diagnostics."""
        stage, target_root, donor_root = case.split(":")
        if stage not in ("debug", "improve"):
            raise ValueError(f"Invalid experiment stage: {stage}")
        target, donor = by_root[int(target_root)], by_root[int(donor_root)]
        if target.terminal is None or donor.terminal is None:
            raise ValueError("Experiments require resolved source episodes")
        if stage == "debug" and target != donor:
            raise ValueError("Debug case must use the same target and donor episode")
        generation = generation_options(operators[operator(nodes[target.root])]["llm"]["generation_kwargs"])
        rewrite_trace = {}
        result = await regenerate(
            stage, target, donor, nodes, client, include_code=include_code, generation=generation, hint=hint,
            trace=rewrite_trace,
        )
        code = nodes[donor.terminal]["code"]
        thinking, answer, block = parts(result["completion"])
        plan = answer[: block.start()].strip()
        name = case.replace(":", "-") + ("-with-code" if include_code else "-hint-only")
        directory = args.output / name
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / "hint_trace.json", hint_trace)
        atomic_json(directory / "rewrite_trace.json", rewrite_trace)
        atomic_json(directory / "original_prompt.json", nodes[target.root]["operators_metrics"][0]["prompt_messages"])
        (directory / "hint.md").write_text(result["hint"] + "\n", encoding="utf-8")
        (directory / "generated.md").write_text(result["completion"] + "\n", encoding="utf-8")
        output = []
        append_rewrite(output, stage, target, donor, nodes, result, str(args.journal))
        atomic_json(directory / "nodes.json", rebuild_links(output))
        diagnostics = {
            "case": case,
            "include_code": include_code,
            "source_journal": str(args.journal),
            "target_steps": target.steps,
            "donor_steps": donor.steps,
            "hint_characters": len(result["hint"]),
            "thinking_characters": len(thinking),
            "plan_characters": len(plan),
            "generated_code_similarity": difflib.SequenceMatcher(
                None, block.group("code"), code, autojunk=False
            ).ratio(),
            "generation_cache_key": result["cache_key"],
            "generation": generation,
            "response_origin": "regenerated",
            "execution_status": "not_run",
            "inherited_metric": nodes[donor.terminal]["metric"],
            "metric_source": {"step": donor.terminal, "id": nodes[donor.terminal]["id"]},
        }
        atomic_json(directory / "diagnostics.json", diagnostics)
        print(f"DONE {name}", flush=True)
        return diagnostics

    async def pair(case):
        """Validate one case, extract a shared hint, and run both regeneration variants concurrently."""
        stage, target_root, donor_root = case.split(":")
        target, donor = by_root[int(target_root)], by_root[int(donor_root)]
        if target.terminal is None or donor.terminal is None:
            raise ValueError("Experiments require resolved source episodes")
        if stage not in ("debug", "improve") or (stage == "debug" and target != donor):
            raise ValueError(f"Invalid experiment case: {case}")
        hint_trace = []
        hint = await extract_hint(stage, target, donor, nodes, client, trace=hint_trace)
        return await asyncio.gather(*(one(case, include, hint, hint_trace) for include in (False, True)))

    try:
        results = [
            result
            for pair_results in await asyncio.gather(*(pair(case) for case in args.case))
            for result in pair_results
        ]
    finally:
        await client.close()
    atomic_json(args.output / "summary.json", results)


def main():
    """Parse journal cases and model settings, then run the comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--case", action="append", required=True, help="stage:target_episode_root:donor_episode_root")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default=os.environ.get("HINDSIGHT_API_KEY", ""))
    parser.add_argument("--model", default="qwen3.8-27b")
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()
    asyncio.run(compare(args))


if __name__ == "__main__":
    main()
