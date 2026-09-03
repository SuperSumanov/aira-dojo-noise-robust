"""Build aggregate token-budget plans from bound historical train-only inputs.

No labels are retained: both sources are projected to canonical endpoint pairs
before ordering.  The output contains aggregate budgets and hashes only, never
card IDs, code, task names, labels, predictions, or model effects.  It loads an
offline tokenizer and the bound CardEncoder, but no model weights and performs
no fit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from phase1.global_local_execution_plan import BatchShape, EncoderBinding, Endpoint, Pair, digest_records
from phase1.global_local_batch_adapter import encoding_digest
from phase1.global_local_token_budget_plan import ARMS, build_plan
from phase1.historical_global_local_pool_readiness import GLOBAL, GLOBAL_SHA, project_pairs
from phase1.historical_train_encoding_readiness import (
    CARDS,
    CONFIG,
    ENCODER_CONFIG,
    EXPECTED,
    MODEL,
    SOURCE,
    TRAIN,
    checked_digest,
    extract_train_inputs,
    independent_encode,
    install_access_guard,
)
from phase1.verify_global_local_token_budget_plan import verify_arm_relations, verify_plan


PROTOCOL_NAME = "global_local_historical_development_protocol_v1.json"
FROZEN_NAME = "global_local_calibration_candidate_protocol_v2.json"
FROZEN_SHA256 = "3e0785a13f9d9fc3638a222e78fd74010757b1201249ebd0ad7a5597c224a2e9"
EXPECTED_COUNTS = {
    "local_pairs": 4689,
    "global_pairs": 9392,
    "local_endpoints": 4095,
    "additional_global_endpoints": 3640,
    "combined_valid_tokens": 104863947,
}


def _project_candidate_pairs(grouped, local, all_global):
    runs = {}
    tasks = {}
    for run_id, cards in grouped.items():
        if not isinstance(run_id, str) or not run_id or not isinstance(cards, list):
            raise ValueError("invalid_grouped_cards")
        for card in cards:
            card_id = card["id"]
            if card_id in runs:
                raise ValueError("duplicate_card_identity")
            runs[card_id] = run_id
            tasks[card_id] = card["task"]["name"]
    local_ids = {card_id for pair in local for card_id in pair}
    if not local_ids <= runs.keys():
        raise ValueError("local_missing_card")
    local_runs = {runs[card_id] for card_id in local_ids}
    local_set = set(local)
    candidate = [
        pair for pair in all_global
        if all(card_id in runs and runs[card_id] in local_runs for card_id in pair)
        and tasks[pair[0]] == tasks[pair[1]]
        and pair not in local_set
    ]
    if len(candidate) != len(set(candidate)):
        raise ValueError("candidate_global_duplicate")
    return tuple(candidate), runs, tasks


def _binding_digest(files):
    return digest_records(sorted((path.name, EXPECTED[path]) for path in files))


def run(output: Path, protocol_path: Path, frozen_path: Path, expected_protocol_sha: str,
        limit_seconds: int) -> None:
    if output.exists() or not output.is_relative_to(Path("/tmp")):
        raise ValueError("new_tmp_output_required")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or os.environ.get("HF_HUB_OFFLINE") != "1":
        raise ValueError("offline_cpu_environment_required")
    output.mkdir(mode=0o700)
    os.environ["TMPDIR"] = str(output)
    started = time.monotonic()
    opened, denied = install_access_guard(output)

    protocol_sha = checked_digest(protocol_path, expected_protocol_sha, scan=True)
    checked_digest(frozen_path, FROZEN_SHA256, scan=True)
    for path, expected in EXPECTED.items():
        checked_digest(path, expected, scan=path in (TRAIN, CARDS))
    checked_digest(GLOBAL, GLOBAL_SHA, scan=True)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (protocol.get("status") != "APPROVED_PROTOCOL_IMPLEMENTATION_EFFECT_BUDGET_BLOCKED"
            or protocol["scope"]["model_fits_authorized"] != 0
            or protocol["budget"]["common_valid_token_cap"] != EXPECTED_COUNTS["combined_valid_tokens"]):
        raise ValueError("protocol_scope_or_budget_mismatch")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if any(config[key] != value for key, value in ENCODER_CONFIG.items()):
        raise ValueError("encoder_config_drift")

    local = tuple(project_pairs(TRAIN.read_text(encoding="utf-8")))
    all_global = tuple(project_pairs(GLOBAL.read_text(encoding="utf-8")))
    grouped = json.loads(CARDS.read_text(encoding="utf-8"))
    global_pairs, runs, tasks = _project_candidate_pairs(grouped, local, all_global)
    local_ids = {card_id for pair in local for card_id in pair}
    global_ids = {card_id for pair in global_pairs for card_id in pair}
    needed = local_ids | global_ids
    if (len(local) != EXPECTED_COUNTS["local_pairs"]
            or len(global_pairs) != EXPECTED_COUNTS["global_pairs"]
            or len(local_ids) != EXPECTED_COUNTS["local_endpoints"]
            or len(global_ids - local_ids) != EXPECTED_COUNTS["additional_global_endpoints"]):
        raise ValueError("historical_identity_count_mismatch")
    code, retained_tasks, retained_runs, _ = extract_train_inputs(grouped, needed)
    del grouped, runs, tasks

    stage_path = output / "stage.json"
    stage_path.write_text(json.dumps({"stage": "offline_tokenizer_and_encoder"}))
    import importlib.util
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(1)
    if torch.cuda.is_initialized():
        raise ValueError("cuda_context_forbidden")
    tokenizer = AutoTokenizer.from_pretrained(
        str(MODEL), local_files_only=True, trust_remote_code=False
    )
    tokenizer.model_max_length = 10**9
    spec = importlib.util.spec_from_file_location("bound_token_plan_pairs", SOURCE)
    source_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = source_module
    spec.loader.exec_module(source_module)
    encoder = source_module.CardEncoder(code, retained_tasks, tokenizer, **ENCODER_CONFIG)

    tokenizer_files = tuple(MODEL / name for name in (
        "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "config.json"
    ))
    tokenizer_binding = _binding_digest(tokenizer_files)
    serialization_binding = digest_records([{
        "encoder_source_sha256": EXPECTED[SOURCE],
        "encoder_config": ENCODER_CONFIG,
        "template": "# MLE-bench task: {task}\\n{code}",
    }])
    encoder_binding = EncoderBinding(tokenizer_binding, serialization_binding, ENCODER_CONFIG["max_len"])
    endpoint = {}
    contexts = {}
    truncated = 0
    stage_path.write_text(json.dumps({"stage": "encode_bound_historical_endpoints"}))
    for index, card_id in enumerate(sorted(needed)):
        if time.monotonic() - started > limit_seconds:
            raise TimeoutError("bounded_token_plan_expired")
        independent, raw_tokens = independent_encode(
            code[card_id], retained_tasks[card_id], tokenizer, **{
                "max_len": ENCODER_CONFIG["max_len"],
                "head_frac": ENCODER_CONFIG["head_frac"],
            }
        )
        actual = tuple(encoder(card_id))
        if actual != independent or tuple(encoder(card_id, 19)) != actual:
            raise ValueError("source_reference_or_disabled_budget_mismatch")
        truncated += raw_tokens > ENCODER_CONFIG["max_len"]
        endpoint[card_id] = Endpoint(card_id, len(actual), encoding_digest(actual))
        contexts[card_id] = digest_records([(
            serialization_binding, retained_tasks[card_id]
        )])
        if index % 250 == 0:
            (output / "progress.json").write_text(json.dumps({
                "endpoints_done": index + 1, "endpoints_total": len(needed)
            }))

    def make_rows(source, pairs):
        result = []
        for left, right in pairs:
            if (retained_tasks[left] != retained_tasks[right]
                    or contexts[left] != contexts[right]
                    or retained_runs[left] is None or retained_runs[right] is None):
                raise ValueError("pair_context_or_run_mismatch")
            result.append(Pair.canonical(
                source, endpoint[left], endpoint[right], contexts[left]
            ))
        return tuple(result)

    g_rows = make_rows("G", global_pairs)
    l_rows = make_rows("L", local)
    if {row.key for row in g_rows} & {row.key for row in l_rows}:
        raise ValueError("cross_source_pair_overlap")
    if sum(row.valid_tokens for row in g_rows + l_rows) != EXPECTED_COUNTS["combined_valid_tokens"]:
        raise ValueError("combined_token_count_mismatch")

    stage_path.write_text(json.dumps({"stage": "build_and_independently_replay_plans"}))
    plan_rows = []
    relation_rows = []
    verification_rows = []
    for shape in (BatchShape(2, 8, 8), BatchShape(4, 8, 4)):
        for seed in (6, 7, 8):
            current = {}
            for arm in ARMS:
                value = build_plan(
                    arm, g_rows, l_rows, seed=seed, shape=shape,
                    encoder=encoder_binding, protocol_sha256=protocol_sha,
                    token_cap=EXPECTED_COUNTS["combined_valid_tokens"],
                )
                verified = verify_plan(value, g_rows, l_rows)
                current[arm] = value
                item = value.summary()
                item["world_size"] = shape.world_size
                item["pairs_per_rank"] = shape.pairs_per_rank
                item["maximum_accumulation_microsteps"] = shape.accumulation
                item["segment_receipts"] = [
                    {
                        "source": segment.source,
                        "cycle": segment.cycle,
                        "optimizer_updates": segment.stop_optimizer_step - segment.start_optimizer_step,
                        "pair_visits": segment.pair_visits,
                        "valid_tokens": segment.valid_tokens,
                    }
                    for segment in value.segments
                ]
                plan_rows.append(item)
                verification_rows.append(verified)
            relation = verify_arm_relations(
                current["L1"], current["Lbudget"],
                current["G_to_L"], current["Ghash_to_L"],
            )
            relation.update({"world_size": shape.world_size, "seed": seed})
            relation_rows.append(relation)
            del current

    if torch.cuda.is_initialized() or denied:
        raise ValueError("scope_violation")
    result = {
        "status": "PASS_HISTORICAL_TOKEN_PLAN_READINESS_EFFECT_BLOCKED",
        "protocol_sha256": protocol_sha,
        "frozen_v2_sha256": FROZEN_SHA256,
        "input_bindings": {
            "local_train_sha256": EXPECTED[TRAIN],
            "global_source_sha256": GLOBAL_SHA,
            "grouped_cards_sha256": EXPECTED[CARDS],
            "encoder_source_sha256": EXPECTED[SOURCE],
            "resolved_config_sha256": EXPECTED[CONFIG],
            "tokenizer_binding_sha256": tokenizer_binding,
            "serialization_binding_sha256": serialization_binding,
        },
        "identity_counts": {
            "local_pairs": len(l_rows),
            "global_candidate_pairs": len(g_rows),
            "combined_pairs_once": len(g_rows) + len(l_rows),
            "local_endpoints": len(local_ids),
            "global_endpoints": len(global_ids),
            "additional_global_endpoints": len(global_ids - local_ids),
            "combined_endpoints": len(needed),
            "local_grouped_runs": len({retained_runs[card_id] for card_id in local_ids}),
            "global_grouped_runs": len({retained_runs[card_id] for card_id in global_ids}),
            "tasks": len({retained_tasks[card_id] for card_id in needed}),
        },
        "token_counts": {
            "global_once": sum(row.valid_tokens for row in g_rows),
            "local_once": sum(row.valid_tokens for row in l_rows),
            "combined_once": sum(row.valid_tokens for row in g_rows + l_rows),
            "warmup": (EXPECTED_COUNTS["combined_valid_tokens"] * 3 + 99) // 100,
            "unique_endpoints_truncated": truncated,
        },
        "plans": plan_rows,
        "cross_arm_relations": relation_rows,
        "independent_replays": verification_rows,
        "source_hashes": {
            "planner_sha256": checked_digest(Path(__file__).with_name("global_local_token_budget_plan.py")),
            "verifier_sha256": checked_digest(Path(__file__).with_name("verify_global_local_token_budget_plan.py")),
            "runner_sha256": checked_digest(Path(__file__)),
        },
        "data_open_counts": dict(opened),
        "denied_attempts": dict(denied),
        "new_train_pool_created": False,
        "candidate_global_effect_eligible": False,
        "real_HF_Trainer_DeepSpeed_bf16_integrated": False,
        "model_weights_loaded": 0,
        "model_fits": 0,
        "gpu_jobs": 0,
        "api_calls": 0,
        "dev_test_vault_files_opened": 0,
        "output_contains_card_ids_code_tasks_labels_predictions_or_effects": False,
        "wall_seconds_not_throughput_benchmark": time.monotonic() - started,
    }
    for path, expected in EXPECTED.items():
        checked_digest(path, expected)
    checked_digest(GLOBAL, GLOBAL_SHA)
    checked_digest(protocol_path, expected_protocol_sha)
    checked_digest(frozen_path, FROZEN_SHA256)
    (output / "summary.json").write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    stage_path.write_text(json.dumps({"stage": "completed"}))
    print(json.dumps({
        "status": result["status"],
        "plans": len(plan_rows),
        "independent_replays": len(verification_rows),
        "combined_pairs_once": result["identity_counts"]["combined_pairs_once"],
        "combined_valid_tokens": result["token_counts"]["combined_once"],
        "model_fits": 0,
        "gpu_jobs": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--frozen-v2", required=True, type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    parser.add_argument("--limit-seconds", type=int, default=1200)
    args = parser.parse_args()
    if not 1 <= args.limit_seconds <= 1200:
        raise SystemExit("bounded_runtime_required")
    try:
        run(
            args.output_root.resolve(), args.protocol.resolve(), args.frozen_v2.resolve(),
            args.expect_protocol_sha256, args.limit_seconds,
        )
    except Exception as exc:
        print(json.dumps({
            "status": "FAILED_CLOSED",
            "exception_type": type(exc).__name__,
            "safe_reason": str(exc) if str(exc) in {
                "credential_shape_hit_no_content_disclosed",
                "immutable_asset_hash_mismatch",
                "offline_no_subprocess_contract",
                "forbidden_data_or_weights",
                "unlisted_research_data",
                "write_outside_output",
            } else "details_withheld",
        }, sort_keys=True), flush=True)
        raise SystemExit(1)

