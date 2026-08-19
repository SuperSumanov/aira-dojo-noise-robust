from __future__ import annotations

from phase1 import probe_balanced_client_providers as probe


def test_provider_matrix_is_exact_and_has_unique_key_names() -> None:
    assert [row[0] for row in probe.PROVIDERS] == [
        "deepseek-v4-flash",
        "qwen3-coder-flash",
        "glm-5",
    ]
    assert len({row[1] for row in probe.PROVIDERS}) == 2
    assert len({row[2] for row in probe.PROVIDERS}) == 3
    assert all(row[1].startswith("https://") and row[1].endswith("/chat/completions") for row in probe.PROVIDERS)
