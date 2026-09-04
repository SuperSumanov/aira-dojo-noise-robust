import json
from pathlib import Path

import pytest

from phase1.g_reuse_effect_power_envelope import PowerEnvelopeError, power, run


def test_power_rises_with_effect_and_tasks():
    low = power(0.01, 0.2, 0.01, 0.5, 3, 28, 0.01, 0.95)
    high_effect = power(0.02, 0.2, 0.01, 0.5, 3, 28, 0.01, 0.95)
    high_tasks = power(0.01, 0.2, 0.01, 0.5, 3, 56, 0.01, 0.95)
    assert high_effect > low
    assert high_tasks > low


def test_power_falls_with_noise_and_correlation():
    base = power(0.02, 0.1, 0.0, 0.0, 3, 28, 0.01, 0.95)
    assert power(0.02, 0.3, 0.0, 0.0, 3, 28, 0.01, 0.95) < base
    assert power(0.02, 0.1, 0.03, 0.0, 3, 28, 0.01, 0.95) < base
    assert power(0.02, 0.1, 0.0, 1.0, 3, 28, 0.01, 0.95) < base


def test_invalid_parameters_rejected():
    with pytest.raises(PowerEnvelopeError):
        power(0.2, 0.1, 0.0, 0.0, 3, 28, 0.01, 0.95)


def test_unbound_protocol_rejected(tmp_path: Path):
    protocol = json.loads(Path("phase1/g_reuse_effect_power_protocol_v1.json").read_text(encoding="utf-8"))
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps({"metrics": {}}), encoding="utf-8")
    with pytest.raises(PowerEnvelopeError, match="not bound"):
        run(protocol_path, source_path)
