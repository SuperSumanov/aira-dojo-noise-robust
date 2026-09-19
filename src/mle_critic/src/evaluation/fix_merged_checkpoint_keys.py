"""Rewrite a merged judger checkpoint whose parameter names carry extra ``language_model.`` levels.

The FSDP merge of the Qwen3.8-27B judger wrote names like
``model.language_model.language_model.language_model.layers.0.linear_attn.norm.weight``
and ``model.language_model.visual.blocks.18.attn.qkv.weight``.  The official
Qwen3.8-27B checkpoint uses ``model.language_model.layers.*`` and
``model.visual.*``, so vLLM's name mapper matches nothing and the weights never
load.  Only the names are wrong: the values, shapes and dtypes are fine.

Because the duplicated level is a pure prefix, this script rewrites the
safetensors headers with the corrected names and copies the data section byte
for byte, so it never has to hold a 50 GB shard in memory.  It refuses to write
anything unless the renamed keys match the Hugging Face model described by the
checkpoint's own ``config.json`` exactly.

Needs transformers >= 5.5, i.e. run it inside the vLLM image:

    python3 src/mle_critic/src/evaluation/fix_merged_checkpoint_keys.py \
        --checkpoint <broken_dir> --output <fixed_dir>
"""

from __future__ import annotations

import argparse
import json
import shutil
import struct
from pathlib import Path
from typing import Any

import torch
from safetensors import safe_open
from transformers import AutoConfig, AutoModelForImageTextToText

# The merge nested the whole vision-language model one level too deep: every
# key got an extra ``language_model.`` after ``model.``, and the text tower kept
# the one it already had.
PREFIX_FIXES: tuple[tuple[str, str], ...] = (
    ("model.language_model.language_model.language_model.", "model.language_model."),
    ("model.language_model.visual.", "model.visual."),
)


def fix_key(name: str) -> str:
    for broken, fixed in PREFIX_FIXES:
        if name.startswith(broken):
            return fixed + name[len(broken) :]
    return name


def read_header(path: Path) -> tuple[int, dict[str, Any]]:
    """Return ``(header_length, header)`` of a safetensors file."""
    with open(path, "rb") as handle:
        (header_length,) = struct.unpack("<Q", handle.read(8))
        return header_length, json.loads(handle.read(header_length))


def write_shard(source: Path, target: Path, header_length: int, header: dict[str, Any]) -> None:
    """Write a renamed copy of ``source``, reusing the original data offsets.

    Data offsets in a safetensors header are relative to the end of the header,
    so keeping the header byte length identical keeps every offset valid and
    lets us stream the payload unchanged.
    """
    renamed = {fix_key(name): meta for name, meta in header.items()}
    payload = json.dumps(renamed, separators=(",", ":"), ensure_ascii=True).encode()
    if len(payload) > header_length:
        raise SystemExit(f"{source.name}: renamed header does not fit in the original {header_length} bytes")

    with open(source, "rb") as reader, open(target, "wb") as writer:
        reader.seek(8 + header_length)
        writer.write(struct.pack("<Q", header_length))
        writer.write(payload + b" " * (header_length - len(payload)))
        shutil.copyfileobj(reader, writer, length=32 << 20)


def reference_shapes(checkpoint: Path) -> dict[str, tuple[int, ...]]:
    """Shapes of the Hugging Face model that ``checkpoint/config.json`` describes."""
    config = AutoConfig.from_pretrained(checkpoint)
    with torch.device("meta"):
        model = AutoModelForImageTextToText.from_config(config)
    shapes = {name: tuple(tensor.shape) for name, tensor in model.state_dict().items()}
    del model
    return shapes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True, help="merged checkpoint with the broken parameter names")
    parser.add_argument("--output", required=True, help="directory to write the fixed checkpoint to")
    args = parser.parse_args()

    source = Path(args.checkpoint)
    target = Path(args.output)
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"{target} is not empty")

    index = json.loads((source / "model.safetensors.index.json").read_text())
    weight_map: dict[str, str] = index["weight_map"]
    shards = sorted(set(weight_map.values()))
    headers = {shard: read_header(source / shard) for shard in shards}
    shapes: dict[str, tuple[int, ...]] = {}
    for _, header in headers.values():
        shapes.update({name: tuple(meta["shape"]) for name, meta in header.items() if name != "__metadata__"})
    if set(shapes) != set(weight_map):
        raise SystemExit("index and safetensors disagree on the parameter names")

    renamed = {fix_key(name): name for name in shapes}
    if len(renamed) != len(shapes):
        raise SystemExit("renaming produced duplicate parameter names")

    expected = reference_shapes(source)
    missing = sorted(set(expected) - set(renamed))
    unexpected = sorted(set(renamed) - set(expected))
    mismatched = [name for name, old in renamed.items() if shapes[old] != expected[name]]
    if missing or unexpected or mismatched:
        raise SystemExit(
            f"renamed keys do not match the model in config.json: "
            f"missing={missing[:5]} unexpected={unexpected[:5]} shape_mismatch={mismatched[:5]}"
        )

    target.mkdir(parents=True, exist_ok=True)
    for shard in shards:
        header_length, header = headers[shard]
        write_shard(source / shard, target / shard, header_length, header)
        print(f"wrote {shard}")

    index["weight_map"] = {fix_key(name): shard for name, shard in weight_map.items()}
    (target / "model.safetensors.index.json").write_text(json.dumps(index, indent=2) + "\n")
    for item in sorted(source.iterdir()):
        if item.name == "model.safetensors.index.json" or item.suffix == ".safetensors":
            continue
        shutil.copy2(item, target / item.name, follow_symlinks=True)

    for shard in shards:
        with safe_open(target / shard, framework="pt") as handle:
            for name in handle.keys():
                assert tuple(handle.get_slice(name).get_shape()) == expected[name], name
    print(f"fixed checkpoint written to {target}, {len(renamed)} parameters renamed")


if __name__ == "__main__":
    main()
