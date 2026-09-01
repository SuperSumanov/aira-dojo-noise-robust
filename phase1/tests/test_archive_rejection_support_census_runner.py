from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "phase1/scripts/run_archive_rejection_support_census_formal_20260901.sh"


def runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8")


def test_runner_has_13_item_preflight_and_exact_frozen_inputs() -> None:
    text = runner_text()
    assert len(re.findall(r"(?m)^(?:0[1-9]|1[0-3])_", text)) == 13
    for value in (
        "c14297637b7356ea617509079fa25ac1875900aae581c8450fd4135a80d409f3",
        "d2ed361a557bf52dadfe9f0547e49c16ea5dc1eea42a1c78f7b354542a2a704a",
        "f5c722af76c6eda9b47b1fb175a51373b721ee084df02c6b72f5298e8fb93cfa",
        "30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f",
        "e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d",
        "4f05659db88e290f18a20d43b33330daa5df27211b1fffb770cbf1658b46ec60",
        "fabae2e42b8e669bc0f212df5365809751966859df22cb1a0ba952ba277f7467",
        "b194b1bc88e561e77f982ae6f46d5ea7cccb745cc960c26da2661ea0ce8bad03",
        "1281797c52007f3a6f9687ded4a785f21f0cc779bb8276e9e41e4ed057587a60",
        "c95b8e0ffce0162bc65e26ce69867187f29a52184205c6c34745daa54c742080",
        "4acc607c86a2560df3036588b1d0f8898533966385551d9d5c0612bc5a64d836",
    ):
        assert value in text
    assert 'cmp "$0" "$WORKTREE/$RUNNER_REL"' in text
    assert 'rev-parse fork/phase1-value-critic' in text


def test_runner_requires_reproducible_nonimporting_reconstruction() -> None:
    text = runner_text()
    assert 'for arm in a b; do' in text
    assert 'cmp "$PUBLIC_ROOT/a/result.json" "$PUBLIC_ROOT/b/result.json"' in text
    assert (
        'cmp "$PUBLIC_ROOT/a/independent_verification.json" '
        '"$PUBLIC_ROOT/b/independent_verification.json"'
    ) in text
    assert "grep -q 'audit_archive_rejection_support_census'" in text
    assert 'readonly_receipt "$PUBLIC_ROOT/readonly_before.json"' in text
    assert 'readonly_receipt "$PUBLIC_ROOT/readonly_after.json"' in text


def test_runner_is_cpu_only_outcome_blind_and_identity_erased() -> None:
    text = runner_text()
    assert "set +u\nsource ~/env_setup.sh\nset -u" in text
    assert "PYTHON_BIN=/research/d7/spc/yzyang4/venvs/exp/bin/python" in text
    assert '"$PYTHON_BIN" -m pytest -q phase1/tests' in text
    assert 'cd "$WORKTREE"' in text
    assert '"$PYTHON_BIN" -m "$PRODUCER_MODULE"' in text
    assert '"$PYTHON_BIN" -m "$VERIFIER_MODULE"' in text
    assert '"$PYTHON_BIN" "$PRODUCER"' not in text
    assert '"$PYTHON_BIN" "$VERIFIER"' not in text
    assert "strace -f -qq -e trace=file,network" in text
    assert "gpu_api_model_fit_base_update=0/0/0/0" in text
    assert "credential_content_hits=0" in text
    assert "labels_outcomes_predictions_accuracy_utility_read=false" in text
    assert "identity-bearing schema detected" in text
    assert "sbatch" not in text
    assert "nvidia-smi" not in text
    for retired in ("multifidelity", "probe-first", "lookahead"):
        assert retired not in text.lower()


def test_runner_is_fresh_fail_closed_and_marks_complete_last() -> None:
    text = runner_text()
    assert '[[ ! -e "$FORMAL_ROOT" && ! -e "$WORKTREE" ]]' in text
    assert 'printf \'%s\\n\' "$rc" >"$PUBLIC_ROOT/FAILED_RC"' in text
    manifest = text.index('xargs -0 sha256sum >"$PUBLIC_ROOT/SHA256SUMS"')
    complete = text.index('touch "$PUBLIC_ROOT/COMPLETE"', manifest)
    readonly = text.index('chmod -R a-w "$FORMAL_ROOT"', complete)
    assert manifest < complete < readonly
