"""Hindsight requests through dojo's LiteLLM backend with shared concurrency.

Input: source operator client config, shared semaphore, messages and generation settings.
Credentials: existing PRIMARY_KEY_<MODEL> or PRIMARY_KEY loaded from .env by dojo.
Output: parsed hint or complete response dictionaries. No filesystem input/output.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from dotenv import load_dotenv

from dojo.core.solvers.llm_helpers.backends.lite_llm import LiteLLMClient

from .helper import parts


def validate_hint(result: dict) -> None:
    """Require a nonempty hint string in the parsed result."""
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    hint = result.get("hint")
    if not isinstance(hint, str) or not hint.strip():
        raise ValueError("Hint extraction requires nonempty hint")


class ModelClient:
    def __init__(self, client_config: dict, semaphore: asyncio.Semaphore):
        """Use the source model/endpoint and dojo's credentials and request handling."""
        load_dotenv()
        self.model = client_config["model_id"]
        self.semaphore = semaphore
        self.backend = LiteLLMClient(
            SimpleNamespace(**{**client_config, "use_azure_client": client_config.get("use_azure_client", False)})
        )

    async def debug_hint(self, messages: list[dict], *, part: bool = False) -> dict:
        """Extract guidance from a debugging trajectory or one trajectory part."""
        return await self._hint("debug_hint_part" if part else "debug_hint", messages)

    async def improve_hint(self, messages: list[dict], *, part: bool = False) -> dict:
        """Extract guidance from an improvement trajectory or one trajectory part."""
        return await self._hint("improve_hint_part" if part else "improve_hint", messages)

    async def _hint(self, stage: str, messages: list[dict]) -> dict:
        """Let dojo parse and validate the JSON hint, leaving thinking to the model service."""
        schema = {
            "type": "object",
            "properties": {"hint": {"type": "string", "minLength": 1}},
            "required": ["hint"],
            "additionalProperties": False,
        }
        async with self.semaphore:
            result, _ = await self.backend.query(
                messages,
                json_schema=json.dumps(schema),
                function_name=stage,
                function_description="Extract engineering guidance from the supplied trajectory.",
                temperature=0.2,
                max_tokens=8192,
            )
        validate_hint(result)
        return result

    async def generate(self, messages: list[dict], generation: dict) -> dict:
        """Generate a full policy response while preserving native thinking for training."""
        async with self.semaphore:
            content, usage = await self.backend.query(messages, include_reasoning=True, **generation)
        parts(content)
        return {"completion": content, "usage": usage, "model": self.model}
