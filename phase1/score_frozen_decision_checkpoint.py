"""Score a locked Bradley-Terry checkpoint on frozen decision pairs.

The checkpoint is selected before this script sees the frozen labels.  Inference scores
each card independently; pair orientation is used only after all card scores are fixed.
Outputs one JSONL row per pair plus run/task-clustered summaries.

This loader matches ``src/mle_critic/src/train/bradley_terry.py`` on the senior branch:
AutoModel backbone, right-padding, final non-pad token pooling, and a bf16 linear head.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
import platform
import random
import subprocess
import sys
from pathlib import Path
from typing import Any


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", required=True)
    parser.add_argument("--run-map", required=True)
    parser.add_argument(
        "--pairs", action="append", required=True, metavar="NAME=PATH",
        help="repeat for frozen_b0/frozen_b1/frozen_b2; extension must use a distinct name",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkpoint", help="exact locked Trainer checkpoint directory")
    source.add_argument(
        "--scores-json", help="CPU audit mode: precomputed {card_id: score} JSON",
    )
    parser.add_argument("--base-model", help="required with --checkpoint")
    parser.add_argument("--expect-cards-sha256")
    parser.add_argument("--expect-run-map-sha256")
    parser.add_argument(
        "--expect-pairs", action="append", default=[], metavar="NAME=COUNT:SHA256",
        help="optional frozen-file lock; repeat for every --pairs input",
    )
    parser.add_argument(
        "--checkpoint-locked-before-frozen", action="store_true",
        help="required attestation: checkpoint/model choice was fixed before reading frozen labels",
    )
    parser.add_argument("--max-len", type=int, default=16384)
    parser.add_argument("--head-frac", type=float, default=0.25)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--task-cond", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--budget-cond", action="store_true")
    parser.add_argument("--budget-pos", choices=("head", "tail"), default="head")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_pair_specs(values: list[str]) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"pair spec needs NAME=PATH: {value}")
        name, raw_path = value.split("=", 1)
        if not name or name in output:
            raise ValueError(f"empty or duplicate pair-set name: {name}")
        output[name] = Path(raw_path)
    return output


def parse_pair_expectations(values: list[str]) -> dict[str, tuple[int, str]]:
    output: dict[str, tuple[int, str]] = {}
    for value in values:
        if "=" not in value or ":" not in value:
            raise ValueError(f"pair expectation needs NAME=COUNT:SHA256: {value}")
        name, raw = value.split("=", 1)
        raw_count, digest = raw.split(":", 1)
        if not name or name in output:
            raise ValueError(f"empty or duplicate pair expectation: {name}")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest.lower()):
            raise ValueError(f"invalid SHA256 for {name}")
        count = int(raw_count)
        if count <= 0:
            raise ValueError(f"pair count must be positive for {name}")
        output[name] = (count, digest.lower())
    return output


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "not-a-git-worktree"


def git_dirty() -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False,
    )
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def file_manifest(paths: list[Path], root: Path) -> dict[str, dict[str, int | str]]:
    return {
        str(path.relative_to(root)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(set(paths))
    }


def cluster_bootstrap(
    rows: list[dict[str, Any]], field: str, cluster: str, draws: int, seed: int,
) -> list[float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row[cluster])].append(float(row[field]))
    keys = sorted(grouped)
    if not keys:
        raise ValueError("empty bootstrap population")
    rng = random.Random(seed)
    samples = []
    for _ in range(draws):
        selected = [rng.choice(keys) for _ in keys]
        values = [value for key in selected for value in grouped[key]]
        samples.append(sum(values) / len(values))
    samples.sort()
    return [samples[int(0.025 * draws)], samples[int(0.975 * draws)]]


def exact_run_sign(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for row in rows:
        grouped[str(row["run_id"])].append(float(row["pair_accuracy"]) - 0.5)
    effects = [sum(values) / len(values) for values in grouped.values()]
    positive = sum(value > 0 for value in effects)
    negative = sum(value < 0 for value in effects)
    tied = len(effects) - positive - negative
    informative = positive + negative
    smaller = min(positive, negative)
    tail = (
        sum(math.comb(informative, k) for k in range(smaller + 1)) / 2**informative
        if informative else 0.5
    )
    return {
        "positive": positive, "negative": negative, "tied": tied,
        "exact_p_two_sided": min(1.0, 2.0 * tail),
    }


def load_cards(path: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    code: dict[str, str] = {}
    task: dict[str, str] = {}
    for row in jsonl(path):
        card_id = str(row["id"])
        if card_id in code:
            raise RuntimeError(f"duplicate card id: {card_id}")
        code[card_id] = row.get("code") or ""
        task[card_id] = str((row.get("task") or {}).get("name", ""))
    return code, task


def validate_pairs(
    pair_sets: dict[str, Path], code: dict[str, str], task: dict[str, str], run_of: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    validated = {}
    for name, path in pair_sets.items():
        rows = jsonl(path)
        if not rows:
            raise RuntimeError(f"{name} is empty")
        ordered: set[tuple[str, str]] = set()
        unordered: set[frozenset[str]] = set()
        for row in rows:
            better, worse = str(row["better"]), str(row["worse"])
            if row.get("intask_split") != "test":
                raise RuntimeError(f"{name} contains non-test row")
            if better not in code or worse not in code:
                raise RuntimeError(f"{name} endpoint absent from cards")
            if better == worse:
                raise RuntimeError(f"{name} contains a self-pair")
            if not code[better].strip() or not code[worse].strip():
                raise RuntimeError(f"{name} contains empty code")
            if task[better] != task[worse] or task[better] != row.get("task"):
                raise RuntimeError(f"{name} mixed/mismatched task")
            if better not in run_of or worse not in run_of or run_of[better] != run_of[worse]:
                raise RuntimeError(f"{name} pair crosses physical runs")
            key = (better, worse)
            undirected = frozenset(key)
            if key in ordered or undirected in unordered:
                raise RuntimeError(f"{name} duplicate or reversed pair")
            ordered.add(key)
            unordered.add(undirected)
        validated[name] = rows
    return validated


def load_checkpoint_scores(
    args: argparse.Namespace,
    pair_sets: dict[str, list[dict[str, Any]]],
    code: dict[str, str],
    task: dict[str, str],
) -> tuple[dict[str, float], dict[str, str], dict[str, dict[str, int | str]]]:
    if not args.base_model:
        raise ValueError("--base-model is required with --checkpoint")
    if not args.checkpoint_locked_before_frozen:
        raise ValueError("checkpoint scoring requires --checkpoint-locked-before-frozen")
    import torch
    import torch.nn as nn
    import safetensors
    from safetensors.torch import load_file as load_safetensors
    from transformers import AutoModel, AutoTokenizer, __version__ as transformers_version

    class RewardModel(nn.Module):
        def __init__(self, model_name: str):
            super().__init__()
            kwargs = {"torch_dtype": torch.bfloat16, "low_cpu_mem_usage": True}
            try:
                self.backbone = AutoModel.from_pretrained(
                    model_name, attn_implementation="flash_attention_2", **kwargs,
                )
            except Exception:
                self.backbone = AutoModel.from_pretrained(model_name, **kwargs)
            self.head = nn.Linear(
                self.backbone.config.hidden_size, 1, dtype=torch.bfloat16,
            )

        def forward(self, input_ids, attention_mask):
            hidden = self.backbone(
                input_ids=input_ids, attention_mask=attention_mask,
            ).last_hidden_state
            final = attention_mask.sum(dim=1) - 1
            pooled = hidden[
                torch.arange(hidden.size(0), device=hidden.device), final,
            ]
            return self.head(pooled).squeeze(-1).float()

    checkpoint = Path(args.checkpoint)
    if not checkpoint.is_dir():
        raise FileNotFoundError(checkpoint)
    state: dict[str, Any] = {}
    weight_paths: list[Path] = []
    safe_index = checkpoint / "model.safetensors.index.json"
    bin_index = checkpoint / "pytorch_model.bin.index.json"
    if safe_index.exists():
        index = json.loads(safe_index.read_text(encoding="utf-8"))
        for shard in sorted(set(index["weight_map"].values())):
            weight_path = checkpoint / shard
            weight_paths.append(weight_path)
            state.update(load_safetensors(str(weight_path), device="cpu"))
        weight_paths.append(safe_index)
    elif (checkpoint / "model.safetensors").exists():
        weight_path = checkpoint / "model.safetensors"
        weight_paths.append(weight_path)
        state = load_safetensors(str(weight_path), device="cpu")
    elif bin_index.exists():
        index = json.loads(bin_index.read_text(encoding="utf-8"))
        for shard in sorted(set(index["weight_map"].values())):
            weight_path = checkpoint / shard
            weight_paths.append(weight_path)
            state.update(torch.load(weight_path, map_location="cpu", weights_only=True))
        weight_paths.append(bin_index)
    elif (checkpoint / "pytorch_model.bin").exists():
        weight_path = checkpoint / "pytorch_model.bin"
        weight_paths.append(weight_path)
        state = torch.load(weight_path, map_location="cpu", weights_only=True)
    else:
        raise FileNotFoundError(f"no supported model weights under {checkpoint}")
    if set(state) and all(key.startswith("module.") for key in state):
        state = {key.removeprefix("module."): value for key, value in state.items()}

    model = RewardModel(args.base_model)
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        raise RuntimeError(
            f"checkpoint architecture mismatch; missing={missing[:8]} unexpected={unexpected[:8]}"
        )
    del state
    if not torch.cuda.is_available():
        raise RuntimeError("checkpoint scoring requires CUDA; use --scores-json for CPU audit")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda")
    model.to(device).eval()
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    def budget_line(budget: int) -> str:
        return (
            "# remaining budget: unlimited\n" if budget == 0
            else f"# remaining budget: {budget} steps\n"
        )

    def encode(card_id: str, budget: int) -> list[int]:
        conditioned = budget if args.budget_cond else None
        prefix = f"# MLE-bench task: {task[card_id]}\n" if args.task_cond else ""
        if conditioned is not None and args.budget_pos == "head":
            prefix += budget_line(conditioned)
        suffix = (
            tokenizer("\n" + budget_line(conditioned), add_special_tokens=False)["input_ids"]
            if conditioned is not None and args.budget_pos == "tail" else []
        )
        tokens = tokenizer(prefix + code[card_id], add_special_tokens=False)["input_ids"]
        room = args.max_len - len(suffix)
        if room <= 0:
            raise ValueError("budget suffix exhausts max_len")
        if len(tokens) > room:
            head = int(room * args.head_frac)
            tokens = tokens[:head] + tokens[-(room - head):]
        return tokens + suffix

    items = sorted({
        (str(row[key]), int(row.get("budget", 0)) if args.budget_cond else 0)
        for rows in pair_sets.values() for row in rows for key in ("better", "worse")
    })
    output: dict[str, float] = {}
    with torch.inference_mode():
        for start in range(0, len(items), args.batch_size):
            batch = items[start:start + args.batch_size]
            sequences = [encode(card_id, budget) for card_id, budget in batch]
            width = max(map(len, sequences))
            input_ids = torch.tensor([
                seq + [tokenizer.pad_token_id] * (width - len(seq)) for seq in sequences
            ], device=device)
            attention = torch.tensor([
                [1] * len(seq) + [0] * (width - len(seq)) for seq in sequences
            ], device=device)
            scores = model(input_ids=input_ids, attention_mask=attention).cpu().tolist()
            for (card_id, budget), score in zip(batch, scores):
                key = f"{card_id}|b{budget}" if args.budget_cond else card_id
                output[key] = float(score)
            print(f"[frozen-score] {min(start + len(batch), len(items))}/{len(items)}", flush=True)
    versions = {
        "torch": torch.__version__, "transformers": transformers_version,
        "safetensors": safetensors.__version__, "device": str(device),
        "cuda": str(torch.version.cuda), "gpu": torch.cuda.get_device_name(device),
    }
    return output, versions, file_manifest(weight_paths, checkpoint)


def main() -> None:
    args = arguments()
    if args.bootstrap <= 0 or args.batch_size <= 0 or args.max_len <= 0:
        raise ValueError("bootstrap, batch-size, and max-len must be positive")
    if not 0.0 <= args.head_frac <= 1.0:
        raise ValueError("head-frac must be in [0, 1]")
    random.seed(args.seed)
    pair_paths = parse_pair_specs(args.pairs)
    expected_pairs = parse_pair_expectations(args.expect_pairs)
    if args.checkpoint and (
        not args.expect_cards_sha256 or not args.expect_run_map_sha256 or not expected_pairs
    ):
        raise ValueError(
            "checkpoint mode requires locked cards/run-map SHA256 and --expect-pairs entries"
        )
    if expected_pairs and set(expected_pairs) != set(pair_paths):
        raise ValueError("--expect-pairs names must exactly match --pairs names")
    if args.expect_cards_sha256 and sha256(args.cards) != args.expect_cards_sha256.lower():
        raise RuntimeError("cards SHA256 differs from the locked value")
    if args.expect_run_map_sha256 and sha256(args.run_map) != args.expect_run_map_sha256.lower():
        raise RuntimeError("run-map SHA256 differs from the locked value")
    code, task = load_cards(args.cards)
    run_of = json.loads(Path(args.run_map).read_text(encoding="utf-8"))
    pair_sets = validate_pairs(pair_paths, code, task, run_of)
    for name, (expected_count, expected_sha) in expected_pairs.items():
        if len(pair_sets[name]) != expected_count or sha256(pair_paths[name]) != expected_sha:
            raise RuntimeError(f"{name} count or SHA256 differs from the locked value")

    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.scores_json:
        scores = {
            str(key): float(value) for key, value in
            json.loads(Path(args.scores_json).read_text(encoding="utf-8")).items()
        }
        versions = {"mode": "precomputed-card-scores"}
        checkpoint_files = None
    else:
        scores, versions, checkpoint_files = load_checkpoint_scores(args, pair_sets, code, task)
    invalid_scores = [key for key, value in scores.items() if not math.isfinite(value)]
    if invalid_scores:
        raise RuntimeError(f"non-finite card scores, examples={invalid_scores[:8]}")

    output_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for name, rows in pair_sets.items():
        scored = []
        for index, row in enumerate(rows):
            budget = int(row.get("budget", 0)) if args.budget_cond else 0
            bkey = f"{row['better']}|b{budget}" if args.budget_cond else row["better"]
            wkey = f"{row['worse']}|b{budget}" if args.budget_cond else row["worse"]
            if bkey not in scores or wkey not in scores:
                raise RuntimeError(f"missing score for {bkey} or {wkey}")
            margin = scores[bkey] - scores[wkey]
            accuracy = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
            record = {
                "pair_set": name, "pair_index": index,
                "better": row["better"], "worse": row["worse"],
                "parent": row.get("parent"), "task": row["task"],
                "run_id": run_of[row["better"]], "budget": int(row.get("budget", 0)),
                "margin": margin, "prediction": 1 if margin > 0 else (0 if margin < 0 else None),
                "pair_accuracy": accuracy,
            }
            scored.append(record)
            output_rows.append(record)
        accuracy = sum(row["pair_accuracy"] for row in scored) / len(scored)
        per_task = {}
        by_task: dict[str, list[float]] = collections.defaultdict(list)
        for row in scored:
            by_task[row["task"]].append(row["pair_accuracy"])
        for task_name, values in sorted(by_task.items()):
            per_task[task_name] = {"n": len(values), "accuracy": sum(values) / len(values)}
        summaries[name] = {
            "pairs": len(scored), "runs": len({row["run_id"] for row in scored}),
            "tasks": len(by_task), "accuracy": accuracy,
            "ties": sum(row["prediction"] is None for row in scored),
            "run_cluster_ci95": cluster_bootstrap(
                scored, "pair_accuracy", "run_id", args.bootstrap, args.seed,
            ),
            "task_cluster_ci95": cluster_bootstrap(
                scored, "pair_accuracy", "task", args.bootstrap, args.seed,
            ),
            "run_sign_vs_chance": exact_run_sign(scored), "per_task": per_task,
        }

    with (out_dir / "per_pair.jsonl").open("w", encoding="utf-8") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    prediction_map: dict[str, dict[str, int | None]] = collections.defaultdict(dict)
    for row in output_rows:
        prediction_map[row["pair_set"]][f"{row['better']}|{row['worse']}"] = row["prediction"]
    (out_dir / "predictions.json").write_text(
        json.dumps(prediction_map, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    provenance = {
        "git_commit": git_commit(), "git_dirty": git_dirty(),
        "command": [sys.executable, *sys.argv], "cwd": os.getcwd(),
        "python": platform.python_version(), "versions": versions,
        "seed": args.seed, "bootstrap": args.bootstrap,
        "checkpoint": args.checkpoint, "base_model": args.base_model,
        "checkpoint_weight_files": checkpoint_files,
        "checkpoint_selected_before_frozen_scoring": args.checkpoint_locked_before_frozen,
        "cards": {"path": args.cards, "sha256": sha256(args.cards)},
        "run_map": {"path": args.run_map, "sha256": sha256(args.run_map)},
        "pairs": {
            name: {"path": str(path), "sha256": sha256(path)}
            for name, path in pair_paths.items()
        },
        "scores_json": (
            {"path": args.scores_json, "sha256": sha256(args.scores_json)}
            if args.scores_json else None
        ),
        "script_sha256": sha256(__file__),
        "render": {
            "max_len": args.max_len, "head_frac": args.head_frac,
            "task_cond": args.task_cond, "budget_cond": args.budget_cond,
            "budget_pos": args.budget_pos,
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(
            {"provenance": provenance, "results": summaries},
            indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False,
        ) + "\n",
        encoding="utf-8",
    )
    for name, result in summaries.items():
        print(
            f"{name}: n={result['pairs']} runs={result['runs']} "
            f"acc={result['accuracy']:.4f} runCI={result['run_cluster_ci95']} "
            f"taskCI={result['task_cluster_ci95']}", flush=True,
        )
    print(f"WROTE {out_dir}", flush=True)


if __name__ == "__main__":
    main()
