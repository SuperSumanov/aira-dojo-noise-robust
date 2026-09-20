"""Actual Qwen tokenizer/parser + real sandbox, with deterministic server turns."""
import asyncio
import json

import pytest
from omegaconf import OmegaConf
from transformers import AutoTokenizer

from verl.experimental.agent_loop.agent_loop import DictConfigWrap, ToolListWrap
from verl.tools.tool_registry import initialize_tools_from_config
from verl.utils.dataset.rl_dataset import RLHFDataset
from verl.workers.rollout.replica import TokenOutput
from src.mle_critic.src.agentic.mle_agent_loop import MLEAgentLoop
from src.mle_critic.src.agentic.sandbox import PROJECT_ROOT


@pytest.fixture(scope="module")
def tokenizer():
    return AutoTokenizer.from_pretrained("Qwen/Qwen3.8-27B", local_files_only=True)


@pytest.mark.parametrize("final,score", [(r"The better solution is \boxed{A}.", 1.0), ("No answer.", 0.0)])
def test_roundtrip_mask_reward_cleanup(tmp_path, tokenizer, final, score):
    async def run():
        turns = [
            "<tool_call>\n<function=bash>\n<parameter=command>printf 'probe' > scratch/probe; cat candidate_A/solution.py; cat candidate_B/solution.py</parameter>\n</function>\n</tool_call><|im_end|>",
            "<tool_call>\n<function=bash>\n<parameter=command>cat scratch/probe; printf '\\\\boxed{A}'; python3 -c 'print(\"word \" * 12000)'</parameter>\n</function>\n</tool_call><|im_end|>",
            final + "<|im_end|>",
        ]
        prompts = []
        class Server:
            async def generate(self, **kwargs):
                prompts.append(kwargs["prompt_ids"].copy())
                return TokenOutput(token_ids=tokenizer.encode(turns[len(prompts)-1], add_special_tokens=False))
        cfg = OmegaConf.create({"actor_rollout_ref": {"rollout": {
            "prompt_length": 2048, "response_length": 8192, "multi_turn": {
                "max_user_turns": None, "max_assistant_turns": 6, "max_parallel_calls": 1,
                "max_tool_response_length": 12000, "tool_response_truncate_side": "right", "format": "qwen3_coder",
            }}}, "data": {}})
        tools = initialize_tools_from_config(PROJECT_ROOT / "src/mle_critic/recipes/agentic/tools.yaml")
        loop = MLEAgentLoop(
            trainer_config=DictConfigWrap(cfg), data_config=DictConfigWrap(cfg.data), server_manager=Server(),
            tokenizer=tokenizer, processor=None, dataset_cls=RLHFDataset, tools=ToolListWrap(tools),
            sandbox={"runtime_base": str(tmp_path / "runtime"), "mlebench_data_root": str(PROJECT_ROOT / "data/mlebench")},
            trace_dir=str(tmp_path / "traces"),
        )
        output = await loop.run({}, raw_prompt=[{"role": "user", "content": "Inspect both candidates."}],
                                sample_uuid="looptest", task="spooky-author-identification",
                                solution_A="print('A')\n", solution_B="print('B')\n",
                                reward_model={"ground_truth": "A"})
        assert output.reward_score == score
        assert len(prompts) == 3 and loop.tool_count == 2
        assert sum(output.response_mask) == sum(len(tokenizer.encode(t, add_special_tokens=False)) for t in turns)
        assert 0 in output.response_mask
        assert "probe" in tokenizer.decode(prompts[-1])
        assert not loop.sandbox.path.exists()
        records = [json.loads(line) for line in next((tmp_path / "traces").glob("*.jsonl")).read_text().splitlines()]
        assert records[-1] == {**records[-1], "event": "closed", "runtime_removed": True}
        assert all(e["result"]["exit_code"] == 0 for e in records if e["event"] == "tool")
        observations = [e["observation"] for e in records if e["event"] == "tool"]
        assert "tool token budget reached" in observations[-1]
        assert "probe" in observations[-1]
    asyncio.run(run())
