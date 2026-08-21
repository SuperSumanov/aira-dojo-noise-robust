import csv
import json
from pathlib import Path

from phase1 import audit_source_choice_oof_exact_sign as audit


def test_mathematical_zero_is_not_misclassified(tmp_path: Path):
    predictions = tmp_path / "predictions.csv"
    fields = [
        "split", "fold", "arm", "group_id", "task", "run_id_sha256", "source_size",
        "selected_candidate_sha256", "hit", "winner_rank",
    ]
    rows = []
    for split in ("task_loto", "run_grouped_5fold"):
        for index, hit in enumerate((1, 0, 0)):
            rows.append({
                "split": split, "fold": "0", "arm": "tfidf_pairwise_lr",
                "group_id": f"{split}-{index}", "task": "task", "run_id_sha256": "run",
                "source_size": 3, "selected_candidate_sha256": "candidate",
                "hit": hit, "winner_rank": 1 if hit else 2,
            })
    with predictions.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metric = {
        "task_macro_delta": 0.0,
        "task_clustered_delta": {"ci95": [0.0, 0.0]},
        "run_clustered_micro_delta": {"ci95": [0.0, 0.0]},
        "task_sign": {"positive": 1, "negative": 0, "zero": 0, "one_sided_p": 0.5},
    }
    summary = {
        "protocol": "source-choice-oof-tfidf-v1",
        "status": "SOURCE_CHOICE_OOF_TFIDF_COMPLETE",
        "verdict": "NO_NARROW_POSITIVE",
        "outputs": {"predictions.csv": audit.digest(predictions)},
        "census": {"groups": 3},
        "metrics": {
            "task_loto": {"tfidf_pairwise_lr": metric},
            "run_grouped_5fold": {"tfidf_pairwise_lr": metric},
        },
        "gate": {
            "minimum_absolute_task_macro_delta": 0.03,
            "maximum_one_sided_task_sign_p": 0.05,
        },
    }
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
    result = audit.audit(summary_path, predictions)
    assert result["split_audits"]["task_loto"]["exact"]["zero"] == 1
    assert result["split_audits"]["task_loto"]["counts_match"] is False
    assert result["exact_sign_verdict"] == "NO_NARROW_POSITIVE"
    assert result["verdict_unchanged"] is True
