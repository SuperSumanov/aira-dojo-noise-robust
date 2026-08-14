from __future__ import annotations

import ast
from pathlib import Path


def test_capability_probe_never_opens_private_or_test_paths() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "balanced_continuation_capability_probe.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    lowered = "\n".join(string_literals).lower()
    assert "/workspace/data" in lowered
    assert "dsearch" not in lowered
    assert "dval" not in lowered
    assert "answer.csv" not in lowered
    assert "test.csv" not in lowered


def test_node_local_nvidia_fix_and_capability_precede_paid_worker() -> None:
    phase1 = Path(__file__).resolve().parents[1]
    launcher = (
        phase1 / "scripts" / "launch_balanced_continuation_e1_20260814.sh"
    ).read_text(encoding="utf-8")
    job = (phase1 / "balanced_continuation_e1_20260814.sbatch").read_text(
        encoding="utf-8"
    )
    assert "cp /usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4" not in launcher
    assert "source_nvvm=/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4" in job
    assert job.index('cp "$source_nvvm"') < job.index("singularity exec")
    assert job.index("singularity exec") < job.index(
        "phase1.balanced_continuation_real_worker"
    )
    assert 'if [[ "$capability_rc" = 0 ]]; then' in job


def test_stage_gate_requires_capability_receipts() -> None:
    phase1 = Path(__file__).resolve().parents[1]
    job = (phase1 / "balanced_continuation_e1_20260814.sbatch").read_text(
        encoding="utf-8"
    )
    monitor = (
        phase1 / "scripts" / "monitor_balanced_continuation_e1_20260814.sh"
    ).read_text(encoding="utf-8")
    assert '"capability_rc":%s' in job
    assert '"capability_rc": 0' in monitor
    assert "capability/worker/verifier/safety receipts are zero" in monitor
