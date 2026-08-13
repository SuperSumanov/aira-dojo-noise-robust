from __future__ import annotations

import ast
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path


LOCAL_MODULE_PATH = Path(__file__).with_name(".codex_scoreable_prediction_tap.py")
REPO_MODULE_PATH = Path(__file__).parent.parent / "scoreable_prediction_tap.py"
MODULE_PATH = LOCAL_MODULE_PATH if LOCAL_MODULE_PATH.is_file() else REPO_MODULE_PATH
SPEC = importlib.util.spec_from_file_location("codex_spt_transform", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
instrument = MODULE.instrument


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_preservation_and_future_import() -> None:
    source = (
        '\"\"\"doc\"\"\"\n'
        "from __future__ import annotations\n"
        "# keep this exact comment\n"
        "a = model.predict(X_val)\n"
        "b = model.predict_proba(X_test)[:, 1]\n"
    )
    output, audit = instrument(source)
    ast.parse(output)
    assert audit["site_count"] == 1
    assert "model.predict(X_val)" in output
    assert "# keep this exact comment" in output
    assert output.index("from __future__ import annotations") < output.index(
        "from scoreable_prediction_tap_runtime"
    )
    assert "__spt_capture__((model.predict_proba(X_test))" in output


def test_runtime_is_identity_and_full_output_is_equal(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "sample_submission.csv").write_text("id,target\na,0.5\nb,0.5\n", encoding="utf-8")
    source = (
        "import numpy as np\n"
        "import pandas as pd\n"
        "class M:\n"
        " def predict_proba(self, value):\n"
        "  return value\n"
        "X_test = np.array([[0.8,0.2],[0.1,0.9]])\n"
        "pred = M().predict_proba(X_test)[:, 1]\n"
        "pd.DataFrame({'id':['a','b'],'target':pred}).to_csv('submission.csv',index=False)\n"
    )
    original = tmp_path / "original"
    tapped = tmp_path / "tapped"
    original.mkdir()
    tapped.mkdir()
    (original / "solution.py").write_text(source, encoding="utf-8")
    output, audit = instrument(source)
    assert audit["site_count"] == 1
    (tapped / "solution.py").write_text(output, encoding="utf-8")
    local_runtime = Path(__file__).with_name(".codex_scoreable_prediction_tap_runtime.py")
    repo_runtime = Path(__file__).parent.parent / "scoreable_prediction_tap_runtime.py"
    runtime_source = local_runtime if local_runtime.is_file() else repo_runtime
    (tapped / "scoreable_prediction_tap_runtime.py").write_bytes(runtime_source.read_bytes())
    for root in (original, tapped):
        (root / "data").mkdir()
        (root / "data" / "sample_submission.csv").write_bytes(
            (data / "sample_submission.csv").read_bytes()
        )
        completed = subprocess.run(
            [sys.executable, "solution.py"], cwd=root, capture_output=True, text=True, check=False
        )
        assert completed.returncode == 0, completed.stderr
    assert sha(original / "submission.csv") == sha(tapped / "submission.csv")
    assert (tapped / "candidate_probe.csv").is_file(), (completed.stdout, completed.stderr, output)
    assert not (original / "candidate_probe.csv").exists()


def test_validation_prediction_only_abstains() -> None:
    source = "prediction = model.predict(X_val)\n"
    try:
        instrument(source)
    except RuntimeError as error:
        assert "no precision-qualified" in str(error)
    else:
        raise AssertionError("validation-only prediction must abstain")


def test_string_literal_does_not_fake_test_facing_argument() -> None:
    source = "prediction = model.predict(frame['contest_feature'])\n"
    try:
        instrument(source)
    except RuntimeError as error:
        assert "no precision-qualified" in str(error)
    else:
        raise AssertionError("a string key containing 'test' must not qualify by itself")


def test_reserved_wrapper_name_abstains() -> None:
    source = "__spt_capture__ = None\nprediction = model.predict(X_test)\n"
    try:
        instrument(source)
    except RuntimeError as error:
        assert "reserved instrumentation name" in str(error)
    else:
        raise AssertionError("instrumentation namespace collision must fail closed")
