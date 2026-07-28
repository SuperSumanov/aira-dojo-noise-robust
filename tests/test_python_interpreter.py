from __future__ import annotations

from pathlib import Path

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
