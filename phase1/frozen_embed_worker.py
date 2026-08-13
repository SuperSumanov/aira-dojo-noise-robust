#!/usr/bin/env python3
"""Checkpointable frozen 0.5B feature extraction for one deterministic shard."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


class IntegrityError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def task_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("desc") or "")
    return str(value or "")


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def git_commit(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()


def load_manifest(
    path: Path, shard: int, num_shards: int
) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    if not rows:
        raise IntegrityError("empty manifest")
    ids = [str(row["card_id"]) for row in rows]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise IntegrityError("manifest IDs are not sorted and unique")
    for row in rows:
        assigned = int(row["shard"])
        if not 0 <= assigned < num_shards:
            raise IntegrityError(f"invalid shard assignment: {assigned}")
    selected = [row for row in rows if int(row["shard"]) == shard]
    if not selected:
        raise IntegrityError(f"manifest shard {shard} is empty")
    return selected, hashlib.sha256(raw).hexdigest()


def load_cards(
    path: Path, manifest: list[dict[str, Any]], expected_sha: str | None
) -> tuple[dict[str, str], str, int]:
    expected = {str(row["card_id"]): row for row in manifest}
    found: dict[str, str] = {}
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for raw_line in handle:
            digest.update(raw_line)
            total += 1
            row = json.loads(raw_line)
            card_id = str(row["id"])
            if card_id not in expected:
                continue
            if card_id in found:
                raise IntegrityError(f"duplicate card id: {card_id}")
            code = str(row.get("code") or "")
            if not code:
                raise IntegrityError(f"empty code: {card_id}")
            if hashlib.sha256(code.encode("utf-8")).hexdigest() != expected[card_id][
                "code_sha256"
            ]:
                raise IntegrityError(f"code SHA mismatch: {card_id}")
            if len(code) != int(expected[card_id]["code_chars"]):
                raise IntegrityError(f"code length mismatch: {card_id}")
            if task_name(row.get("task")) != str(expected[card_id]["task"]):
                raise IntegrityError(f"task mismatch: {card_id}")
            found[card_id] = code
    digest_value = digest.hexdigest()
    if expected_sha and digest_value != expected_sha.lower():
        raise IntegrityError("cards SHA256 mismatch")
    missing = sorted(expected.keys() - found.keys())
    if missing:
        raise IntegrityError(f"missing cards, examples={missing[:8]}")
    return found, digest_value, total


def existing_prefix(
    out_dir: Path, expected_ids: list[str]
) -> tuple[int, int | None, list[dict[str, Any]]]:
    consumed = 0
    feature_dim: int | None = None
    chunk_records: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("chunk_*.npz")):
        with np.load(path, allow_pickle=False) as data:
            ids = [str(value) for value in data["card_ids"].tolist()]
            features = np.asarray(data["features"])
            token_counts = np.asarray(data["token_counts"])
            code_chars = np.asarray(data["code_chars"])
        if not ids or ids != expected_ids[consumed : consumed + len(ids)]:
            raise IntegrityError(f"non-contiguous or unexpected chunk IDs: {path}")
        if features.ndim != 2 or features.shape[0] != len(ids):
            raise IntegrityError(f"invalid feature shape: {path}")
        if token_counts.shape != (len(ids),) or code_chars.shape != (len(ids),):
            raise IntegrityError(f"invalid metadata shape: {path}")
        if not np.isfinite(features).all():
            raise IntegrityError(f"non-finite features: {path}")
        if feature_dim is None:
            feature_dim = int(features.shape[1])
        elif feature_dim != int(features.shape[1]):
            raise IntegrityError(f"feature dimension mismatch: {path}")
        consumed += len(ids)
        chunk_records.append(
            {
                "file": path.name,
                "rows": len(ids),
                "sha256": sha256(path),
            }
        )
    return consumed, feature_dim, chunk_records


def truncate(ids: list[int], max_len: int, head_fraction: float) -> list[int]:
    if len(ids) <= max_len:
        return ids
    head = int(max_len * head_fraction)
    return ids[:head] + ids[-(max_len - head) :]


def save_chunk(
    path: Path,
    card_ids: list[str],
    features: np.ndarray,
    token_counts: np.ndarray,
    code_chars: np.ndarray,
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            card_ids=np.asarray(card_ids),
            features=np.asarray(features, dtype=np.float16),
            token_counts=np.asarray(token_counts, dtype=np.int32),
            code_chars=np.asarray(code_chars, dtype=np.int32),
        )
    os.replace(temporary, path)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--num-shards", type=int, default=4)
    parser.add_argument("--max-len", type=int, default=8192)
    parser.add_argument("--head-fraction", type=float, default=0.25)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--chunk-size", type=int, default=32)
    parser.add_argument(
        "--limit-cards",
        type=int,
        default=0,
        help="label-blind sorted-prefix limit for GPU smoke only; zero means full shard",
    )
    parser.add_argument("--expect-cards-sha256")
    parser.add_argument("--expect-manifest-sha256")
    parser.add_argument("--expect-model-sha256")
    parser.add_argument("--expect-commit")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if not 0 <= args.shard < args.num_shards:
        raise ValueError("shard must be in [0, num_shards)")
    if (
        args.max_len <= 0
        or args.batch_size <= 0
        or args.chunk_size <= 0
        or args.limit_cards < 0
    ):
        raise ValueError("length and batch/chunk sizes must be positive")
    if not 0.0 < args.head_fraction < 1.0:
        raise ValueError("head_fraction must be in (0, 1)")
    commit = git_commit(args.repo_root)
    if args.expect_commit and commit != args.expect_commit:
        raise IntegrityError(f"commit mismatch: {commit}")
    model_weights = args.model / "model.safetensors"
    if not model_weights.exists():
        raise FileNotFoundError(model_weights)
    model_sha = sha256(model_weights)
    if args.expect_model_sha256 and model_sha != args.expect_model_sha256.lower():
        raise IntegrityError("model SHA256 mismatch")
    manifest, manifest_sha = load_manifest(args.manifest, args.shard, args.num_shards)
    if args.expect_manifest_sha256 and manifest_sha != args.expect_manifest_sha256.lower():
        raise IntegrityError("manifest SHA256 mismatch")
    if args.limit_cards:
        manifest = manifest[: args.limit_cards]
    expected_ids = [str(row["card_id"]) for row in manifest]
    manifest_by_id = {str(row["card_id"]): row for row in manifest}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = args.out_dir / "metadata.json"
    previous: dict[str, Any] = {}
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        previous_config = previous.get("config") or {}
        expected_config = {
            "shard": args.shard,
            "num_shards": args.num_shards,
            "max_len": args.max_len,
            "head_fraction": args.head_fraction,
            "batch_size": args.batch_size,
            "chunk_size": args.chunk_size,
            "limit_cards": args.limit_cards,
        }
        if previous.get("git_commit") != commit or previous_config != expected_config:
            raise IntegrityError("resume metadata does not match current source/config")
    consumed, feature_dim, chunks = existing_prefix(args.out_dir, expected_ids)
    if previous:
        previous_inputs = previous.get("inputs") or {}
        if previous.get("status") not in {"RUNNING", "COMPLETE"}:
            raise IntegrityError("resume metadata has an invalid status")
        if previous.get("source_sha256") != sha256(Path(__file__)):
            raise IntegrityError("resume worker-source hash mismatch")
        if (
            previous_inputs.get("manifest_sha256") != manifest_sha
            or previous_inputs.get("model_weights_sha256") != model_sha
        ):
            raise IntegrityError("resume input provenance mismatch")
        if (
            args.expect_cards_sha256
            and previous_inputs.get("cards_sha256") != args.expect_cards_sha256.lower()
        ):
            raise IntegrityError("resume cards provenance mismatch")
        if previous.get("status") == "COMPLETE" and consumed != len(expected_ids):
            raise IntegrityError("COMPLETE metadata has incomplete chunks")
    if consumed == len(expected_ids):
        if not metadata_path.exists():
            raise IntegrityError("all chunks exist but metadata is absent")
        if previous.get("status") == "RUNNING":
            previous_feature = previous.get("feature") or {}
            if (
                previous.get("source_sha256") != sha256(Path(__file__))
                or previous_inputs.get("manifest_sha256") != manifest_sha
                or previous_inputs.get("model_weights_sha256") != model_sha
                or int(previous_feature.get("dimension", -1)) != int(feature_dim or -1)
            ):
                raise IntegrityError("cannot finalize resumed shard: provenance mismatch")
            if (
                args.expect_cards_sha256
                and previous_inputs.get("cards_sha256")
                != args.expect_cards_sha256.lower()
            ):
                raise IntegrityError("cannot finalize resumed shard: cards hash mismatch")
            previous.update(
                {
                    "status": "COMPLETE",
                    "completed_cards": consumed,
                    "chunks": chunks,
                    "resumed_finalization": True,
                }
            )
            atomic_json(metadata_path, previous)
        elif previous.get("status") != "COMPLETE":
            raise IntegrityError("all chunks exist but metadata has an invalid status")
        print(
            "FROZEN_EMBED_WORKER_ALREADY_COMPLETE",
            f"shard={args.shard}",
            f"cards={consumed}",
            flush=True,
        )
        return 0

    cards, cards_sha, corpus_rows = load_cards(
        args.cards, manifest, args.expect_cards_sha256
    )
    started = time.time()
    metadata: dict[str, Any] = {
        "status": "RUNNING",
        "protocol": "frozen_embed_v11_discovery_v1",
        "git_commit": commit,
        "source_sha256": sha256(Path(__file__)),
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "command": [sys.executable, *sys.argv],
        "config": {
            "shard": args.shard,
            "num_shards": args.num_shards,
            "max_len": args.max_len,
            "head_fraction": args.head_fraction,
            "batch_size": args.batch_size,
            "chunk_size": args.chunk_size,
            "limit_cards": args.limit_cards,
        },
        "inputs": {
            "cards_sha256": cards_sha,
            "cards_rows": corpus_rows,
            "manifest_sha256": manifest_sha,
            "model_weights_sha256": model_sha,
        },
        "expected_cards": len(expected_ids),
        "resumed_cards": consumed,
        "chunks": chunks,
    }
    atomic_json(metadata_path, metadata)

    import torch
    from transformers import AutoModel, AutoTokenizer, __version__ as transformers_version

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen feature extraction")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    model_kwargs: dict[str, Any] = {
        "torch_dtype": torch.bfloat16,
        "low_cpu_mem_usage": True,
    }
    attention_backend = "flash_attention_2"
    try:
        model = AutoModel.from_pretrained(
            args.model, attn_implementation=attention_backend, **model_kwargs
        )
    except (ImportError, ValueError):
        attention_backend = "sdpa"
        model = AutoModel.from_pretrained(
            args.model, attn_implementation=attention_backend, **model_kwargs
        )
    model = model.cuda().eval()
    model.config.use_cache = False
    hidden_size = int(model.config.hidden_size)
    expected_feature_dim = hidden_size * 2
    if feature_dim is not None and feature_dim != expected_feature_dim:
        raise IntegrityError("existing chunk feature dimension differs from model")
    metadata["software"] = {
        "torch": torch.__version__,
        "transformers": transformers_version,
        "cuda": str(torch.version.cuda),
        "gpu": torch.cuda.get_device_name(0),
        "attention_backend": attention_backend,
    }
    metadata["feature"] = {
        "definition": "concat(masked_mean_last_hidden)",
        "dtype": "float16",
        "hidden_size": hidden_size,
        "dimension": expected_feature_dim,
        "task_prefix": True,
    }
    atomic_json(metadata_path, metadata)

    for chunk_start in range(consumed, len(expected_ids), args.chunk_size):
        chunk_ids = expected_ids[chunk_start : chunk_start + args.chunk_size]
        chunk_features: list[np.ndarray] = []
        chunk_tokens: list[int] = []
        chunk_chars: list[int] = []
        for batch_start in range(0, len(chunk_ids), args.batch_size):
            batch_ids = chunk_ids[batch_start : batch_start + args.batch_size]
            sequences: list[list[int]] = []
            for card_id in batch_ids:
                task = str(manifest_by_id[card_id]["task"])
                text = f"# MLE-bench task: {task}\n{cards[card_id]}"
                token_ids = tokenizer(text, add_special_tokens=False)["input_ids"]
                if not token_ids:
                    token_ids = [int(tokenizer.eos_token_id)]
                token_ids = truncate(token_ids, args.max_len, args.head_fraction)
                sequences.append(token_ids)
                chunk_tokens.append(len(token_ids))
                chunk_chars.append(len(cards[card_id]))
            width = max(len(sequence) for sequence in sequences)
            pad = int(tokenizer.pad_token_id)
            input_ids = torch.tensor(
                [sequence + [pad] * (width - len(sequence)) for sequence in sequences],
                dtype=torch.long,
                device="cuda",
            )
            attention_mask = torch.tensor(
                [
                    [1] * len(sequence) + [0] * (width - len(sequence))
                    for sequence in sequences
                ],
                dtype=torch.long,
                device="cuda",
            )
            with torch.inference_mode():
                hidden = model(
                    input_ids=input_ids, attention_mask=attention_mask, use_cache=False
                ).last_hidden_state
            mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
            mean_pool = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
            final = attention_mask.sum(1) - 1
            last = hidden[
                torch.arange(hidden.shape[0], device=hidden.device), final
            ]
            features = torch.cat((mean_pool, last), dim=1).float().cpu().numpy()
            if not np.isfinite(features).all():
                raise IntegrityError("non-finite model features")
            chunk_features.append(features)
            del input_ids, attention_mask, hidden, mask, mean_pool, last, features
        matrix = np.vstack(chunk_features)
        chunk_end = chunk_start + len(chunk_ids)
        chunk_path = args.out_dir / f"chunk_{chunk_start:06d}_{chunk_end:06d}.npz"
        if chunk_path.exists():
            raise FileExistsError(chunk_path)
        save_chunk(
            chunk_path,
            chunk_ids,
            matrix,
            np.asarray(chunk_tokens),
            np.asarray(chunk_chars),
        )
        metadata["chunks"].append(
            {
                "file": chunk_path.name,
                "rows": len(chunk_ids),
                "sha256": sha256(chunk_path),
            }
        )
        metadata["completed_cards"] = chunk_end
        metadata["elapsed_s"] = time.time() - started
        atomic_json(metadata_path, metadata)
        print(
            "FROZEN_EMBED_CHUNK",
            f"shard={args.shard}",
            f"cards={chunk_end}/{len(expected_ids)}",
            f"elapsed_s={metadata['elapsed_s']:.3f}",
            flush=True,
        )

    consumed_after, feature_dim_after, chunks_after = existing_prefix(
        args.out_dir, expected_ids
    )
    if consumed_after != len(expected_ids) or feature_dim_after != expected_feature_dim:
        raise IntegrityError("post-write shard completeness check failed")
    metadata.update(
        {
            "status": "COMPLETE",
            "completed_cards": consumed_after,
            "elapsed_s": time.time() - started,
            "chunks": chunks_after,
        }
    )
    atomic_json(metadata_path, metadata)
    print(
        "FROZEN_EMBED_WORKER_COMPLETE",
        f"shard={args.shard}",
        f"cards={consumed_after}",
        f"chunks={len(chunks_after)}",
        f"elapsed_s={metadata['elapsed_s']:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
