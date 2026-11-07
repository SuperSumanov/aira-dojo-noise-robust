"""Report observed execution results, keeping unfinished debug chains explicit."""

import argparse
import json
from pathlib import Path

from ..helper import atomic_json


def summarize(output: Path) -> None:
    manifest = json.loads((output / "manifest.json").read_text())
    rows = []
    for record in manifest["runs"]:
        directory = output / "runs" / record["name"]
        attempts = []
        attempt = 0
        while (directory / f"attempt-{attempt}.json").exists():
            result = json.loads((directory / f"attempt-{attempt}.json").read_text())
            attempts.append(result)
            if result["valid"]:
                break
            attempt += 1
        terminal = next((result for result in attempts if result["valid"]), None)
        if terminal:
            status = "resolved"
        elif not attempts:
            status = "not_run"
        elif record["variant"] in ("terminal-reference", "donor-reference"):
            status = "reference_failed"
        elif len(attempts) >= 5:
            status = "repair_budget_exhausted"
        elif (directory / f"attempt-{len(attempts)}.py").exists():
            status = "repair_ready"
        else:
            status = "needs_repair"
        rows.append(
            {
                **record,
                "executed_attempts": len(attempts),
                "first_attempt_valid": attempts[0]["valid"] if attempts else None,
                "resolved": terminal is not None,
                "status": status,
                "debug_calls_to_success": terminal["attempt"] if terminal else None,
                "observed_failed_attempts": sum(not result["valid"] for result in attempts),
                "test_score": terminal["test_score"] if terminal else None,
                "execution_seconds": sum(result["execution"]["exec_time"] for result in attempts),
            }
        )
    atomic_json(output / "results.json", rows)
    header = "| Solution | Status | Attempts run | Debug calls to success | Test score | Historical debug calls | Historical test |"
    lines = [header, "|---|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        debug = row["debug_calls_to_success"] if row["resolved"] else "unresolved"
        score = f"{row['test_score']:.5f}" if row["test_score"] is not None else "—"
        lines.append(
            f"| {row['name']} | {row['status']} | {row['executed_attempts']} | {debug} | {score} | "
            f"{row['historical_debug_calls']} | {row['historical_test']} |"
        )
    text = "\n".join(lines) + "\n"
    (output / "results.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("tmp/examples/hindsight/exp"))
    summarize(parser.parse_args().output)
