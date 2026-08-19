from __future__ import annotations

import json
from pathlib import Path

import yaml

from phase1 import verify_balanced_client_pilot as verifier


COMMIT = "b" * 40
MODELS = (
    ("litellm_deepseek_flash", "deepseek-v4-flash", "https://api.deepseek.com"),
    ("litellm_gen2", "qwen3-coder-flash", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    ("litellm_gen3", "glm-5", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)


def manifest_rows() -> list[dict]:
    rows = []
    for client, model, base_url in MODELS:
        for task in ("spooky-author-identification", "spaceship-titanic"):
            for seed in (1402, 1403):
                rows.append({
                    "index": len(rows), "client_config": client, "model_id": model,
                    "base_url": base_url, "task": task, "seed": seed,
                })
    return rows


def config(row: dict) -> dict:
    client = {"model_id": row["model_id"], "base_url": row["base_url"]}
    return {
        "metadata": {"seed": row["seed"], "git_issue_id": verifier.issue_id(row)},
        "task": {"name": row["task"]},
        "solver": {
            "step_limit": 4, "execution_timeout": 300, "time_limit_secs": 1800,
            "operators": {name: {"llm": {"client": client}} for name in verifier.OPERATORS},
        },
        "logger": {"write_env_vars": False},
    }


def make_root(tmp_path: Path, invalidate_model: str | None = None) -> Path:
    root = tmp_path / "pilot"
    root.mkdir()
    rows = manifest_rows()
    manifest = {
        "schema_version": "balanced-client-pilot-manifest-v1",
        "tasks": ["spooky-author-identification", "spaceship-titanic"],
        "seeds": [1402, 1403], "slurm_time_limit": "02:15:00",
        "shards": [[0, 4, 8], [5, 9, 1], [10, 2, 6], [3, 7, 11]],
        "rows": rows, "step_limit": 4, "execution_timeout": 300, "run_time_limit_secs": 1800,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "source_commit.txt").write_text(COMMIT + "\n", encoding="utf-8")
    (root / "control_commit.txt").write_text(COMMIT + "\n", encoding="utf-8")
    jobs = [str(100 + index) for index in range(4)]
    (root / "submission.txt").write_text("\n".join(jobs) + "\n", encoding="utf-8")
    (root / "slurm_accounting.txt").write_text(
        "\n".join(f"{job}|COMPLETED|0:0|120|billing=6,gres/gpu=1" for job in jobs) + "\n",
        encoding="utf-8",
    )
    for row in rows:
        cfg = config(row)
        index = row["index"]
        (root / f"resolved_{index}.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
        receipt = {
            "index": index, "model": row["model_id"], "task": row["task"], "seed": row["seed"],
            "rc": 0, "source_commit": COMMIT,
        }
        (root / f"rc_{index}.json").write_text(json.dumps(receipt), encoding="utf-8")
        valid = row["model_id"] != invalidate_model
        journal = [
            {"step": 0, "code": "", "parents": [], "children": [1, 2, 3]},
            *[
                {
                    "step": step, "code": f"print({step})", "parents": [0], "children": [],
                    "is_buggy": not valid, "metric": 0.5 if valid else None,
                    "metric_info": {"valid_submission": 1.0 if valid else 0.0},
                }
                for step in (1, 2, 3)
            ],
        ]
        run_dir = root / "outputs" / str(index)
        (run_dir / "checkpoint").mkdir(parents=True)
        (run_dir / "dojo_config.json").write_text(json.dumps(cfg), encoding="utf-8")
        (run_dir / "checkpoint" / "journal.jsonl").write_text(
            "\n".join(json.dumps(node) for node in journal) + "\n", encoding="utf-8"
        )
        (run_dir / "checkpoint" / "state.json").write_text(
            json.dumps({"current_step": 4, "running_time": 100.0, "num_starts": 0}), encoding="utf-8"
        )
        (run_dir / f"{index}_search_data.json").write_text(
            json.dumps({"nodes": journal, "solution": "print(3)"}), encoding="utf-8"
        )
    return root


def test_balanced_pilot_passes_support_gate(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    result = verifier.verify(root, COMMIT, root / "verification.json")
    assert result["status"] == "GO_BALANCED_ACQUISITION"
    assert result["valid_nonroot_nodes_total"] == 36
    assert result["finite_sibling_pairs_total"] == 36
    assert result["winner_labels_computed"] is False


def test_balanced_pilot_keeps_integrity_but_fails_support(tmp_path: Path) -> None:
    root = make_root(tmp_path, invalidate_model="qwen3-coder-flash")
    result = verifier.verify(root, COMMIT, root / "verification.json")
    assert result["status"] == "INSUFFICIENT_BALANCED_PILOT_SUPPORT"
    assert result["gates"]["each_client_valid_runs_at_least_2"] is False
    assert result["gates"]["each_client_has_pair"] is False


def test_balanced_pilot_rejects_environment_dump(tmp_path: Path) -> None:
    root = make_root(tmp_path)
    (root / "outputs" / "env_variables.json").write_text("{}", encoding="utf-8")
    try:
        verifier.verify(root, COMMIT, root / "verification.json")
    except verifier.VerificationError as error:
        assert "environment dump" in str(error)
    else:
        raise AssertionError("environment dump did not fail closed")


def test_checked_in_manifest_is_exact_factorial_grid() -> None:
    manifest = json.loads(Path("phase1/balanced_client_pilot_manifest_20260819.json").read_text(encoding="utf-8"))
    rows = verifier.validate_manifest(manifest)
    assert rows == manifest_rows()


def test_pilot_uses_plain_jobs_and_fixed_resource_cap() -> None:
    launcher = Path("phase1/scripts/launch_balanced_client_pilot_20260819.sh").read_text(encoding="utf-8")
    worker = Path("phase1/scripts/balanced_client_pilot_20260819.sbatch").read_text(encoding="utf-8")
    assert "--array" not in launcher
    assert "SLURM_ARRAY_" not in worker
    assert "Slurm hard cap 9 GPU-hours" in launcher
    assert "#SBATCH --time=02:15:00" in worker
    assert "BALANCED_PILOT_SHARD" in worker
    for shard, indices in enumerate(("0 4 8", "5 9 1", "10 2 6", "3 7 11")):
        assert f'{shard}) pilot_indices="{indices}"' in worker
