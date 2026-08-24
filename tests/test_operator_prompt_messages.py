from pathlib import Path

from omegaconf import OmegaConf

from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM


class _Prompt:
    def __init__(self, text: str) -> None:
        self.text = text

    def format(self, **query_data) -> str:
        return self.text.format(**query_data)


class _Client:
    client_content_key = "content"

    def __init__(self) -> None:
        self.messages = None

    def query(self, messages, **kwargs):
        self.messages = messages
        return "response", {}


def test_generic_llm_sends_system_and_initial_user_messages():
    llm = GenericLLM.__new__(GenericLLM)
    llm.client = _Client()
    llm.generation_kwargs = {}
    llm.system_message_prompt_template = _Prompt("system policy")
    llm.init_user_message_prompt_template = _Prompt("task: {task}")
    llm.user_message_prompt_template = _Prompt("follow-up: {task}")
    llm.call_tracker = 0

    output, metadata = llm(query_data={"task": "train a model"})

    expected_messages = [
        {"role": "system", "content": "system policy"},
        {"role": "user", "content": "task: train a model"},
    ]
    assert output == "response"
    assert llm.client.messages == expected_messages
    assert metadata["prompt_messages"] == expected_messages


def test_operator_system_prompts_are_static_and_user_prompts_hold_context():
    config_root = (
        Path(__file__).parents[1]
        / "src"
        / "dojo"
        / "configs"
        / "solver"
        / "operators"
        / "mlebench"
    )
    config_paths = sorted(config_root.glob("*_operators/*.yaml"))

    assert config_paths
    for config_path in config_paths:
        config = OmegaConf.load(config_path)
        operator_name = next(key for key in config if key != "defaults")
        operator = config[operator_name]
        system_template = operator.system_message_prompt_template.template
        user_template = operator.init_user_message_prompt_template.template

        assert "{{" not in system_template, config_path
        assert "{%" not in system_template, config_path
        assert "{{" in user_template, config_path
