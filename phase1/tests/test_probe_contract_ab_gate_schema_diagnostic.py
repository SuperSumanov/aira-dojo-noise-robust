import json
from pathlib import Path

from phase1.probe_contract_ab_gate_schema_diagnostic import build


def test_schema_diagnostic_changes_only_gate_label(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("generation_manifest.json", "replay_manifest.audit.json"):
        (source / name).write_text("{}\n", encoding="utf-8")
    (source / "replay_manifest.jsonl").write_text("{}\n", encoding="utf-8")
    (source / "replay").mkdir()
    (source / "status").mkdir()
    primary = {
        "version": "v2",
        "schema_version": 2,
        "gates": {"quality_pairs_at_least_3": True, "K0": False},
        "summary": {"paired_full_scores": 4, "coverage_gain": 0},
    }
    (source / "probe_contract_ab_result.json").write_text(
        json.dumps(primary) + "\n", encoding="utf-8"
    )

    diagnostic = tmp_path / "diagnostic"
    receipt = build(source, diagnostic)
    corrected = json.loads((diagnostic / "probe_contract_ab_result.json").read_text())

    assert receipt["formal_experiment_status"] == "INVALID_INDEPENDENT_VERIFIER"
    assert corrected["gates"] == {"quality_pairs_at_least_4": True, "K0": False}
    assert corrected["summary"] == primary["summary"]
    assert corrected["postoutcome_diagnostic"]["scientific_scalars_changed"] is False
    for name in (
        "generation_manifest.json",
        "replay_manifest.audit.json",
        "replay_manifest.jsonl",
        "replay",
        "status",
    ):
        assert (diagnostic / name).exists()
