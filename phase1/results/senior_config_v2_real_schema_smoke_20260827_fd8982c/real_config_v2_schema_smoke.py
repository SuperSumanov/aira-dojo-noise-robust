from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parser = argparse.ArgumentParser()
parser.add_argument("--selection", type=Path, required=True)
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--reference-root", type=Path, required=True)
args = parser.parse_args()

sys.path.insert(0, str(args.reference_root))
import phase1.senior_experiment_config_v2 as reference
import phase1.validate_senior_experiment_config_manifest as v1

candidate = load_module("real_config_v2_candidate", args.candidate)

selection_rows = []
for line_number, line in enumerate(args.selection.read_text(encoding="utf-8").splitlines(), 1):
    parts = line.split("\t", 2)
    if len(parts) != 3:
        raise RuntimeError(f"malformed selection row {line_number}")
    mtime, size, path_value = parts
    selection_rows.append((mtime, int(size), Path(path_value)))
if len(selection_rows) != 20:
    raise RuntimeError("selection must contain exactly 20 configs")
if len({path for _, _, path in selection_rows}) != len(selection_rows):
    raise RuntimeError("selection contains duplicate paths")

raw_configs: list[tuple[Path, bytes]] = []
for _, expected_size, path in selection_rows:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("selected config is absent, non-regular, or symlinked")
    raw = path.read_bytes()
    if len(raw) != expected_size:
        raise RuntimeError("selected config size changed after metadata freeze")
    if candidate.CREDENTIAL.search(raw) or v1.CREDENTIAL.search(raw):
        raise RuntimeError("credential-shaped bytes refused before config parse")
    raw_configs.append((path, raw))

rows = []
top_level_schemas = set()
solver_fingerprints = set()
stratum_fingerprints = set()
clients = set()
tasks = set()
sidecars_before = 0
sidecars_after = 0
for path, raw in raw_configs:
    sidecars_before += int((path.parent / candidate.PER_RUN_FILENAME).exists())
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError("real dojo config root is not an object")
    task_value = value.get("task")
    task = task_value.get("name") if isinstance(task_value, dict) else None
    if not isinstance(task, str):
        raise RuntimeError("real dojo config task name is absent")
    expected = reference.make_row(
        value,
        task=task,
        generator_release="unknown",
        hardware="unknown",
    )
    observed = candidate.make_row(
        value,
        generator_release="unknown",
        hardware="unknown",
    )
    if observed != expected:
        raise RuntimeError("candidate/reference row mismatch on real config")
    if candidate.render_rows([observed]) != (
        v1.canonical_json(expected) + "\n"
    ).encode("utf-8"):
        raise RuntimeError("candidate/reference byte mismatch on real config")
    rows.append(observed)
    top_level_schemas.add(tuple(sorted(value)))
    solver_fingerprints.add(observed["resolved_solver_config_sha256"])
    stratum_fingerprints.add(observed["experiment_stratum_sha256"])
    clients.add(observed["client"])
    tasks.add(observed["task"])
    sidecars_after += int((path.parent / candidate.PER_RUN_FILENAME).exists())

canonical_rows = candidate.render_rows(rows)
summary = {
    "candidate_reference_bytes_equal": len(rows),
    "config_contents_read": len(raw_configs),
    "configs": len(rows),
    "credential_scan_before_parse": True,
    "distinct_clients": len(clients),
    "distinct_experiment_strata": len(stratum_fingerprints),
    "distinct_solver_fingerprints": len(solver_fingerprints),
    "distinct_tasks": len(tasks),
    "distinct_top_level_schemas": len(top_level_schemas),
    "generator_release_for_smoke": "unknown",
    "hardware_for_smoke": "unknown",
    "historical_only_not_provenance": True,
    "rows_sha256": hashlib.sha256(canonical_rows).hexdigest(),
    "sidecars_after": sidecars_after,
    "sidecars_before": sidecars_before,
    "sidecars_written": sidecars_after - sidecars_before,
    "status": "REAL_CONFIG_SCHEMA_COMPAT_PASS",
}
print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
