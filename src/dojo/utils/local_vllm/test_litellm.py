"""Smoke test for the local vLLM server using litellm.

Run this on the node that hosts the server (the default base URL is
``http://127.0.0.1:8000/v1``). Run it through srun if you only have the
allocation, e.g.

    srun -J litellmtest --ntasks 1 --cpus-per-task=2 \
        python -m dojo.utils.local_vllm.test_litellm

Three checks, in increasing order of "how close this is to what the solver does":

1. ``litellm.acompletion`` with a plain text prompt.
2. ``litellm.acompletion`` with ``response_format={"type": "json_object"}``.
3. ``dojo.core.solvers.llm_helpers.backends.lite_llm.LiteLLMClient.query`` with a
   JSON schema, which is the code path the MCTS solvers use for structured calls.
"""

import argparse
import asyncio
import json
import os
import sys

# The cluster routes outbound traffic through a proxy. The vLLM server is on the
# local node, so it must bypass the proxy. This has to happen before litellm /
# httpx build their clients.
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

import litellm
from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "qwen3.8-27b"
DEFAULT_BASE_URL = os.getenv("HOST_QWEN3_8_27B", "http://127.0.0.1:8000/v1")
DEFAULT_API_KEY = os.getenv("PRIMARY_KEY_QWEN3_8_27B", "")

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "animal": {"type": "string"},
        "count": {"type": "integer"},
        "colors": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["animal", "count", "colors"],
    "additionalProperties": False,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser.parse_args()


async def check_plain_text(args, litellm_model: str) -> None:
    print("=" * 70)
    print("[1/3] plain text completion")
    response = await litellm.acompletion(
        model=litellm_model,
        api_key=args.api_key,
        base_url=args.base_url,
        messages=[{"role": "user", "content": "Reply with exactly: hello from vllm"}],
        temperature=0.0,
        max_tokens=args.max_tokens,
        max_retries=0,
        timeout=600,
    )
    content = response.choices[0].message.content
    print(f"  content: {content!r}")
    print(f"  usage: {response.usage}")
    assert content and "hello" in content.lower(), f"unexpected content: {content!r}"


async def check_json_mode(args, litellm_model: str) -> None:
    print("=" * 70)
    print("[2/3] json_object response format")
    response = await litellm.acompletion(
        model=litellm_model,
        api_key=args.api_key,
        base_url=args.base_url,
        messages=[
            {
                "role": "user",
                "content": (
                    "Return a JSON object with the keys animal (string), count (integer) "
                    "and colors (array of strings). Use the animal 'cat' and the count 3."
                ),
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=args.max_tokens,
        max_retries=0,
        timeout=600,
    )
    content = response.choices[0].message.content
    print(f"  raw content: {content!r}")
    parsed = json.loads(content)
    print(f"  parsed: {parsed}")
    assert isinstance(parsed, dict), "json mode did not return a JSON object"


async def check_solver_client(args) -> None:
    print("=" * 70)
    print("[3/3] dojo LiteLLMClient.query with a JSON schema")
    from dojo.config_dataclasses.client.base import ClientConfig
    from dojo.core.solvers.llm_helpers.backends.lite_llm import LiteLLMClient

    client_cfg = ClientConfig(
        api="litellm",
        model_id=args.model,
        base_url=args.base_url,
        use_azure_client=False,
        provider="selfhosted",
    )
    client = LiteLLMClient(client_cfg)
    output, usage = await client.query(
        messages=[
            # Keep this in the style of the real operators' system messages. Do not
            # write something like "answer with JSON only": with the JSON schema
            # appended by the client, Qwen3.8-27B then tends to echo the schema
            # itself instead of an instance of it.
            {"role": "system", "content": "You are a careful assistant. Follow the requested response format."},
            {
                "role": "user",
                "content": "There are 3 cats, and their colors are black and white.",
            },
        ],
        json_schema=json.dumps(ANSWER_SCHEMA),
        function_name="describe_animals",
        function_description="Report the animal, how many there are, and their colors.",
        temperature=0.0,
        max_tokens=args.max_tokens,
    )
    print(f"  parsed output: {output}")
    print(f"  usage: {usage}")
    assert isinstance(output, dict), f"structured output is not a dict: {output!r}"


async def main() -> int:
    args = parse_args()
    print(f"base_url = {args.base_url}")
    print(f"model    = {args.model}")
    if not args.api_key:
        print("no API key configured; sending requests without an Authorization header")
    litellm_model = f"openai/{args.model}"
    try:
        await check_plain_text(args, litellm_model)
        await check_json_mode(args, litellm_model)
        await check_solver_client(args)
    except Exception as error:  # noqa: BLE001 - this is a smoke test, report everything
        print(f"\nFAILED: {type(error).__name__}: {error}")
        return 1
    print("=" * 70)
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
