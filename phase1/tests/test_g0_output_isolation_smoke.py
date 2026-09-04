from pathlib import Path

import pytest

from phase1.g0_output_isolation_smoke import worker_contract


def test_real_worker_redirects_shared_defaults_before_launcher():
    body = Path('phase1/scripts/critic_component_g0_worker_20260821.sh').read_bytes()
    assert worker_contract(body)
    assert b'$G0_RUN_ROOT/shared-env-output' in body
    assert b'$G0_RUN_ROOT/shared-env-logs' in body


def test_missing_or_late_binding_is_rejected():
    with pytest.raises(ValueError):
        worker_contract(b'/usr/bin/time -v -o "$resource_usage" bash "$launcher"')
    with pytest.raises(ValueError):
        worker_contract(b'/usr/bin/time -v -o "$resource_usage" bash "$launcher"\n'
                        b'export MLE_CRITIC_OUTPUT_DIR="$shared_env_output"\n'
                        b'export MLE_CRITIC_LOG_DIR="$shared_env_logs"\n')
