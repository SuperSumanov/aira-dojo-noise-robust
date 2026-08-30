from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

from phase1 import audit_foreagent_pair_graph_linear_rank as producer
from phase1 import verify_foreagent_pair_graph_linear_rank as verifier


SOURCE_SHA = producer.SOURCE_SHA256
ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_foreagent_pair_graph_linear_rank_formal_20260830.sh"
PROTOCOL = ROOT / "phase1/foreagent_pair_graph_linear_rank_addendum_v1.json"


def path(task: str, name: str) -> str:
    return f"root/solutions_subset_50/{task}/{name}.py"


def rows() -> list[dict]:
    a, b, c = (path("task-a", name) for name in ("a", "b", "c"))
    d, e = (path("task-b", name) for name in ("d", "e"))
    return [
        {"paths": [a, b]},
        {"paths": [b, c]},
        {"paths": [a, c]},
        {"paths": [d, e]},
    ]


def test_triangle_plus_edge_has_exact_incidence_rank() -> None:
    result = producer.summarize(rows(), SOURCE_SHA)
    assert result["pair_rows"] == 4
    assert result["vertices"] == 5
    assert result["connected_components"] == 2
    assert result["endpoint_edge_incidence_rank"] == 3
    assert result["cycle_redundant_pair_rows"] == 1
    assert result["pair_rows_per_incidence_rank"] == {
        "numerator": 4,
        "denominator": 3,
        "decimal_17g": format(4 / 3, ".17g"),
    }
    assert result["scope"]["scores_or_predictions_read"] is False


def test_independent_dfs_reconstruction_is_byte_equivalent() -> None:
    assert verifier.reconstruct(rows(), SOURCE_SHA) == producer.summarize(rows(), SOURCE_SHA)


def test_duplicate_or_cross_task_edges_fail_closed() -> None:
    duplicate = rows() + [copy.deepcopy(rows()[0])]
    with pytest.raises(ValueError, match="duplicate"):
        producer.summarize(duplicate, SOURCE_SHA)
    cross = rows()
    cross[0] = {"paths": [path("task-a", "a"), path("task-b", "d")]}
    with pytest.raises(ValueError, match="cross-task"):
        producer.summarize(cross, SOURCE_SHA)


def test_schema_or_source_drift_fails_closed() -> None:
    changed = rows()
    changed[0]["score"] = 1.0
    with pytest.raises(ValueError, match="schema"):
        producer.summarize(changed, SOURCE_SHA)
    with pytest.raises(ValueError, match="source SHA"):
        producer.summarize(rows(), "x" * 64)


def test_public_result_emits_no_solution_or_task_identities() -> None:
    result = producer.summarize(rows(), SOURCE_SHA)
    rendered = producer.canonical_bytes(result).decode()
    for forbidden in ("task-a", "task-b", "/a.py", "/b.py", "/c.py", "/d.py", "/e.py"):
        assert forbidden not in rendered


def test_runner_is_hash_bound_repeated_traced_and_cpu_only() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    if os.name != "nt":
        subprocess.run(["bash", "-n", str(RUNNER)], check=True, capture_output=True)
    assert "if [[ $# -ne 7 ]]" in source
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", source)) == 13
    assert "result_a.json" in source and "result_b.json" in source
    assert "verification_a.json" in source and "verification_b.json" in source
    assert 'cmp "$output/result_a.json" "$output/result_b.json"' in source
    assert 'cmp "$output/verification_a.json" "$output/verification_b.json"' in source
    assert 'timeout 1800s "$python_bin" -m pytest -q phase1/tests' in source
    assert "strace -ff -tt -yy -e trace=file,network" in source
    assert "gpu_paid_api_model_fit_base_update=0/0/0/0" in source
    assert "sbatch" not in source and "nvidia-smi" not in source


def test_protocol_binds_every_runtime_source() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    assert protocol["status"] == "POSTDISCLOSURE_DESCRIPTIVE_AUDIT_NOT_PREREGISTERED_CONFIRMATION"
    for binding in protocol["source_bindings"].values():
        path = ROOT / binding["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"]
