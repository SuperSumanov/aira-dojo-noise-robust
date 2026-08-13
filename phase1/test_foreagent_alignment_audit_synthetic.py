"""End-to-end synthetic test for the frozen FOREAGENT alignment audit."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="foreagent_audit_test_") as raw_tmp:
        root = Path(raw_tmp)
        files = []
        for task_index in range(26):
            task = f"task-{task_index:02d}"
            for model in ("deepseek", "gpt"):
                for release_run in (1, 2, 3):
                    files.append(
                        {
                            "task": task,
                            "model_family": model,
                            "model_token": "deepseek-reasoner" if model == "deepseek" else "gpt-5_1",
                            "temperature_token": "1p0",
                            "timestamp": f"2026010{release_run}_000000",
                            "path": f"fake/{task}/{model}/{release_run}.json",
                            "size": 1,
                            "oid": f"oid-{task}-{model}-{release_run}",
                            "release_run": release_run,
                        }
                    )
        manifest = {
            "schema_version": 1,
            "source": {"repo_id": "synthetic/test", "revision": "frozen", "root": "fake"},
            "file_count": len(files),
            "files": files,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

        master_path = root / "master.jsonl"
        with master_path.open("w", encoding="utf-8") as handle:
            for source_index, source in enumerate(files):
                for pair_index in range(80):
                    gap = (pair_index + 1) / 1000.0
                    paths = [f"solution-{pair_index:03d}-a.py", f"solution-{pair_index:03d}-b.py"]
                    if pair_index % 2 == 0:
                        scores = [0.5 + gap, 0.5]
                        true_index = 0
                    else:
                        scores = [0.5, 0.5 + gap]
                        true_index = 1
                    quartile = pair_index // 20
                    if quartile == 0:
                        is_correct = (pair_index + source["release_run"]) % 2 == 0
                    elif quartile == 1:
                        is_correct = (pair_index + source["release_run"]) % 3 != 0
                    elif quartile == 2:
                        is_correct = (pair_index + source["release_run"]) % 5 != 0
                    else:
                        is_correct = True
                    predicted_index = true_index if is_correct else 1 - true_index
                    row = {
                        "source_index": source_index,
                        "task": source["task"],
                        "model_family": source["model_family"],
                        "release_run": source["release_run"],
                        "ordinal": pair_index,
                        "log_index": None if source["release_run"] == 1 else pair_index,
                        "solution_paths": paths,
                        "scores": scores,
                        "is_lower_better": False,
                        "groundtruth_best_index": true_index,
                        "prediction_best_index": predicted_index,
                        "confidence": 0.5 if quartile == 0 else 0.8,
                        "release_correct": "correct" if is_correct else "false",
                    }
                    handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

        log_path = root / "download_log.json"
        log = {
            "manifest_sha256": sha256(manifest_path),
            "master": {"sha256": sha256(master_path)},
        }
        log_path.write_text(json.dumps(log, sort_keys=True) + "\n", encoding="utf-8")
        out_dir = root / "out"
        subprocess.run(
            [
                sys.executable,
                str(HERE / "audit_foreagent_alignments.py"),
                "--manifest",
                str(manifest_path),
                "--download-log",
                str(log_path),
                "--master",
                str(master_path),
                "--out-dir",
                str(out_dir),
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(HERE / "verify_foreagent_alignment_audit.py"),
                "--manifest",
                str(manifest_path),
                "--master",
                str(master_path),
                "--summary",
                str(out_dir / "summary.json"),
            ],
            check=True,
        )
        summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
        if summary["primary_gate"]["decision"] != "LOCAL-DIFFICULTY-CONFIRMED":
            raise RuntimeError(f"unexpected synthetic decision: {summary['primary_gate']['decision']}")
        print("FOREAGENT_ALIGNMENT_SYNTHETIC_E2E_PASS")


if __name__ == "__main__":
    main()
