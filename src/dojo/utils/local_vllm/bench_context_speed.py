"""Measure the usable context window and the inference speed of the local vLLM server.

All requests are sent one at a time (concurrency 1), which is the setting we care
about: it is the case in which one request may occupy the whole KV cache.

Two measurements:

1. longest prompt the server accepts. The prompt size is found by doubling and
   then bisecting the number of filler characters; the reported number is the
   ``usage.prompt_tokens`` of the largest request that succeeded.
2. inference speed: time to first token (prefill) and decode tokens/s, measured
   with streaming for a few prompt sizes.

Run it on the node that hosts the server, e.g.

    srun -J vllmbench --ntasks 1 --cpus-per-task=2 \
        python -m dojo.utils.local_vllm.bench_context_speed
"""

import argparse
import os
import sys
import time

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "qwen3.8-27b"
DEFAULT_BASE_URL = os.getenv("HOST_QWEN3_8_27B", "http://127.0.0.1:8000/v1")
DEFAULT_API_KEY = os.getenv("PRIMARY_KEY_QWEN3_8_27B", "")

# One sentence of filler; repeated to build long prompts.
FILLER_SENTENCE = (
    "The quick brown fox jumps over the lazy dog while the engineer waits for the "
    "cluster scheduler to hand out a GPU. "
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument(
        "--probe-max-tokens",
        type=int,
        default=16,
        help="how many tokens the model may generate while probing the context limit",
    )
    parser.add_argument(
        "--probe-max-chars",
        type=int,
        default=4_000_000,
        help="upper bound for the filler prompt size in characters",
    )
    parser.add_argument(
        "--probe-chars",
        default="",
        help=(
            "comma separated filler sizes (characters) to probe once each, instead of "
            "the doubling/bisect search. Useful when the context is huge and each probe "
            "costs minutes of prefill"
        ),
    )
    parser.add_argument(
        "--decode-tokens",
        type=int,
        default=128,
        help="generated tokens per speed measurement",
    )
    parser.add_argument(
        "--speed-prompt-chars",
        default="4096,32768",
        help="comma separated filler sizes (characters) for the speed measurements",
    )
    parser.add_argument("--runs", type=int, default=2, help="repeats per speed measurement")
    return parser.parse_args()


def make_prompt(n_chars: int) -> str:
    repeats = max(1, n_chars // len(FILLER_SENTENCE))
    return FILLER_SENTENCE * repeats


def build_client(args):
    from openai import OpenAI

    return OpenAI(
        base_url=args.base_url,
        api_key=args.api_key or "unused",
        max_retries=0,
        timeout=1800,
    )


def probe(client, args, n_chars: int):
    """Send one request. Returns (prompt_tokens, error_message_or_None)."""
    try:
        response = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "user", "content": make_prompt(n_chars) + "\nReply with the word ok."}],
            max_tokens=args.probe_max_tokens,
            temperature=0.0,
        )
        return response.usage.prompt_tokens, None
    except Exception as error:  # noqa: BLE001 - any failure means "too long for this server"
        message = str(error)
        return None, message


def find_max_context(client, args) -> None:
    print("=" * 78)
    print(f"[1/2] longest prompt accepted (one request at a time, max_tokens={args.probe_max_tokens})")
    print("  doubling to find a failing size ...")

    n_chars = 4096
    last_ok = None
    last_error = None
    while n_chars <= args.probe_max_chars:
        prompt_tokens, error = probe(client, args, n_chars)
        if error is not None:
            last_error = error
            print(f"  {n_chars:>9} chars -> FAILED")
            break
        last_ok = (n_chars, prompt_tokens)
        print(f"  {n_chars:>9} chars -> ok ({prompt_tokens} prompt tokens)")
        n_chars *= 2

    if last_ok is None:
        print(f"\n  the very first request failed: {last_error}")
        return
    if n_chars > args.probe_max_chars:
        print(f"\n  no failure up to {args.probe_max_chars} chars; raise --probe-max-chars to find the limit")
        return

    low_chars, low_tokens = last_ok
    high_chars = n_chars
    print(f"  bisecting between {low_chars} and {high_chars} chars ...")
    while high_chars - low_chars > 2048:
        mid = (low_chars + high_chars) // 2
        prompt_tokens, error = probe(client, args, mid)
        if error is None:
            low_chars, low_tokens = mid, prompt_tokens
        else:
            high_chars = mid
            last_error = error
    print(f"\n  RESULT: largest accepted prompt = {low_tokens} tokens")
    print(f"  RESULT: first failing prompt     > {high_chars} filler characters")
    print(f"  server error at the failing size: {last_error}")


def probe_sizes(client, args) -> None:
    print("=" * 78)
    print(f"[1/2] single probes (one request at a time, max_tokens={args.probe_max_tokens})")
    for n_chars in [int(x) for x in args.probe_chars.split(",") if x.strip()]:
        start = time.monotonic()
        prompt_tokens, error = probe(client, args, n_chars)
        elapsed = time.monotonic() - start
        if error is None:
            print(f"  {n_chars:>9} chars -> ok: {prompt_tokens} prompt tokens, prefill {elapsed:.1f}s")
        else:
            print(f"  {n_chars:>9} chars -> FAILED after {elapsed:.1f}s: {error[:160]}")


def measure_speed(client, args, n_chars: int) -> dict:
    from openai import OpenAI  # noqa: F401 - import kept local for clarity

    prompt = make_prompt(n_chars) + "\nReply with the word ok."
    start = time.monotonic()
    stream = client.chat.completions.create(
        model=args.model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=args.decode_tokens,
        temperature=0.0,
        stream=True,
        stream_options={"include_usage": True},
    )
    ttft = None
    usage = None
    for chunk in stream:
        if ttft is None:
            ttft = time.monotonic() - start
        if chunk.usage is not None:
            usage = chunk.usage
    total = time.monotonic() - start
    decode_tokens = usage.completion_tokens if usage else args.decode_tokens
    decode_seconds = total - ttft
    return {
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "completion_tokens": decode_tokens,
        "ttft_s": ttft,
        "total_s": total,
        "prefill_tok_s": (usage.prompt_tokens / ttft) if usage and ttft else float("nan"),
        "decode_tok_s": decode_tokens / decode_seconds if decode_seconds > 0 else float("nan"),
    }


def report_speed(client, args) -> None:
    print("=" * 78)
    print(f"[2/2] speed at concurrency 1 ({args.decode_tokens} generated tokens, {args.runs} runs each)")
    sizes = [int(x) for x in args.speed_prompt_chars.split(",") if x.strip()]
    print(f"{'prompt_tokens':>14} {'TTFT (s)':>10} {'total (s)':>10} {'prefill tok/s':>14} {'decode tok/s':>13}")
    for n_chars in sizes:
        for run in range(args.runs):
            stats = measure_speed(client, args, n_chars)
            print(
                f"{str(stats['prompt_tokens']):>14} {stats['ttft_s']:>10.2f} {stats['total_s']:>10.2f}"
                f" {stats['prefill_tok_s']:>14.1f} {stats['decode_tok_s']:>13.1f}"
                + ("   (first run, may include compile/compile-graph warmup)" if run == 0 else "")
            )


def main() -> int:
    args = parse_args()
    print(f"base_url = {args.base_url}")
    print(f"model    = {args.model}")
    client = build_client(args)
    if args.probe_chars.strip():
        probe_sizes(client, args)
    elif args.probe_max_chars > 0:
        find_max_context(client, args)
    report_speed(client, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
