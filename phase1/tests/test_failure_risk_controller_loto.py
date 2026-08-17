from __future__ import annotations

from phase1.failure_risk_controller_loto import evaluate_pairs, summarize, truncate_code


def test_truncate_code_uses_fixed_head_tail_contract() -> None:
    code = "a" * 5_001 + "b" * 15_001
    truncated = truncate_code(code)
    assert len(truncated) == 20_000
    assert truncated == code[:5_000] + code[-15_000:]


def test_synthetic_loto_lexical_signal_beats_equal_length_baseline() -> None:
    pairs = []
    for task_index in range(3):
        for pair_index in range(4):
            pairs.append(
                {
                    "task": f"task-{task_index}",
                    "run_id": f"run-{task_index}-{pair_index}",
                    "success_code": "SAFE_OK token token",
                    "failure_code": "BROKEN! token token",
                }
            )
    rows = evaluate_pairs(pairs)
    result = summarize(rows)
    assert result["tfidf_micro_accuracy"] == 1.0
    assert result["length_micro_accuracy"] in {0.0, 0.5, 1.0}
    assert all("code" not in row for row in result["per_task"].values())
