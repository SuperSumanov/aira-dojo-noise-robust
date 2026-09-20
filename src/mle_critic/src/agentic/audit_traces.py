"""Summarize saved trajectories and render one readable Markdown file per trace."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


def audit(directory):
    summaries = []
    for path in sorted(Path(directory).glob("*.jsonl")):
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        start = events[0]
        results = [e for e in events if e["event"] == "result"]
        result = results[-1] if results else {}
        tools = [e for e in events if e["event"] == "tool"]
        summary = {"trace": path.name, "sample_uuid": start["sample_uuid"], "task": start["task"],
                   "reward": result.get("reward"), "answer": result.get("answer"),
                   "ground_truth": result.get("ground_truth"), "tool_calls": len(tools),
                   "tool_errors": sum(t["result"].get("exit_code", 0) != 0 or "error" in t["result"] for t in tools),
                   "tool_timeouts": sum(t["result"].get("timed_out", False) for t in tools),
                   "model_tokens": result.get("model_tokens"), "observation_tokens": result.get("observation_tokens"),
                   "closed": events[-1].get("runtime_removed", False), "completed": bool(results)}
        summaries.append(summary)
        lines = [f"# {start['task']} — {start['sample_uuid']}", "", json.dumps(summary, indent=2), ""]
        for event in events:
            if event["event"] == "assistant":
                lines += ["## Assistant", "", event["text"], ""]
            elif event["event"] == "tool":
                lines += [f"## Tool: {event['name']}", "", "```json", event["arguments"], "```", "",
                          "```text", event["observation"], "```", ""]
            elif event["event"] == "error":
                lines += ["## Error", event["error"], ""]
        path.with_suffix(".md").write_text("\n".join(lines))
    groups = defaultdict(list)
    for row in summaries:
        if row["completed"]:
            groups[row["sample_uuid"]].append(row["reward"])
    report = {"trajectories": len(summaries), "completed": sum(s["completed"] for s in summaries),
              "closed": sum(s["closed"] for s in summaries),
              "valid_answers": sum(s["answer"] in ("A", "B") for s in summaries),
              "tool_calls": sum(s["tool_calls"] for s in summaries),
              "tool_errors": sum(s["tool_errors"] for s in summaries),
              "tool_timeouts": sum(s["tool_timeouts"] for s in summaries),
              "correct": sum(s["reward"] == 1 for s in summaries),
              "groups_with_nonzero_reward_variance": sum(len(set(values)) > 1 for values in groups.values()),
              "rows": summaries}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_dir", type=Path)
    args = parser.parse_args()
    report = audit(args.trace_dir)
    (args.trace_dir.parent / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
