"""Replay one journal's step 1 with its recorded generation settings."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

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


USE_FAST = re.compile(r"\buse_fast\b")
FAST_TRUE = re.compile(r"\buse_fast\b[\x27\x22]?\s*(?:=|:)\s*True\b", re.IGNORECASE)
FAST_FALSE = re.compile(r"\buse_fast\b[\x27\x22]?\s*(?:=|:)\s*False\b", re.IGNORECASE)
FAST_CLASS = re.compile(r"\b\w*TokenizerFast\b")
CODE_BLOCK = re.compile(r"^```(?:python|py)?[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
ENGINEERING_NOTES = re.compile(r"\bengineering\s+notes\b", re.IGNORECASE)


def indicators(content: str, reasoning: str = "") -> dict[str, bool]:
    """Count lexical matches separately in reasoning, final answer and fenced code."""
    answer = content.rsplit("</think>", 1)[-1]
    if "<think>" in answer:
        answer = ""
    code = "\n".join(CODE_BLOCK.findall(answer))
    full_text = reasoning + "\n" + content
    return {
        "use_fast": bool(USE_FAST.search(full_text)),
        "answer_use_fast": bool(USE_FAST.search(answer)),
        "has_code": bool(code.strip()),
        "code_use_fast": bool(USE_FAST.search(code)),
        "code_use_fast_true": bool(FAST_TRUE.search(code)),
        "code_use_fast_false": bool(FAST_FALSE.search(code)),
        "code_fast_tokenizer_class": bool(FAST_CLASS.search(code)),
        "mentions_engineering_notes": bool(ENGINEERING_NOTES.search(full_text)),
    }


def proportion(hits: int, total: int) -> dict:
    """Report the empirical rate and its 95% Wilson binomial interval."""
    if total == 0:
        return {"hits": hits, "total": total, "rate": None, "wilson_95": None}
    rate = hits / total
    z_score = 1.959963984540054
    denominator = 1 + z_score**2 / total
    center = (rate + z_score**2 / (2 * total)) / denominator
    radius = z_score * math.sqrt(rate * (1 - rate) / total + z_score**2 / (4 * total**2)) / denominator
    return {
        "hits": hits, "total": total, "rate": rate,
        "wilson_95": [max(0, center - radius), min(1, center + radius)],
    }


def summarize(records: list[dict]) -> dict:
    """Failures are counted explicitly; length-truncated responses stay visible."""
    successful = [record for record in records if "error" not in record]
    stopped = [record for record in successful if record["finish_reason"] == "stop"]

    def rates(rows: list[dict]) -> dict:
        return {
            name: proportion(sum(record["indicators"][name] for record in rows), len(rows))
            for name in indicators("")
        }

    return {
        "requested": len(records),
        "succeeded": len(successful),
        "failed": len(records) - len(successful),
        "truncated": sum(record["finish_reason"] == "length" for record in successful),
        "metrics": rates(successful),
        "stop_only_metrics": rates(stopped),
    }


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
    metadata = {
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
                record["indicators"] = indicators(
                    message.get("content") or "", message.get("reasoning_content") or ""
                )
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
                    **metadata, **summarize(records), "requested": args.n,
                    "completed": len(records), "unfinished": args.n - len(records),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                temporary = args.output_dir / "summary.json.tmp"
                temporary.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
                temporary.replace(args.output_dir / "summary.json")
                print(
                    f"{len(records)}/{args.n}: sample={record['sample_index']} "
                    f"{record.get('error', record.get('indicators'))}", flush=True,
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
    parser.add_argument("--model-id", required=True,
                        choices=["qwen3.8-27b", "qwen3.8-27b-mle-lora"])
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory")
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
