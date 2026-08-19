"""Offline probe that loads the exact DeBERTa main revision from safetensors only."""

from __future__ import annotations

import hashlib
import json
import pathlib


MODEL_ID = "microsoft/deberta-v3-base"
EXPECTED_SAFE_SHA256 = "57cbd0cad054ba5be8d4c6965b836e132f029edbbe3ed9c5bc9ef4fe1c40c34e"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    import torch
    import transformers
    from transformers import DebertaV2Model

    repo = pathlib.Path("/hf/hub/models--microsoft--deberta-v3-base")
    revision = (repo / "refs" / "main").read_text(encoding="ascii").strip()
    snapshot = repo / "snapshots" / revision
    safe = snapshot / "model.safetensors"
    unsafe = snapshot / "pytorch_model.bin"
    if unsafe.exists() or unsafe.is_symlink():
        raise RuntimeError("unsafe PyTorch link remains in the main snapshot")
    if not safe.is_file() or not safe.is_symlink() or sha256(safe) != EXPECTED_SAFE_SHA256:
        raise RuntimeError("main safetensors link/hash differs")
    model = DebertaV2Model.from_pretrained(MODEL_ID, local_files_only=True)
    result = {
        "status": "E2A_DEBERTA_SAFETENSORS_OFFLINE_LOAD_PASS",
        "model_id": MODEL_ID,
        "revision": revision,
        "model_class": type(model).__name__,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "hidden_size": model.config.hidden_size,
        "safe_sha256": EXPECTED_SAFE_SHA256,
        "pytorch_link_present": False,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "network_required": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
