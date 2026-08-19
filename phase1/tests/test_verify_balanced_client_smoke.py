from __future__ import annotations

import json
from pathlib import Path

import yaml

from phase1 import verify_balanced_client_smoke as verifier


COMMIT = "a" * 40


def make_config(model: str, base_url: str) -> dict:
    client = {"model_id": model, "base_url": base_url}
    return {
        "metadata": {"seed": 1401},
        "task": {"name": "spooky-author-identification"},
        "solver": {
            "step_limit": 2,
            "execution_timeout": 300,
            "time_limit_secs": 900,
            "operators": {name: {"llm": {"client": client}} for name in verifier.OPERATORS},
        },
        "logger": {"write_env_vars": False},
    }


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "run"
    root.mkdir()
    (root / "source_commit.txt").write_text(COMMIT + "\n", encoding="utf-8")
    (root / "control_commit.txt").write_text(COMMIT + "\n", encoding="utf-8")
    jobs = ["11", "12", "13"]
    (root / "submission.txt").write_text("\n".join(jobs) + "\n", encoding="utf-8")
    (root / "slurm_accounting.txt").write_text(
        "\n".join(f"{job}|COMPLETED|0:0|60|billing=6,gres/gpu=1" for job in jobs) + "\n",
        encoding="utf-8",
    )
    journal = [
        {"step": 0, "code": "print(0)", "parents": [], "children": [1]},
        {"step": 1, "code": "print(1)", "parents": [0], "children": []},
    ]
    for index, (model, base_url) in verifier.CLIENTS.items():
        config = make_config(model, base_url)
        (root / f"resolved_{index}.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        (root / f"rc_{index}.json").write_text(
            json.dumps({"array_index": index, "model": model, "rc": 0, "source_commit": COMMIT}),
            encoding="utf-8",
        )
        run_dir = root / "outputs" / model
        (run_dir / "checkpoint").mkdir(parents=True)
        (run_dir / "dojo_config.json").write_text(json.dumps(config), encoding="utf-8")
        journal_text = "\n".join(json.dumps(row) for row in journal) + "\n"
        (run_dir / "checkpoint" / "journal.jsonl").write_text(journal_text, encoding="utf-8")
        (run_dir / "checkpoint" / "state.json").write_text(
            json.dumps({"current_step": 2, "running_time": 10.0, "num_starts": 0}), encoding="utf-8"
        )
        (run_dir / f"{model}_search_data.json").write_text(
            json.dumps({"nodes": journal, "solution": "print(1)"}), encoding="utf-8"
        )
    return root


def test_verifier_accepts_complete_score_blind_smoke(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    result = verifier.verify(root, COMMIT, root / "verification.json")
    assert result["status"] == "PASS_BALANCED_CLIENT_SMOKE"
    assert result["physical_runs"] == 3
    assert result["score_fields_read"] is False


def test_verifier_rejects_environment_dump(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    (root / "outputs" / "env_variables.json").write_text("{}", encoding="utf-8")
    try:
        verifier.verify(root, COMMIT, root / "verification.json")
    except verifier.VerificationError as error:
        assert "environment dump" in str(error)
    else:
        raise AssertionError("environment dump did not fail closed")


def test_verifier_rejects_search_journal_mismatch(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    target = next((root / "outputs" / "deepseek-v4-flash").glob("*_search_data.json"))
    value = json.loads(target.read_text(encoding="utf-8"))
    value["nodes"][1]["parents"] = []
    target.write_text(json.dumps(value), encoding="utf-8")
    try:
        verifier.verify(root, COMMIT, root / "verification.json")
    except verifier.VerificationError as error:
        assert "search export/journal mismatch" in str(error)
    else:
        raise AssertionError("search mismatch did not fail closed")
