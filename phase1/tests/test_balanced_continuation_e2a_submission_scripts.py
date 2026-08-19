from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def script(name: str) -> str:
    return (ROOT / "phase1" / "scripts" / name).read_text(encoding="utf-8")


def test_warm_smoke_uses_two_qos_safe_chunks_and_monitor_owned_submission() -> None:
    launcher = script("launch_balanced_continuation_e2a_warm_smoke_20260819.sh")
    monitor = script("monitor_balanced_continuation_e2a_warm_smoke_20260819.sh")
    assert "sbatch " not in launcher
    assert 'chunks=("0,1,2,3" "4,5")' in monitor
    assert "MAX_SUBMITTED_TASKS=4" in monitor
    assert '--array="$indices"' in monitor
    assert "%4" not in monitor
    assert 'export_spec="ALL' not in monitor


def test_formal_monitor_chunks_every_frozen_wave_without_dependency_or_all_env() -> None:
    monitor = script("monitor_balanced_continuation_e2a_20260819.sh")
    assert "MAX_SUBMITTED_TASKS=4" in monitor
    assert 'chunk_items=("${indices[@]:offset:MAX_SUBMITTED_TASKS}")' in monitor
    assert '--array="$indices"' in monitor
    assert "--dependency" not in monitor
    assert "%4" not in monitor
    assert 'export_spec="ALL' not in monitor
    assert "sealed_values_opened=false" in monitor
