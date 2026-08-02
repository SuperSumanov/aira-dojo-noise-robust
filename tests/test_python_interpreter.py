from __future__ import annotations

from pathlib import Path

import pytest

from dojo.config_dataclasses.interpreter.python import PythonInterpreterConfig
from dojo.core.interpreters.python import PythonInterpreter


def _make_interpreter(tmp_path: Path) -> PythonInterpreter:
    return PythonInterpreter(
        PythonInterpreterConfig(working_dir=str(tmp_path), timeout=10)
    )


def test_python_interpreter_executes_standard_main_guard(tmp_path: Path) -> None:
    interpreter = _make_interpreter(tmp_path)
    try:
        result = interpreter.run(
            """
from pathlib import Path

def main():
    Path("submission.csv").write_text("id,prediction\\n1,ok\\n", encoding="utf-8")
    print("main executed")

if __name__ == "__main__":
    main()
""",
            file_name="solution.py",
        )
    finally:
        interpreter.cleanup_session()

    assert result.exit_code == 0
    assert "main executed" in "".join(result.term_out)
    assert (tmp_path / "submission.csv").is_file()


def test_python_interpreter_provides_and_refreshes_script_metadata(
    tmp_path: Path,
) -> None:
    interpreter = _make_interpreter(tmp_path)
    try:
        first = interpreter.run(
            "from pathlib import Path\n"
            "saved_value = 42\n"
            "print(__name__, Path(__file__).name, __package__)",
            file_name="first.py",
        )
        second = interpreter.run(
            "print(__name__, Path(__file__).name, __package__, saved_value)",
            reset_session=False,
            file_name="second.py",
        )
    finally:
        interpreter.cleanup_session()

    assert first.exit_code == 0
    assert "__main__ first.py None" in "".join(first.term_out)
    assert second.exit_code == 0
    assert "__main__ second.py None 42" in "".join(second.term_out)


def test_python_interpreter_supports_spawn_for_user_defined_objects(
    tmp_path: Path,
) -> None:
    interpreter = _make_interpreter(tmp_path)
    try:
        result = interpreter.run(
            """
import multiprocessing

class SpawnPayload:
    def __init__(self, value):
        self.value = value

def send_payload(output):
    output.put(SpawnPayload(42))

if __name__ == "__main__":
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    child = context.Process(target=send_payload, args=(output,))
    child.start()
    payload = output.get(timeout=5)
    child.join(timeout=5)
    print("spawn-payload", payload.value, "exitcode", child.exitcode)
""",
            file_name="solution.py",
        )
    finally:
        interpreter.cleanup_session()

    assert result.exit_code == 0, "".join(result.term_out)
    assert "spawn-payload 42 exitcode 0" in "".join(result.term_out)


def test_python_interpreter_preserves_exception_messages_containing_dojo_path(
    tmp_path: Path,
) -> None:
    interpreter = _make_interpreter(tmp_path)
    message = (
        "cannot import name 'AdamW' from 'transformers' "
        "(/opt/conda/envs/aira-dojo/lib/python3.12/site-packages/transformers/__init__.py)"
    )
    try:
        result = interpreter.run(
            f"raise ImportError({message!r})",
            file_name="solution.py",
        )
    finally:
        interpreter.cleanup_session()

    output = "".join(result.term_out)
    assert result.exit_code == 1
    assert f"ImportError: {message}" in output


def test_python_interpreter_hard_timeout_returns_execution_result(
    tmp_path: Path,
) -> None:
    interpreter = PythonInterpreter(
        PythonInterpreterConfig(working_dir=str(tmp_path), timeout=0.1)
    )
    interpreter.timeout_grace_seconds = 0.1

    try:
        result = interpreter.run(
            "import signal, time\n"
            "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
            "while True:\n"
            "    time.sleep(0.01)\n",
            file_name="solution.py",
        )
    finally:
        interpreter.cleanup_session()

    assert result.exit_code == 1
    assert result.exec_time == 0.1
    assert "TimeoutError: Execution exceeded the time limit" in "".join(result.term_out)


@pytest.mark.parametrize("file_name", ["../escape.py", "/tmp/escape.py"])
def test_python_interpreter_rejects_file_name_escape(tmp_path: Path, file_name: str) -> None:
    interpreter = _make_interpreter(tmp_path)
    try:
        result = interpreter.run("print('must not execute')", file_name=file_name)
    finally:
        interpreter.cleanup_session()

    assert result.exit_code == 1
    assert "ValueError" in "".join(result.term_out)


def test_python_interpreter_fetch_file_stays_in_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("sentinel", encoding="utf-8")
    inside = tmp_path / "inside.txt"
    inside.write_text("result", encoding="utf-8")
    interpreter = _make_interpreter(tmp_path)

    assert interpreter.fetch_file(str(inside)) == str(inside.resolve())
    assert interpreter.fetch_file(str(outside)) is None
