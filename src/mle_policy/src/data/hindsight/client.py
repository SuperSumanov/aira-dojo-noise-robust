"""Model requests with bounded concurrency and three attempts per call.

Input: source operator client config, shared semaphore, messages and generation settings.
Credentials: existing PRIMARY_KEY_<MODEL> or PRIMARY_KEY loaded from .env.
Output: parsed hint or complete response dictionaries. No filesystem input/output.
"""

from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace

from dotenv import load_dotenv
import httpx
import openai

from dojo.core.solvers.llm_helpers.backends.open_ai import OpenAIClient

from .helper import parts

HINT_PROPERTIES = {"hint": {"type": "string", "minLength": 1}}


def validate_hint(result: dict) -> None:
    """Require a nonempty hint string in the parsed result."""
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    hint = result.get("hint")
    if not isinstance(hint, str) or not hint.strip():
        raise ValueError("Hint extraction requires nonempty hint")


class ModelClient:
    def __init__(self, client_config: dict, semaphore: asyncio.Semaphore):
        """Use the source operator's model/endpoint and existing PRIMARY_KEY settings from .env."""
        load_dotenv()
        self.model = client_config["model_id"]
        self.semaphore = semaphore
        key_name = "PRIMARY_KEY_" + self.model.replace("-", "_").replace(".", "_").upper()
        self.backend = OpenAIClient(
            SimpleNamespace(**{**client_config, "use_azure_client": client_config.get("use_azure_client", False)}),
            api_key=os.environ.get(key_name) or os.environ["PRIMARY_KEY"],
            max_retries=0,
            http_client=httpx.Client(trust_env=False, timeout=1800),
        )

    async def close(self) -> None:
        """Close the synchronous backend in a worker thread and release HTTP connections."""
        await asyncio.to_thread(self.backend.close)

    async def request(self, request: dict) -> dict:
        """Forward one request through dojo, placing provider-specific options in extra_body."""
        parameters = dict(request)
        extra = {}
        for key in ("chat_template_kwargs", "top_k", "min_p", "repetition_penalty"):
            if key in parameters:
                extra[key] = parameters.pop(key)
        if extra:
            parameters["extra_body"] = extra
        response = await asyncio.to_thread(self.backend.query_raw, **parameters)
        return response.model_dump()

    async def debug_hint(self, messages: list[dict], *, part: bool = False) -> dict:
        """Extract guidance from a debugging trajectory or one trajectory part."""
        return await self._hint("debug_hint_part" if part else "debug_hint", messages)

    async def improve_hint(self, messages: list[dict], *, part: bool = False) -> dict:
        """Extract guidance from an improvement trajectory or one trajectory part."""
        return await self._hint("improve_hint_part" if part else "improve_hint", messages)

    async def _hint(self, stage: str, messages: list[dict]) -> dict:
        """Build the shared non-thinking JSON request used by both hint-extraction endpoints."""
        request = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 8192,
            "response_format": {"type": "json_object"},
            "chat_template_kwargs": {"enable_thinking": False},
        }
        return await self._json_result(stage, request)

    async def _json_result(self, stage: str, request: dict) -> dict:
        """Request and validate a JSON hint, retrying at most three times."""
        async with self.semaphore:
            attempt_request = dict(request)
            for attempt in range(3):
                raw = None
                try:
                    raw = await self.request(attempt_request)
                    choice = raw["choices"][0]
                    if choice.get("finish_reason") != "stop":
                        raise ValueError(f"Incomplete generation: {choice.get('finish_reason')}")
                    content = choice["message"]["content"]
                    result = json.loads(content)
                    validate_hint(result)
                    return result
                except (openai.APIError, ValueError, KeyError, TypeError) as error:
                    if isinstance(error, openai.APIStatusError) and error.status_code in (400, 401, 403, 404):
                        raise RuntimeError(f"Model request rejected: {error.response.text}") from error
                    if raw is not None:
                        attempt_request = {
                            **request,
                            "messages": request["messages"]
                            + [
                                {
                                    "role": "user",
                                    "content": f"Your previous generation failed validation: {error}. "
                                    "Regenerate a complete JSON object with exactly the requested fields and types. ",
                                }
                            ],
                        }
                        attempt_request["response_format"] = {
                            "type": "json_schema",
                            "json_schema": {
                                "name": stage,
                                "strict": True,
                                "schema": {
                                    "type": "object",
                                    "properties": HINT_PROPERTIES,
                                    "required": list(HINT_PROPERTIES),
                                    "additionalProperties": False,
                                },
                            },
                        }
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable model request state")

    async def generate(self, messages: list[dict], generation: dict) -> dict:
        """Generate native thinking, plan, and code, retrying at most three times."""
        request = {"model": self.model, "messages": messages, **generation}
        async with self.semaphore:
            for attempt in range(3):
                raw = None
                try:
                    raw = await self.request(request)
                    choice = raw["choices"][0]
                    if choice.get("finish_reason") != "stop":
                        raise ValueError(f"Incomplete generation: {choice.get('finish_reason')}")
                    message = choice["message"]
                    content = message.get("content") or ""
                    reasoning = message.get("reasoning_content")
                    if reasoning and "</think>" not in content:
                        content = reasoning + "\n</think>\n\n" + content
                    parts(content)
                    result = {
                        "completion": content,
                        "usage": raw.get("usage", {}),
                        "model": self.model,
                    }
                    return result
                except (openai.APIError, ValueError, KeyError, TypeError, SyntaxError) as error:
                    if isinstance(error, openai.APIStatusError) and error.status_code in (400, 401, 403, 404):
                        raise RuntimeError(f"Model request rejected: {error.response.text}") from error
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable model request state")
