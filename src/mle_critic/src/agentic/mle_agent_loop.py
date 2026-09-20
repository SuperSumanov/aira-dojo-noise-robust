"""Project-specific ToolAgentLoop; reward only sees the last assistant turn."""
import asyncio
import hashlib
import json
from pathlib import Path
import time

from verl.experimental.agent_loop.tool_agent_loop import ToolAgentLoop, AgentState
from verl.tools.schemas import ToolResponse

from .common import final_answer
from .sandbox import ChrootBashSandbox


class MLEAgentLoop(ToolAgentLoop):
    def __init__(self, *args, sandbox, trace_dir, **kwargs):
        super().__init__(*args, **kwargs)
        self.sandbox_config = dict(sandbox)
        self.trace_dir = Path(trace_dir)
        if self.max_parallel_calls != 1:
            raise ValueError("MLEAgentLoop requires max_parallel_calls=1")
        self.sandbox = None
        self.trace = None
        self.last_assistant = ""
        self.tool_count = 0
        self.tool_seconds = 0.0

    def record(self, event, **values):
        self.trace.write(json.dumps({"event": event, "time": time.time(), **values}, ensure_ascii=False) + "\n")
        self.trace.flush()

    async def run(self, sampling_params, **kwargs):
        self.sandbox = ChrootBashSandbox(self.sandbox_config, kwargs["sample_uuid"], kwargs["task"],
                                         kwargs["solution_A"], kwargs["solution_B"])
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = self.trace_dir / f"{kwargs['sample_uuid']}-{self.sandbox.trajectory_uuid}.jsonl"
        with trace_path.open("x", encoding="utf-8") as self.trace:
            self.record("start", sample_uuid=kwargs["sample_uuid"], trajectory_uuid=self.sandbox.trajectory_uuid,
                        task=kwargs["task"], prompt=list(kwargs["raw_prompt"]),
                        solution_sha256={name: hashlib.sha256(kwargs[f"solution_{name}"].encode()).hexdigest()
                                         for name in ("A", "B")})
            try:
                async with self.sandbox:
                    self.record("sandbox_ready", setup_s=self.sandbox.setup_s)
                    output = await asyncio.wait_for(super().run(sampling_params, **kwargs),
                                                    self.sandbox_config.get("trajectory_timeout_s", 600))
                    answer = final_answer(self.last_assistant)
                    label = kwargs["reward_model"]["ground_truth"]
                    output.reward_score = float(answer is not None and answer == label)
                    output.extra_fields.update({
                        "mle_trace_path": str(trace_path), "mle_tool_calls": self.tool_count,
                        "mle_tool_seconds": self.tool_seconds, "mle_sandbox_setup_s": self.sandbox.setup_s,
                        "mle_answer": answer or "invalid",
                    })
                    self.record("result", answer=answer, ground_truth=label, reward=output.reward_score,
                                num_turns=output.num_turns, model_tokens=sum(output.response_mask),
                                observation_tokens=len(output.response_mask) - sum(output.response_mask),
                                response_ids=output.response_ids, response_mask=output.response_mask,
                                final_assistant=self.last_assistant)
                    return output
            except BaseException as error:
                self.record("error", error=f"{type(error).__name__}: {error}")
                raise
            finally:
                self.record("closed", runtime_removed=not self.sandbox.path.exists())

    async def _handle_generating_state(self, agent_data, sampling_params, ignore_termination=False):
        remaining = self.response_length - len(agent_data.response_mask)
        if remaining <= 0:
            return AgentState.TERMINATED
        sampling_params = {**sampling_params, "max_tokens": remaining}
        state = await super()._handle_generating_state(agent_data, sampling_params, ignore_termination)
        self.last_assistant = self.tokenizer.decode(agent_data.response_ids, skip_special_tokens=False)
        self.record("assistant", text=self.last_assistant, tokens=len(agent_data.response_ids), state=state.value)
        return state

    async def _call_tool(self, tool_call, tools_kwargs, agent_data):
        self.tool_count += 1
        try:
            arguments = json.loads(tool_call.arguments)
            result = await self.sandbox.call(tool_call.name, arguments)
            self.tool_seconds += result.get("duration_s", 0)
        except (ValueError, TypeError, KeyError, TimeoutError, RuntimeError, BrokenPipeError) as error:
            result = {"error": f"{type(error).__name__}: {error}"}
        text = json.dumps(result, ensure_ascii=False)
        if len(text) > self.max_tool_response_length:
            text = text[:self.max_tool_response_length] + "\n[tool output truncated]"
        if len(agent_data.tool_calls) > 1:
            text += "\nOnly the first tool call was executed. Make one call per turn."
        # AgentLoopBase also caps each freshly templated tool message at
        # prompt_length. Bound the observation first so it cannot left-truncate
        # away the Qwen tool-response opening tokens.
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        if len(tokens) > self.prompt_length - 128:
            text = self.tokenizer.decode(tokens[:self.prompt_length - 128]) + "\n[tool token budget reached]"
        self.record("tool", name=tool_call.name, arguments=tool_call.arguments, result=result, observation=text)
        return ToolResponse(text=text), 0.0, {}
