"""Pruning the vision-tower LoRA tensors out of a merged SFT adapter."""

import json

import pytest
import torch
from safetensors.torch import load_file, save_file

from src.mle_policy.src.export.lora_adapter import module_path, prune

RANK = 4
HIDDEN = 8
UP = 6
LANGUAGE_MODEL_MODULE = "model.language_model.layers.0.mlp.up_proj"
VISION_TOWER_MODULE = "model.visual.blocks.0.attn.qkv"


def lora_pair(module: str, out_features: int, *, zero_b: bool) -> dict[str, torch.Tensor]:
    """One adapter module in the layout ``verl.model_merger`` writes."""
    weights = torch.ones(out_features, RANK) if not zero_b else torch.zeros(out_features, RANK)
    return {
        f"base_model.model.{module}.lora_A.weight": torch.ones(RANK, HIDDEN),
        f"base_model.model.{module}.lora_B.weight": weights,
    }


def write_adapter(adapter_dir, *, tower_b_zero: bool = True, extra: dict | None = None):
    tensors = {
        **lora_pair(LANGUAGE_MODEL_MODULE, UP, zero_b=False),
        **lora_pair(VISION_TOWER_MODULE, 3 * UP, zero_b=tower_b_zero),
        **(extra or {}),
    }
    save_file(tensors, adapter_dir / "adapter_model.safetensors")
    (adapter_dir / "adapter_config.json").write_text(
        json.dumps(
            {
                "peft_type": "LORA",
                "task_type": "CAUSAL_LM",
                "r": RANK,
                "lora_alpha": 2 * RANK,
                "target_modules": ["up_proj", "qkv"],
            }
        ),
        encoding="utf-8",
    )
    return tensors


def test_module_path_strips_peft_prefix_and_lora_suffix():
    assert module_path(f"base_model.model.{VISION_TOWER_MODULE}.lora_B.weight") == VISION_TOWER_MODULE


def test_prune_keeps_language_model_and_drops_untrained_vision_tower(tmp_path):
    adapter_dir = tmp_path / "lora_adapter"
    adapter_dir.mkdir()
    tensors = write_adapter(adapter_dir)

    summary = prune(adapter_dir, tmp_path / "lora_adapter_vllm")

    output = load_file(tmp_path / "lora_adapter_vllm" / "adapter_model.safetensors")
    assert set(output) == {key for key in tensors if "visual" not in key}
    assert torch.equal(
        output[f"base_model.model.{LANGUAGE_MODEL_MODULE}.lora_B.weight"],
        tensors[f"base_model.model.{LANGUAGE_MODEL_MODULE}.lora_B.weight"],
    )
    assert summary["dropped_vision_tower_tensors"] == 2

    config = json.loads((tmp_path / "lora_adapter_vllm" / "adapter_config.json").read_text())
    assert config["target_modules"] == ["up_proj"]
    assert (config["r"], config["lora_alpha"]) == (RANK, 2 * RANK)


def test_prune_refuses_to_drop_trained_vision_tower(tmp_path):
    adapter_dir = tmp_path / "lora_adapter"
    adapter_dir.mkdir()
    write_adapter(adapter_dir, tower_b_zero=False)

    with pytest.raises(ValueError, match="not zero"):
        prune(adapter_dir, tmp_path / "out")


def test_prune_rejects_unknown_modules(tmp_path):
    adapter_dir = tmp_path / "lora_adapter"
    adapter_dir.mkdir()
    write_adapter(adapter_dir, extra=lora_pair("model.sound_encoder.layers.0.proj", UP, zero_b=True))

    with pytest.raises(ValueError, match="neither a language-model nor a vision-tower module"):
        prune(adapter_dir, tmp_path / "out")


def test_prune_rejects_incomplete_lora_pairs(tmp_path):
    adapter_dir = tmp_path / "lora_adapter"
    adapter_dir.mkdir()
    write_adapter(adapter_dir)
    weights = load_file(adapter_dir / "adapter_model.safetensors")
    del weights[f"base_model.model.{LANGUAGE_MODEL_MODULE}.lora_B.weight"]
    save_file(weights, adapter_dir / "adapter_model.safetensors")

    with pytest.raises(ValueError, match="without a complete"):
        prune(adapter_dir, tmp_path / "out")
