"""Executed inside the sandbox as the unprivileged command user."""
import json
import sys
from pathlib import Path


def edit(args):
    path = Path(args["path"])
    if not path.is_absolute():
        path = Path("/workspace") / path
    path = path.resolve()
    if not path.is_relative_to("/workspace"):
        raise ValueError("Editor paths must stay under /workspace")
    command = args["command"]
    if command == "create":
        with path.open("x", encoding="utf-8") as f:
            f.write(args["file_text"])
        return "Created file"
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Editor only supports files up to 2 MiB")
    text = path.read_text()
    if command == "view":
        return "\n".join(f"{i}: {line}" for i, line in enumerate(text.splitlines(), 1))[:60000]
    if command == "str_replace":
        old = args["old_str"]
        if not old or text.count(old) != 1:
            raise ValueError("old_str must match exactly once")
        text = text.replace(old, args["new_str"], 1)
    elif command == "insert":
        lines = text.splitlines(keepends=True)
        index = args["insert_line"]
        if type(index) is not int or not 0 <= index <= len(lines):
            raise ValueError("insert_line must be between 0 and the number of lines")
        lines.insert(index, args["new_str"] + "\n")
        text = "".join(lines)
    else:
        raise ValueError("Unknown editor command")
    path.write_text(text)
    return "Updated file"


if __name__ == "__main__":
    try:
        print(edit(json.loads(sys.argv[1])))
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
