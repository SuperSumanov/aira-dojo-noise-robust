"""Bounded asynchronous model calls, with content-addressed resumable results."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai

from dojo.core.solvers.llm_helpers.backends.open_ai import OpenAIClient

from .helper import VERSION, atomic_json, parts

HINT_PROPERTIES = {"hint": {"type": "string", "minLength": 1}}


def validate_hint(result: dict) -> None:
    """Require a nonempty hint string in the parsed result."""
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    hint = result.get("hint")
    if not isinstance(hint, str) or not hint.strip():
        raise ValueError("Hint extraction requires nonempty hint")


class ModelClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        cache: Path,
        concurrency: int = 24,
    ):
        """Configure the dojo client, request concurrency, and a shared result cache."""
        self.model = model
        self.cache = cache
        self.semaphore = asyncio.Semaphore(concurrency)
        self.backend = OpenAIClient(
            SimpleNamespace(model_id=model, base_url=base_url, use_azure_client=False),
            api_key=api_key or "unused",
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
        """Extract debugging guidance, with a separate cache stage for trajectory parts."""
        return await self._hint("debug_hint_part" if part else "debug_hint", messages)

    async def improve_hint(self, messages: list[dict], *, part: bool = False) -> dict:
        """Extract improvement guidance, with a separate cache stage for trajectory parts."""
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
        """Load a validated cached result or request JSON with up to three attempts and format repair as configured."""
        identity = {"version": VERSION, "stage": stage, "request": request}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.cache / stage / f"{digest}.json"
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))["result"]
            validate_hint(result)
            return result
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
                    atomic_json(
                        path,
                        {"identity": identity, "attempt_request": attempt_request, "result": result, "response": raw},
                    )
                    return result
                except (openai.APIError, ValueError, KeyError, TypeError) as error:
                    if isinstance(error, openai.APIStatusError) and error.status_code in (400, 401, 403, 404):
                        raise RuntimeError(f"Model request rejected: {error.response.text}") from error
                    if raw is not None:
                        atomic_json(
                            self.cache / "errors" / f"{digest}-{attempt}.json",
                            {
                                "identity": identity,
                                "attempt_request": attempt_request,
                                "error": str(error),
                                "response": raw,
                            },
                        )
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
        """Generate and validate full thinking, plan, and code, merge separate reasoning, and cache the response."""
        request = {"model": self.model, "messages": messages, **generation}
        identity = {"version": VERSION, "stage": "regenerate", "request": request}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = self.cache / "regenerate" / f"{digest}.json"
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))["result"]
            parts(result["completion"])
            return result
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
                        "cache_key": digest,
                        "model": self.model,
                    }
                    atomic_json(path, {"identity": identity, "result": result, "response": raw})
                    return result
                except (openai.APIError, ValueError, KeyError, TypeError, SyntaxError) as error:
                    if isinstance(error, openai.APIStatusError) and error.status_code in (400, 401, 403, 404):
                        raise RuntimeError(f"Model request rejected: {error.response.text}") from error
                    atomic_json(
                        self.cache / "errors" / f"{digest}-{attempt}.json",
                        {"identity": identity, "error": str(error), "response": raw},
                    )
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable model request state")
