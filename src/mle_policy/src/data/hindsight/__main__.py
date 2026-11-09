"""Rewrite search journals, then save the output run trees."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil

from .helper import VERSION, atomic_json
from .client import ModelClient
from .regenerate import append_rewrite, generation_options, regenerate
from .tree import better, episodes, operator, rebuild_links, validate


async def rewrite(
    nodes: list[dict],
    client,
    *,
    include_code: bool = False,
    source_journal: str = "",
    generations: dict | None = None,
    mode: str = "debug-improve",
) -> tuple[list[dict], dict]:
    """Regenerate resolved debug trajectories and optionally absorb better improvement proposals."""
    if mode not in ("debug", "debug-improve"):
        raise ValueError(f"Unknown hindsight mode: {mode!r}")
    validate(nodes)
    original = {node["step"]: copy.deepcopy(node) for node in nodes}
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
            client,
            include_code=include_code,
            generation=generation_options(generations.get(operator(original[target.root]))),
        )

    rewritten = await asyncio.gather(*(generate("debug", episode, episode) for episode in debug_episodes))
    debug_records = []
    for episode, result in zip(debug_episodes, rewritten):
        debug_records.append(append_rewrite(output, "debug", episode, episode, original, result, source_journal))

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
    improve_records = []
    for (target, donor), result in zip(candidates, improvements):
        improve_records.append(append_rewrite(output, "improve", target, donor, original, result, source_journal))
    output = rebuild_links(output)
    report = {
        "input_nodes": len(nodes),
        "response_origin": "regenerated",
        "metric_origin": "inherited",
        "execution_status": "not_run",
        "mode": mode,
        "output_nodes": len(output),
        "debug_rewrites": debug_records,
        "improve_rewrites": improve_records,
        "rewrites_by_target_operator": {
            stage: dict(Counter(operator(original[item["root"]]) for item in records))
            for stage, records in (("debug", debug_records), ("improve", improve_records))
        },
    }
    return output, report


def write_lines(path: Path, rows: list[dict]) -> None:
    """Write journal rows to a temporary file and replace the destination after completion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def checkpoint_node(node: dict) -> dict:
    """Convert flat metric_info/ fields into the nested checkpoint representation."""
    result = {key: value for key, value in node.items() if not key.startswith("metric_info/")}
    info = {key.split("/", 1)[1]: value for key, value in node.items() if key.startswith("metric_info/")}
    if info:
        result["metric_info"] = info
    return result


async def run(args: argparse.Namespace) -> None:
    """Process input journals with bounded concurrency, saving synthetic trees, run metadata, and aggregate reports."""
    source, output = args.input.resolve(), args.output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Input and output trees must be separate")
    paths = sorted(source.rglob("JOURNAL.jsonl"))
    if not paths:
        raise ValueError(f"No JOURNAL.jsonl found in {source}")
    client = ModelClient(args.base_url, args.api_key, args.model, output / "_hindsight/cache", args.concurrency)
    semaphore = asyncio.Semaphore(args.journal_workers)
    failures = []
    summaries = []

    async def process(path: Path) -> None:
        """Reuse validated artifacts or regenerate one journal, then save both tree formats and a fingerprinted report."""
        async with semaphore:
            relative = path.relative_to(source)
            destination = output / relative
            report_path = output / "_hindsight/reports" / relative.with_suffix(".json")
            content = path.read_bytes()
            fingerprint = hashlib.sha256(content).hexdigest()
            identity = {
                "source_sha256": fingerprint,
                "version": VERSION,
                "model": args.model,
                "mode": args.mode,
                "hint_code": args.hint_code,
            }
            try:
                run_dir = next(parent for parent in path.parents if (parent / "dojo_config.json").is_file())
                metadata = [
                    run_dir / name for name in ("dojo_config.json", "env_variables.json") if (run_dir / name).exists()
                ]
                identity["metadata_sha256"] = {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in metadata
                }
                if report_path.exists():
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    artifacts = report.get("artifacts", {})
                    if (
                        all(report.get(key) == value for key, value in identity.items())
                        and artifacts
                        and all(
                            (output / name).is_file()
                            and hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
                            for name, digest in artifacts.items()
                        )
                    ):
                        summaries.append(
                            {"journal": str(relative), "status": "cached", "nodes": report["output_nodes"]}
                        )
                        print(f"CACHED {relative}", flush=True)
                        return
                rows = [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]
                nodes = [row["data"] for row in rows]
                config = json.loads((run_dir / "dojo_config.json").read_text(encoding="utf-8"))
                generations = {
                    name: settings.get("llm", {}).get("generation_kwargs", {})
                    for name, settings in config.get("solver", {}).get("operators", {}).items()
                }
                rewritten, report = await rewrite(
                    nodes,
                    client,
                    include_code=args.hint_code == "include",
                    source_journal=str(relative),
                    generations=generations,
                    mode=args.mode,
                )
                validate(rewritten)
                target_run = output / run_dir.relative_to(source)
                target_run.mkdir(parents=True, exist_ok=True)
                for path in metadata:
                    shutil.copy2(path, target_run / path.name)
                envelopes = {
                    row["data"]["id"]: {key: value for key, value in row.items() if key != "data"} for row in rows
                }
                timestamp = rows[-1].get("timestamp") if rows else None
                write_lines(
                    destination,
                    [
                        {**envelopes.get(node["id"], {"timestamp": timestamp}), "step": node["step"], "data": node}
                        for node in rewritten
                    ],
                )
                checkpoint = target_run / "checkpoint/journal.jsonl"
                write_lines(checkpoint, [checkpoint_node(node) for node in rewritten])
                report.update(identity)
                report["artifacts"] = {
                    str(artifact.relative_to(output)): hashlib.sha256(artifact.read_bytes()).hexdigest()
                    for artifact in (destination, checkpoint, *(target_run / path.name for path in metadata))
                }
                atomic_json(report_path, report)
                summaries.append({"journal": str(relative), "status": "written", "nodes": len(rewritten)})
                print(
                    f"DONE {relative}: {len(nodes)} -> {len(rewritten)} nodes; "
                    f"debug={len(report['debug_rewrites'])}, "
                    f"improve={len(report['improve_rewrites'])}",
                    flush=True,
                )
            except Exception as error:
                failures.append({"journal": str(relative), "error": f"{type(error).__name__}: {error}"})
                print(f"FAILED {relative}: {error}", flush=True)

    try:
        await asyncio.gather(*(process(path) for path in paths))
    finally:
        await client.close()
    atomic_json(
        output / "_hindsight/summary.json",
        {
            "input": str(source),
            "output": str(output),
            "model": args.model,
            "mode": args.mode,
            "concurrency": args.concurrency,
            "journal_workers": args.journal_workers,
            "journals": sorted(summaries, key=lambda item: item["journal"]),
            "failures": failures,
        },
    )
    if failures:
        raise RuntimeError(
            f"{len(failures)}/{len(paths)} journals failed; see _hindsight/summary.json. Rerun to resume."
        )


def main() -> None:
    """Parse batch-generation paths, model settings, and concurrency, then start generation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/augmented_mle_critic/raw_journal/hindsight/1028"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/augmented_mle_critic/raw_journal/hindsight/1028_hindsight_v3")
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default=os.environ.get("HINDSIGHT_API_KEY", ""))
    parser.add_argument("--model", default="qwen3.8-27b")
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--journal-workers", type=int, default=8)
    parser.add_argument("--hint-code", choices=("include", "omit"), default="omit")
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
