# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import jsonschema
import litellm
from dataclasses_json import DataClassJsonMixin
from litellm import completion as completion_fn

litellm.api_version = "2024-12-01-preview"
litellm.set_verbose = False

NUM_RETRIES = 10
TIMEOUT = 1500
STRUCTURED_OUTPUT_RETRIES = 2


# Configure logging
logger = logging.getLogger("Backend")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@dataclass
class FunctionSpec(DataClassJsonMixin):
    name: str
    json_schema: Dict[str, Any]  # JSON schema
    description: str

    def __post_init__(self):
        # Validate the JSON schema
        jsonschema.Draft7Validator.check_schema(self.json_schema)

    @property
    def as_openai_tool_dict(self) -> Dict[str, Any]:
        """Convert to the modern OpenAI tools format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.json_schema,
            },
        }

    @property
    def openai_tool_choice_dict(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name},
        }

    @property
    def as_anthropic_tool_dict(self):
        """Convert to Anthropic's tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.json_schema,  # Anthropic uses input_schema instead of parameters
        }

    @property
    def anthropic_tool_choice_dict(self):
        """Convert to Anthropic's tool choice format."""
        return {
            "type": "tool",  # Anthropic uses "tool" instead of "function"
            "name": self.name,
        }


class LiteLLMClient:
    PromptType = Union[str, Dict[str, Any], List[Any]]
    FunctionCallType = Dict[str, Any]
    OutputType = Union[str, FunctionCallType]

    def __init__(self, client_cfg):
        """
        Initialize the OpenAI client with any desired default arguments or configuration.
        """
        self.model = client_cfg.model_id
        self.base_url = client_cfg.base_url
        api_key = os.getenv("PRIMARY_KEY_" + self.model.replace("-", "_").replace(".", "_").upper(), "")
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("PRIMARY_KEY", "")
        self.use_azure_client = client_cfg.use_azure_client
        self.provider = client_cfg.provider
        if self.use_azure_client:
            self.model_prefix = "azure/"
        else:
            self.model_prefix = "openai/"

        self.model = self.model_prefix + self.model

        logging.getLogger("httpx").setLevel(logging.WARNING)

    @property
    def client_content_key(self):
        return "content"

    def _calculate_cost(self, prompt_tokens, completion_tokens):
        """Calculate the API cost for a request based on token usage and provider-specific pricing."""
        cost = 0.0
        # Example cost calculation for different providers/models
        if self.provider.lower() == "openai":
            # Define cost per 1K tokens for some known OpenAI models (in USD)
            if "gpt-3.5" in self.model.lower():
                prompt_cost_per_1k = 0.0
                completion_cost_per_1k = 0.0
            elif "gpt-4" in self.model.lower():
                prompt_cost_per_1k = 0.0
                completion_cost_per_1k = 0.0
            else:
                # Default rates for other OpenAI models (if any)
                prompt_cost_per_1k = 0.0
                completion_cost_per_1k = 0.0
            # Calculate cost proportionally to the number of tokens (token counts are divided by 1000 for per-1K pricing)
            cost = (prompt_tokens / 1000.0) * prompt_cost_per_1k + (
                completion_tokens / 1000.0
            ) * completion_cost_per_1k
        elif self.provider.lower() == "anthropic":
            prompt_cost_per_1k = 0.0  # example cost per 1K tokens for prompts on Anthropic
            completion_cost_per_1k = 0.0  # example cost per 1K tokens for completions on Anthropic
            cost = (prompt_tokens / 1000.0) * prompt_cost_per_1k + (
                completion_tokens / 1000.0
            ) * completion_cost_per_1k
        else:
            # Other providers or default case
            # If costs are not known, leave as 0 or implement accordingly
            cost = 0.0
        return round(cost, 6)  # rounding to a reasonable number of decimal places for currency

    def count_tokens(self, text):
        """Utility method to count tokens in a given text string."""
        # In a real scenario, this should use the model's tokenizer for accuracy.
        # Here, we'll use a simple whitespace split as a placeholder.
        if text is None:
            return 0
        return len(text.split())

    @staticmethod
    def _messages_with_json_schema(
        messages: List[Dict[str, str]], func_spec: FunctionSpec
    ) -> List[Dict[str, str]]:
        """Return a copy of messages that explicitly requests schema-conformant JSON."""
        schema_instruction = (
            "\n\nReturn only a JSON object for the following operation: "
            f"{func_spec.description}\nThe JSON object must validate against this JSON Schema:\n"
            f"{json.dumps(func_spec.json_schema, ensure_ascii=False)}"
        )
        structured_messages = [message.copy() for message in messages]
        for message in structured_messages:
            if message.get("role") == "system" and isinstance(message.get("content"), str):
                message["content"] += schema_instruction
                break
        else:
            structured_messages.insert(0, {"role": "system", "content": schema_instruction.strip()})
        return structured_messages

    @staticmethod
    def _json_mode_is_unsupported(error: Exception) -> bool:
        message = str(error).lower()
        mentions_json_mode = any(
            marker in message for marker in ("response_format", "json mode", "json_object")
        )
        mentions_unsupported = any(
            marker in message for marker in ("not support", "unsupported", "unknown", "invalid")
        )
        return mentions_json_mode and mentions_unsupported

    @staticmethod
    def _message_tool_call(message: Any) -> Any:
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            return tool_calls[0].function
        if isinstance(message, dict):
            tool_calls = message.get("tool_calls")
            if tool_calls:
                return tool_calls[0]["function"]
        return None

    @staticmethod
    def _field(value: Any, name: str) -> Any:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    def _parse_structured_output(
        self, completion: Any, func_spec: FunctionSpec, transport: str
    ) -> FunctionCallType:
        message = completion.choices[0].message
        if transport == "json":
            raw_output = self._field(message, "content")
            if not raw_output:
                raise ValueError("JSON mode returned empty message content")
        else:
            function_call = self._message_tool_call(message)
            if function_call is None:
                raise ValueError("Tools mode returned no tool call")
            function_name = self._field(function_call, "name")
            if str(function_name).strip() != func_spec.name.strip():
                raise ValueError(
                    f"Function name mismatch: expected {func_spec.name}, got {function_name}"
                )
            raw_output = self._field(function_call, "arguments")

        if isinstance(raw_output, dict):
            output = raw_output
        else:
            if not isinstance(raw_output, str):
                raise TypeError(
                    f"Structured output must be a JSON string or object, got {type(raw_output).__name__}"
                )
            output = json.loads(raw_output)
        if not isinstance(output, dict):
            raise TypeError(f"Structured output must be an object, got {type(output).__name__}")
        jsonschema.Draft7Validator(func_spec.json_schema).validate(output)
        return output

    def _query_client(
        self,
        messages: List[Dict[str, str]],
        model_kwargs: Optional[Dict[str, Any]] = None,
        json_schema: Optional[str] = None,
        function_name: Optional[str] = None,
        function_description: Optional[str] = None,
    ) -> Tuple[OutputType, Dict[str, Any]]:
        model_kwargs = dict(model_kwargs or {})

        # Prepare function specifications if provided
        func_spec = None
        if json_schema and function_name and function_description:
            func_spec = FunctionSpec(function_name, json.loads(json_schema), function_description)

        structured_output_mode = model_kwargs.pop("structured_output_mode", "json")
        structured_output_retries = model_kwargs.pop(
            "structured_output_retries", STRUCTURED_OUTPUT_RETRIES
        )
        if structured_output_mode not in {"json", "tools"}:
            raise ValueError("structured_output_mode must be either 'json' or 'tools'")
        if not isinstance(structured_output_retries, int) or structured_output_retries < 0:
            raise ValueError("structured_output_retries must be a non-negative integer")
        if func_spec is not None:
            for transport_argument in (
                "response_format",
                "tools",
                "tool_choice",
                "functions",
                "function_call",
            ):
                model_kwargs.pop(transport_argument, None)

        # Always include necessary model parameters
        model_kwargs["model"] = self.model
        model_kwargs["base_url"] = self.base_url
        model_kwargs["api_key"] = self.api_key
        filtered_kwargs = {k: v for k, v in model_kwargs.items() if v is not None}

        filtered_kwargs["max_retries"] = NUM_RETRIES
        filtered_kwargs["num_retries"] = NUM_RETRIES
        filtered_kwargs["request_timeout"] = httpx.Timeout(timeout=TIMEOUT)

        # Record start time for latency measurement
        start_time = time.monotonic()

        # Execute the LLM call. Structured requests default to JSON mode because
        # DeepSeek thinking models reject forced tool_choice. Services which reject
        # JSON mode fall back to the modern tools interface, never to plain text.
        completion = None
        completed_requests = []
        output = None
        request_messages = messages
        transport = structured_output_mode
        attempts = structured_output_retries + 1 if func_spec is not None else 1
        for attempt in range(attempts):
            request_kwargs = filtered_kwargs.copy()
            if func_spec is not None and transport == "json":
                request_messages = self._messages_with_json_schema(messages, func_spec)
                request_kwargs["response_format"] = {"type": "json_object"}
            elif func_spec is not None:
                request_messages = messages
                request_kwargs["tools"] = [func_spec.as_openai_tool_dict]
                request_kwargs["tool_choice"] = func_spec.openai_tool_choice_dict

            try:
                completion = completion_fn(messages=request_messages, **request_kwargs)
                completed_requests.append(completion)
            except litellm.BadRequestError as error:
                if func_spec is not None and transport == "json" and self._json_mode_is_unsupported(error):
                    logger.warning(
                        "JSON mode is unsupported by this endpoint; retrying with modern tools."
                    )
                    transport = "tools"
                    request_kwargs = filtered_kwargs.copy()
                    request_kwargs["tools"] = [func_spec.as_openai_tool_dict]
                    request_kwargs["tool_choice"] = func_spec.openai_tool_choice_dict
                    request_messages = messages
                    completion = completion_fn(messages=messages, **request_kwargs)
                    completed_requests.append(completion)
                else:
                    raise

            if func_spec is None:
                break
            try:
                output = self._parse_structured_output(completion, func_spec, transport)
                break
            except (json.JSONDecodeError, jsonschema.ValidationError, TypeError, ValueError) as error:
                if attempt + 1 >= attempts:
                    raise ValueError(
                        f"Invalid structured output after {attempts} attempt(s): {error}"
                    ) from error
                logger.warning(
                    "Invalid structured output on attempt %s/%s (%s); retrying.",
                    attempt + 1,
                    attempts,
                    error,
                )

        # Calculate latency
        latency = time.monotonic() - start_time

        # Extract usage stats from the LLM response (if available)
        choice = completion.choices[0]
        request_usage = [item.to_dict().get("usage", {}) for item in completed_requests]
        usage_stats = dict(request_usage[-1])
        for token_key in ("prompt_tokens", "completion_tokens"):
            token_values = [usage.get(token_key) for usage in request_usage]
            if token_values and all(isinstance(value, int) for value in token_values):
                usage_stats[token_key] = sum(token_values)

        # Add latency and success status to the stats
        usage_stats["latency"] = latency
        usage_stats["success"] = True
        if func_spec is not None:
            usage_stats["structured_output_transport"] = transport
            usage_stats["structured_output_requests"] = len(completed_requests)

        # If token counts are not available from the response, estimate them.
        if "prompt_tokens" not in usage_stats:
            prompt_text = " ".join([m.get("content", "") for m in request_messages])
            usage_stats["prompt_tokens"] = self.count_tokens(prompt_text)
        if "completion_tokens" not in usage_stats:
            usage_stats["completion_tokens"] = self.count_tokens(choice.message.content)
        usage_stats["total_tokens"] = usage_stats["prompt_tokens"] + usage_stats["completion_tokens"]

        # Calculate cost using a helper (this method can adjust for different backends)
        usage_stats["cost"] = self._calculate_cost(usage_stats["prompt_tokens"], usage_stats["completion_tokens"])

        if func_spec is None:
            output = choice.message.content

        return output, usage_stats

    def query(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[str] = None,
        function_name: Optional[str] = None,
        function_description: Optional[str] = None,
        **model_kwargs,
    ) -> OutputType:
        """
        General LLM query for various backends with a single system and user message.
        Supports function calling for some backends.

        Args:
            system_message (PromptType | None): Uncompiled system message.
            user_message (PromptType | None): Uncompiled user message.
            model (str): Identifier for the model to use (e.g., "gpt-4-turbo").
            temperature (float | None, optional): Sampling temperature.
            max_tokens (int | None, optional): Maximum number of tokens to generate.
            func_spec (FunctionSpec | None, optional): Optional FunctionSpec for function calling.
            **model_kwargs: Additional keyword arguments for the model.

        Returns:
            OutputType: A string completion or a dict with function call details.
        """

        if self.model == "azure/o1-preview" or self.model == "azure/o3-mini":
            messages = [{"role": "user", self.client_content_key: m[self.client_content_key]} for m in messages]
            if "temperature" in model_kwargs:
                model_kwargs.pop("temperature")

        output, usage_stats = self._query_client(
            messages=messages,
            model_kwargs=model_kwargs,
            json_schema=json_schema,
            function_name=function_name,
            function_description=function_description,
        )

        return output, usage_stats
