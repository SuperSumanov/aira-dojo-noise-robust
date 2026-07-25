# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POOL_LAUNCHER_TYPES = {"srun_pool", "local_gpu_pool"}


def find_pool_manifests(meta_experiment_dir: str | Path) -> list[Path]:
    root = Path(meta_experiment_dir).expanduser().resolve()
    manifests: set[Path] = set()
    for launcher_type in POOL_LAUNCHER_TYPES:
        manifests.update(root.glob(f"{launcher_type}/*/manifest.json"))
        manifests.update(root.glob(f"**/{launcher_type}/*/manifest.json"))
    return sorted(manifests)


def load_pool_manifests(meta_experiment_dir: str | Path) -> list[dict[str, Any]]:
    manifests = []
    for path in find_pool_manifests(meta_experiment_dir):
        with path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
        if manifest.get("launcher_type") not in POOL_LAUNCHER_TYPES or not isinstance(
            manifest.get("tasks"), dict
        ):
            continue
        manifest["manifest_path"] = str(path)
        manifests.append(manifest)
    return manifests


def get_pool_tasks(meta_experiment_dir: str | Path) -> list[dict[str, Any]]:
    tasks = []
    for manifest in load_pool_manifests(meta_experiment_dir):
        launcher_type = manifest["launcher_type"]
        allocation_nodes = {
            item.get("allocation_id", ""): item.get("node_list", "")
            for item in manifest.get("allocations", [])
        }
        for run_id, task in manifest["tasks"].items():
            step_id = task.get("step_id", "")
            allocation_id = step_id.partition(".")[0] if "." in step_id else ""
            allocation_id = allocation_id or manifest.get("allocation_id", "")
            tasks.append(
                {
                    **task,
                    "run_id": run_id,
                    "allocation_id": allocation_id,
                    "node_list": allocation_nodes.get(
                        allocation_id,
                        manifest.get("node_list", manifest.get("host", "")),
                    ),
                    "launcher_type": launcher_type,
                    "execution_id": task.get("execution_id", ""),
                    "manifest_path": manifest["manifest_path"],
                }
            )
    return tasks


def find_srun_pool_manifests(meta_experiment_dir: str | Path) -> list[Path]:
    """Backward-compatible srun-only manifest finder."""
    return [
        path
        for path in find_pool_manifests(meta_experiment_dir)
        if "srun_pool" in path.parts
    ]


def load_srun_pool_manifests(meta_experiment_dir: str | Path) -> list[dict[str, Any]]:
    """Backward-compatible srun-only manifest loader."""
    return [
        manifest
        for manifest in load_pool_manifests(meta_experiment_dir)
        if manifest.get("launcher_type") == "srun_pool"
    ]


def get_srun_pool_tasks(meta_experiment_dir: str | Path) -> list[dict[str, Any]]:
    """Backward-compatible srun-only task reader."""
    return [
        task
        for task in get_pool_tasks(meta_experiment_dir)
        if task.get("launcher_type") == "srun_pool"
    ]
