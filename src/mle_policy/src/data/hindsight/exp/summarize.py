"""Collect measured execution results from a prepared experiment.

Input --output: manifest.json and runs/<name>/result.json from evaluate.py.
Output: results.json in the same directory, one row per manifest run.
Historical CV/test labels and measured scores remain separate columns.
"""

import argparse
import json
from pathlib import Path

from ..helper import write_json


def summarize(output: Path) -> None:
    """Read completed runs and write their execution counts and measured scores."""
    manifest = json.loads((output / "manifest.json").read_text())
    rows = []
    for record in manifest["runs"]:
        attempts = json.loads((output / record["result"]).read_text())["attempts"]
        terminal = attempts[-1]
        rows.append(
            {
                **record,
                "executed_attempts": len(attempts),
                "first_attempt_valid": attempts[0]["valid"],
                "resolved": terminal["valid"],
                "debug_calls_to_success": terminal["attempt"] if terminal["valid"] else None,
                "test_score": terminal["test_score"] if terminal["valid"] else None,
                "execution_seconds": sum(result["execution"]["exec_time"] for result in attempts),
            }
        )
    write_json(output / "results.json", rows)
    print(f"Evaluated {len(rows)} solutions: {sum(row['resolved'] for row in rows)} valid", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Completed evaluation directory")
    summarize(parser.parse_args().output)
