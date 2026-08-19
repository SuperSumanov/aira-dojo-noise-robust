from __future__ import annotations

from pathlib import Path

import yaml

from phase1 import probe_balanced_client_providers as probe


def test_provider_matrix_is_exact_and_has_unique_key_names() -> None:
    assert [row[0] for row in probe.PROVIDERS] == [
        "deepseek-v4-flash",
        "qwen3-coder-flash",
        "glm-5",
    ]
    assert len({row[1] for row in probe.PROVIDERS}) == 2
    assert len({row[2] for row in probe.PROVIDERS}) == 3
    assert all(row[1].startswith("https://") and row[1].endswith("/chat/completions") for row in probe.PROVIDERS)


def test_production_client_configs_match_probe_matrix() -> None:
    config_root = Path("src/dojo/configs/solver/client")
    expected = {
        "litellm_deepseek_flash.yaml": ("deepseek-v4-flash", "https://api.deepseek.com"),
        "litellm_gen2.yaml": ("qwen3-coder-flash", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "litellm_gen3.yaml": ("glm-5", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    }
    for filename, (model_id, base_url) in expected.items():
        config = yaml.safe_load((config_root / filename).read_text(encoding="utf-8"))
        assert config["model_id"] == model_id
        assert config["base_url"] == base_url


def test_launcher_uses_one_commit_for_control_and_production() -> None:
    launcher = Path("phase1/scripts/launch_balanced_client_smoke_20260819.sh").read_text(encoding="utf-8")
    assert 'SOURCE_COMMIT="$CONTROL_COMMIT"' in launcher
    assert 'RUN_ROOT="/research/d7/spc/yzyang4/balanced-client-smoke-${CONTROL_COMMIT:0:7}-a2"' in launcher
