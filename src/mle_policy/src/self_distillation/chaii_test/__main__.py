"""Replay one journal's step 1 with its recorded generation settings."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .evaluation import analyze_record, response_mode, summarize

def read_step_one(path: Path) -> tuple[dict, dict, dict]:
    """Read json/JOURNAL.jsonl or checkpoint/journal.jsonl and its run config."""
    config = json.loads((path.parent.parent / "dojo_config.json").read_text(encoding="utf-8"))
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            node = record["data"] if "data" in record else record
            if node["step"] == 1:
                index = node["operators_used"].index("draft")
                return node, node["operators_metrics"][index], config
    raise ValueError(f"No step 1 in {path}")


async def sample(args, client: httpx.AsyncClient) -> dict:
    """Replay step 1 unchanged, saving completed responses and partial summaries."""
    node, call, config = read_step_one(args.journal)
    generation_kwargs = dict(config["solver"]["operators"]["draft"]["llm"]["generation_kwargs"])
    generation_kwargs.pop("allowed_openai_params", None)
    payload = {
        **generation_kwargs,
        "model": args.model_id,
        "messages": call["prompt_messages"],
        "n": 1,
    }
    prompt_json = json.dumps(payload["messages"], ensure_ascii=False, sort_keys=True)
    mode = response_mode(payload, args.response_mode)
    metadata = {
        "response_mode": mode,
        "schema_version": 2,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "journal": str(args.journal.resolve()),
        "step": node["step"],
        "node_id": node["id"],
        "prompt_sha256": hashlib.sha256(prompt_json.encode()).hexdigest(),
        "base_url": args.base_url,
        "request": payload,
        "n": args.n,
        "concurrency": args.concurrency,
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "request.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    semaphore = asyncio.Semaphore(args.concurrency)

    async def generate(index: int) -> dict:
        record = {"sample_index": index}
        async with semaphore:
            try:
                response = await client.post(args.base_url.rstrip("/") + "/chat/completions", json=payload)
                response.raise_for_status()
                raw = response.json()
                record["response"] = raw
                if len(raw["choices"]) != 1:
                    raise ValueError("Expected exactly one response choice")
                choice = raw["choices"][0]
                message = choice["message"]
                record["finish_reason"] = choice["finish_reason"]
                record["analysis"] = analyze_record(record, mode)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
                record["error"] = f"{type(error).__name__}: {error}"
        return record

    records = []
    tasks = [asyncio.create_task(generate(index)) for index in range(args.n)]
    with (args.output_dir / "responses.jsonl").open("w", encoding="utf-8") as handle:
        try:
            for pending in asyncio.as_completed(tasks):
                record = await pending
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                summary = {
                    **metadata, **summarize([record if "error" in record else record["analysis"] for record in records]), "requested": args.n,
                    "completed": len(records), "unfinished": args.n - len(records),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                temporary = args.output_dir / "summary.json.tmp"
                temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
                temporary.replace(args.output_dir / "summary.json")
                print(
                    f"{len(records)}/{args.n}: sample={record['sample_index']} "
                    f"{record.get('error', record.get('analysis'))}", flush=True,
                )
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--base-url", required=True, help="API root including /v1")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory")
    parser.add_argument("--response-mode", choices=["auto", "thinking", "answer"], default="auto")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=6)
    args = parser.parse_args()
    if min(args.n, args.concurrency) < 1:
        parser.error("n and concurrency must be positive")

    async def run() -> dict:
        async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
            return await sample(args, client)

    result = asyncio.run(run())
    print(json.dumps(result["metrics"], indent=2))
    print(f"Summary: {args.output_dir / 'summary.json'}")
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
