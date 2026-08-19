import json
from argparse import Namespace
from pathlib import Path

from phase1.deterministic_failure_precheck import analyze_code, sha256_file, summarize, write_json
from phase1.verify_deterministic_failure_precheck import verify


DIGEST = "0" * 64


def endpoint(parseable: bool, writers: list[str], decision: str) -> dict[str, object]:
    return {"code_sha256": DIGEST, "parseable": parseable, "writer_kinds": writers, "decision": decision}


def test_fixed_static_rule() -> None:
    assert analyze_code("def broken(:\n")["decision"] == "REJECT_SYNTAX"
    assert analyze_code("x = 1\n")["decision"] == "REJECT_NO_ARTIFACT_WRITER"
    assert analyze_code("frame.to_csv(output_path)\n") == {
        "parseable": True,
        "writer_kinds": ["to_csv"],
        "decision": "KEEP",
    }
    assert analyze_code('open("submission.csv", "w").write("x")\n')["decision"] == "KEEP"
    assert analyze_code('open("submission.csv")\n')["decision"] == "REJECT_NO_ARTIFACT_WRITER"
    assert analyze_code('Path("submission.csv").write_text("x")\n')["decision"] == "KEEP"
    assert analyze_code('Path("submission.csv").open("w")\n')["decision"] == "KEEP"


def test_anonymized_artifact_verifies(tmp_path: Path) -> None:
    rows = [
        {
            "failure": endpoint(False, [], "REJECT_SYNTAX"),
            "failure_category": "OTHER_TRACEBACK",
            "parent_key_sha256": "1" * 64,
            "run_id": "r1",
            "success": endpoint(True, ["to_csv"], "KEEP"),
            "task": "t1",
        },
        {
            "failure": endpoint(True, [], "REJECT_NO_ARTIFACT_WRITER"),
            "failure_category": "ARTIFACT_OUTPUT_CONTRACT",
            "parent_key_sha256": "2" * 64,
            "run_id": "r2",
            "success": endpoint(True, ["open"], "KEEP"),
            "task": "t2",
        },
    ]
    registry_summary = {
        "support_summary_sha256": DIGEST,
        "pair_registry_sha256": "ee7c878c9b3390c08d309229ac6380bf86e6934b92aab269e42ce7c2ffd57747",
        "inputs": {
            "cards_sha256": DIGEST,
            "status_per_child_sha256": DIGEST,
            "taxonomy_per_child_sha256": DIGEST,
            "pair_sha256": [DIGEST],
        },
    }
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    write_json(artifact / "summary.json", summarize(rows, "0" * 40, registry_summary))
    with (artifact / "pair_features.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    write_json(
        artifact / "sha256_manifest.json",
        {name: sha256_file(artifact / name) for name in ("summary.json", "pair_features.jsonl")},
    )
    result = verify(Namespace(artifact=str(artifact)))
    assert result["status"] == "INDEPENDENT_DETERMINISTIC_PRECHECK_ARTIFACT_VERIFIED"
    assert result["failure_caught"] == 2
    assert result["success_false_rejected"] == 0
