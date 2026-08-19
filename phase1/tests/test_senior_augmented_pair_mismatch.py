import hashlib
import json
from argparse import Namespace
from pathlib import Path

from phase1.audit_senior_augmented_pair_mismatch import run, sha256_file
from phase1.verify_senior_augmented_pair_mismatch import verify


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def test_pair_mismatch_round_trip(tmp_path: Path) -> None:
    runs = []
    for index, config in enumerate(("a", "a", "b", "b"), 1):
        runs.append({
            "cards": 1, "config_sha256": _sha(config), "curve_order_sha256": _sha(f"c{index}"),
            "dev_order_sha256": _sha(f"d{index}"), "original_hold": False, "role": "train",
            "run_id": f"user_issue_task-4seeds_seed_{index}_id_{index:040x}__2026-08-01", "task": "task",
        })
    pairs = []
    specs = ((0, 1), (0, 2), (1, 3))
    for number, (left, right) in enumerate(specs):
        pairs.append({
            "original_split": "train", "pair_key_sha256": _sha(f"p{number}"),
            "run_ids": sorted([runs[left]["run_id"], runs[right]["run_id"]]),
            "same_experiment_contract": runs[left]["config_sha256"] == runs[right]["config_sha256"], "task": "task",
        })
    run_path, pair_path, support_path = tmp_path / "runs.jsonl", tmp_path / "pairs.jsonl", tmp_path / "support.json"
    run_path.write_text("".join(json.dumps(row) + "\n" for row in runs), encoding="utf-8")
    pair_path.write_text("".join(json.dumps(row) + "\n" for row in pairs), encoding="utf-8")
    support_path.write_text(json.dumps({"inventory": {"full_train_pairs": 9001}, "status": "FROZEN"}), encoding="utf-8")
    # The protocol deliberately hard-locks the formal count; repeat a valid pair under unique IDs.
    base = pairs[-1]
    with pair_path.open("a", encoding="utf-8") as handle:
        for number in range(3, 9001):
            row = dict(base, pair_key_sha256=_sha(f"p{number}"))
            handle.write(json.dumps(row) + "\n")
    out = tmp_path / "out"
    args = Namespace(
        run_manifest=str(run_path), expect_run_manifest_sha256=sha256_file(run_path),
        pair_structure=str(pair_path), expect_pair_structure_sha256=sha256_file(pair_path),
        support_summary=str(support_path), expect_support_summary_sha256=sha256_file(support_path),
        source_commit="0" * 40, output=str(out),
    )
    assert run(args) == 0
    result = verify(Namespace(
        artifact=str(out), run_manifest=str(run_path), pair_structure=str(pair_path),
        support_summary=str(support_path), output=str(tmp_path / "unused.json"),
    ))
    assert result["status"] == "INDEPENDENT_PAIR_MISMATCH_ARTIFACT_VERIFIED"
    assert result["attribution"] == "BATCH_CONTENT_MIXING_LIKELY"
    assert result["mismatch_pairs"] == 9000
