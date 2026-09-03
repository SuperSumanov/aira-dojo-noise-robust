import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "phase1" / "results" / "global_local_partial_ddp_20260904"
SUMMARY_SHA = "bf488388f8115633862c6cfffae393908b3a4cada3aea7004ec11c26cc60476a"


def test_partial_ddp_summary_is_exact_and_scope_limited():
    raw = (RESULT / "summary.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SUMMARY_SHA
    value = json.loads(raw)
    assert value["status"] == "PASS_SYNTHETIC_PARTIAL_DDP_GLOO_NOT_RESEARCH_FIT"
    assert value["synthetic_source_counts"] == {"G": 176, "L": 209}
    assert value["matching_real_terminal_remainders"] == {"G": 48, "L": 81}
    assert value["distributed_trajectories"] == 16
    assert value["global_optimizer_updates"] == 48
    assert value["all_rank_forward_calls"] == 612
    assert value["partial_loss_normalization_matches_full_update_reference"] is True
    assert value["G_and_Ghash_input_trace_identical"] is True
    assert value["research_model_fits"] == value["api_calls"] == 0
    assert value["real_data_opened"] is value["gpu_context_created"] is False
    assert value["real_HF_Trainer_DeepSpeed_bf16_verified"] is False


def test_independent_receipt_covers_all_rank_resume_cases():
    value = json.loads((RESULT / "independent_receipt.json").read_text())
    assert value["status"] == "PASS_INDEPENDENT_PARTIAL_DDP_SAVED_STATE"
    assert value["summary_sha256"] == SUMMARY_SHA
    assert value["partial_loss_reference_checks"] == 4
    assert {(row["world"], row["arm"], row["verified_ranks"]) for row in value["resume_cases"]} == {
        (2, "G_to_L", 2), (2, "Ghash_to_L", 2),
        (4, "G_to_L", 4), (4, "Ghash_to_L", 4),
    }
    assert all(row["complete_state_bitwise_equal"] and row["event_prefix_equal"]
               for row in value["resume_cases"])


def test_three_saved_state_faults_are_rejected():
    value = json.loads((RESULT / "fault_receipt.json").read_text())
    assert value["status"] == "PASS_FAULTS_REJECTED"
    assert {row["case"] for row in value["cases"]} == {
        "missing-rank", "corrupt-rank", "manifest-rank-missing"
    }
    assert all(row["rejected"] for row in value["cases"])

