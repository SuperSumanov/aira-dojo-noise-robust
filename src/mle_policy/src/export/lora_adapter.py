"""Prune a merged Qwen3.5 SFT adapter so vLLM accepts it.

``verl.model_merger merge`` copies every ``lora_`` tensor of the FSDP state dict
into ``<target_dir>/lora_adapter``.  The SFT run trains with
``model.target_modules=all-linear``, which also matches every linear layer of
the *vision tower* of Qwen3.5-9B / Qwen3.8-27B, so the adapter carries weights
for ``model.visual.*``.  vLLM only applies LoRA to the language model (tower
LoRA needs ``--enable-tower-connector-lora``) and rejects keys it does not know
about:

    ValueError: While loading .../lora_adapter, expected target modules in
    {... 'q_proj' ...} but received ['visual.blocks.0.attn.proj', ...]

The MLE policy data is text only, so the vision-tower adapters never receive a
gradient and their ``lora_B`` stays exactly zero: dropping them changes nothing
numerically.  This module writes a pruned copy of the adapter (by default
``<adapter_dir>_vllm``) without the ``visual.*`` tensors and with a matching
``adapter_config.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

import torch
from safetensors import safe_open
from safetensors.torch import save_file

# Key layout of a PEFT adapter exported from the FSDP checkpoint: every tensor
# is ``base_model.model.<hf module path>.lora_{A,B}.weight``.
PEFT_PREFIX = "base_model.model."
LANGUAGE_MODEL_PREFIX = "model.language_model."
VISION_TOWER_PREFIX = "model.visual."


def module_path(tensor_key: str) -> str:
    """``...model.visual.blocks.0.attn.qkv.lora_A.weight`` -> ``model.visual.blocks.0.attn.qkv``."""
    return tensor_key.removeprefix(PEFT_PREFIX).rsplit(".lora_", 1)[0]


def classify(module: str) -> Literal["language_model", "vision_tower"]:
    """Return the part of the model a LoRA module belongs to.

    Only the language model is served by vLLM, so anything else has to be
    accounted for explicitly instead of being dropped silently.
    """
    if module.startswith(LANGUAGE_MODEL_PREFIX):
        return "language_model"
    if module.startswith(VISION_TOWER_PREFIX):
        return "vision_tower"
    raise ValueError(
        f"{module!r} is neither a language-model nor a vision-tower module; check the merged adapter before pruning it"
    )


def prune(adapter_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Write ``adapter_dir`` minus its vision-tower tensors into ``output_dir``."""
    weights_path = adapter_dir / "adapter_model.safetensors"
    config_path = adapter_dir / "adapter_config.json"

    kept: dict[str, torch.Tensor] = {}
    dropped = 0
    trained_tower: list[str] = []
    with safe_open(weights_path, framework="pt") as handle:
        for key in handle.keys():
            if classify(module_path(key)) == "vision_tower":
                dropped += 1
                if key.endswith(".lora_B.weight") and bool(handle.get_tensor(key).any()):
                    trained_tower.append(key)
                continue
            kept[key] = handle.get_tensor(key)

    if trained_tower:
        raise ValueError("refusing to drop vision-tower LoRA weights that are not zero: " + ", ".join(trained_tower))

    modules = {module_path(key) for key in kept}
    incomplete = [
        module
        for module in sorted(modules)
        if any(f"{PEFT_PREFIX}{module}.lora_{kind}.weight" not in kept for kind in ("A", "B"))
    ]
    if incomplete:
        raise ValueError(f"kept LoRA modules without a complete lora_A/lora_B pair: {incomplete}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["target_modules"] = sorted({module.rsplit(".", 1)[-1] for module in modules})

    output_dir.mkdir(parents=True, exist_ok=True)
    save_file(kept, output_dir / "adapter_model.safetensors")
    (output_dir / "adapter_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "kept_tensors": len(kept),
        "kept_modules": len(modules),
        "dropped_vision_tower_tensors": dropped,
        "target_modules": config["target_modules"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--adapter-dir",
        required=True,
        type=Path,
        help="lora_adapter directory written by verl.model_merger",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="where to write the pruned adapter; defaults to <adapter_dir>_vllm",
    )
    args = parser.parse_args()
    output_dir = args.output_dir or args.adapter_dir.with_name(f"{args.adapter_dir.name}_vllm")
    summary = prune(args.adapter_dir, output_dir)
    print(json.dumps(summary, indent=2))
    print(f"\n--lora-modules <model-name>={output_dir}")


if __name__ == "__main__":
    main()
