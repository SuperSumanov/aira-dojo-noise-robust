"""CPU-only source-parity check; no checkpoint loading or real-data reader."""
from __future__ import annotations

import argparse
import ast
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Sequence

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from torch import nn
import transformers
from transformers import AutoTokenizer, Qwen3Config, Qwen3Model

from phase1.g_reuse_endpoint_inference import encode_endpoints, score_endpoints

SOURCE_COMMIT = "5f3bc362db922c8edee2ef134656dfdb9a2b74fb"
SOURCE_HASHES = {
    "src/mle_critic/src/train/bradley_terry.py": "d3cfd12602dc399a456810d4f706124df7117834ebba124813233f77ba043977",
    "src/mle_critic/src/train/dataset/pairs.py": "3e1969499405199a187c12106d9f4d4a5542b4a1ecf094e0bd9f7c71514b4643",
}


def source_definitions(root):
    namespace = {"torch": torch, "nn": nn, "dataclass": dataclass, "Any": Any, "Sequence": Sequence}
    for path, expected in SOURCE_HASHES.items():
        raw = subprocess.check_output(["git", "-C", str(root), "show", SOURCE_COMMIT + ":" + path])
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError("reference_source_drift")
        # Extract only these definitions. Never execute train main or file readers.
        tree = ast.parse(raw.decode())
        nodes = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                 and node.name in {"CardEncoder", "pair_collate", "BradleyTerryRewardModel"}]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "hash_bound_reference", "exec"), namespace)
    return namespace


class ByteTokenizer:
    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {"input_ids": [1 + ord(c) % 256 for c in text]}


def fixture():
    return [{"endpoint_id": "synthetic:a", "task_name": "任务", "code": "x = 1\n" * 40},
            {"endpoint_id": "synthetic:b", "task_name": "task", "code": ""},
            {"endpoint_id": "synthetic:c", "task_name": "task", "code": "print(42)"},
            {"endpoint_id": "synthetic:d", "task_name": "task", "code": "# tail\n"}]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if torch.__version__ != "2.11.0+cu128" or transformers.__version__ != "5.12.1":
        raise RuntimeError("unexpected_runtime")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    assert not torch.cuda.is_initialized()
    args.output.mkdir(parents=True, exist_ok=False)
    ref = source_definitions(args.source_root)
    rows = fixture()
    encoding_rows = rows + [{"endpoint_id": "synthetic:long", "task_name": "task", "code": "x=1\n" * 10000}]
    code = {r["endpoint_id"]: r["code"] for r in encoding_rows}
    tasks = {r["endpoint_id"]: r["task_name"] for r in encoding_rows}
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True, trust_remote_code=False)
    parity = []
    for name, tok in (("byte", ByteTokenizer()), ("pinned_qwen", tokenizer)):
        for context in (1, 3, 16, 64, 16384):
            old = ref["CardEncoder"](code=code, tasks=tasks, tokenizer=tok, max_len=context,
                                     head_frac=.25, task_cond=True, budget_cond=False)
            new = encode_endpoints(encoding_rows, tok, max_len=context)
            assert all(tuple(old.encode(r.endpoint_id)) == r.input_ids for r in new)
            parity.append({"tokenizer": name, "max_len": context, "endpoints": len(new), "tokens_equal": True})
    cases = []
    for seed in (6, 7, 8):
        torch.manual_seed(seed)
        config = Qwen3Config(vocab_size=257, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
                            num_attention_heads=2, num_key_value_heads=1, head_dim=8,
                            max_position_embeddings=256, pad_token_id=0, use_cache=False,
                            attn_implementation="eager")
        cls = ref["BradleyTerryRewardModel"]
        model = cls.__new__(cls)
        nn.Module.__init__(model)
        model.backbone = Qwen3Model(config)
        model.head = nn.Linear(16, 1, dtype=torch.float32)
        model.eval()
        initial = {k: v.detach().clone() for k, v in model.state_dict().items()}
        new = encode_endpoints(rows, ByteTokenizer(), max_len=64)
        lookup = {r.endpoint_id: list(r.input_ids) for r in new}
        pairs = [("synthetic:a", "synthetic:b"), ("synthetic:a", "synthetic:c"), ("synthetic:d", "synthetic:b")]
        packed = ref["pair_collate"]([{"b": lookup[a], "w": lookup[b]} for a, b in pairs], pad_token_id=0)
        with torch.inference_mode():
            scores = model(**packed)["logits"]
            expected = scores[:len(pairs)] - scores[len(pairs):]
        for batch in (1, 2, 4):
            for reverse in (False, True):
                actual, receipt = score_endpoints(model, tuple(reversed(new)) if reverse else new,
                                                  pad_id=0, batch_size=batch, device="cpu")
                observed = torch.tensor([actual[a] - actual[b] for a, b in pairs])
                torch.testing.assert_close(observed, expected, atol=1e-6, rtol=1e-5)
                assert all(torch.equal(initial[k], v) for k, v in model.state_dict().items())
                assert all(p.grad is None for p in model.parameters())
                cases.append({"seed": seed, "endpoint_batch": batch, "reversed_input": reverse,
                              "endpoints": receipt["endpoints"], "pairs": len(pairs),
                              "forward_calls": receipt["forward_calls"], "valid_tokens": receipt["valid_tokens"],
                              "padded_slots": receipt["padded_slots"],
                              "max_abs_margin_difference": float((observed - expected).abs().max()),
                              "parameters_unchanged": True, "pass": True})
    assert not torch.cuda.is_initialized()
    with (args.output / "cases.csv").open("x", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cases[0])); writer.writeheader(); writer.writerows(cases)
    summary = {
        "classification": "CPU_REFERENCE_FORWARD_PARITY_NOT_CRITIC_EFFECT",
        "reference_commit": SOURCE_COMMIT, "reference_source_sha256": SOURCE_HASHES,
        "adapter_sha256": hashlib.sha256(Path(__file__).parents[1].joinpath("g_reuse_endpoint_inference.py").read_bytes()).hexdigest(),
        "validation_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runtime": {"torch": torch.__version__, "transformers": transformers.__version__},
        "seeds": [6, 7, 8], "token_parity_cases": parity, "forward_parity_cases": len(cases),
        "max_abs_margin_difference": max(row["max_abs_margin_difference"] for row in cases),
        "gpu_used": False, "model_fits": 0, "real_checkpoint_loaded": False, "protected_inputs_read": False,
        "cuda_initialized": torch.cuda.is_initialized(),
    }
    with (args.output / "summary.json").open("x", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True, allow_nan=False); f.write("\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
