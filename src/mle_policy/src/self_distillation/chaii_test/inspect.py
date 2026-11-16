"""Reanalyze saved API responses with the same metrics as fresh sampling."""

import argparse
import json
from pathlib import Path

from .evaluation import LENGTH_METRICS, RATE_METRICS, analyze_record, response_mode, summarize


def inspect_run(path, mode="auto"):
    request_path = path.parent / "request.json"
    metadata = json.loads(request_path.read_text()) if request_path.exists() else {}
    mode = response_mode(metadata.get("request", {}), metadata.get("response_mode", mode) if mode == "auto" else mode)
    rows = [analyze_record(json.loads(line), mode) for line in path.read_text().splitlines() if line.strip()]
    return {"source": str(path), "response_mode": mode,
            "model_id": metadata.get("request", {}).get("model"),
            "prompt_sha256": metadata.get("prompt_sha256"),
            "request": metadata.get("request"), **summarize(rows), "samples": rows}


def compare_reports(reports):
    """Compare all groups with the first, retaining different sample counts."""
    baseline = reports[0]
    comparisons = []
    for report in reports:
        reference_request = baseline["request"]
        current_request = report["request"]
        different_settings = None
        if reference_request is not None and current_request is not None:
            keys = (reference_request.keys() | current_request.keys()) - {"model", "messages"}
            different_settings = sorted(key for key in keys if reference_request.get(key) != current_request.get(key))
        rates = {}
        for name in RATE_METRICS:
            reference = baseline["metrics"][name]["rate"]
            current = report["metrics"][name]["rate"]
            rates[name] = 100 * (current - reference) if current is not None and reference is not None else None
        lengths = {}
        for name in LENGTH_METRICS:
            reference = baseline["lengths"][name]["mean"]
            current = report["lengths"][name]["mean"]
            lengths[name] = {
                "mean_delta": current - reference if current is not None and reference is not None else None,
                "mean_ratio": current / reference if current is not None and reference else None,
            }
        comparisons.append({"source": report["source"], "baseline": baseline["source"],
                            "different_generation_settings": different_settings,
                            "same_prompt": report["prompt_sha256"] == baseline["prompt_sha256"]
                            if report["prompt_sha256"] and baseline["prompt_sha256"] else None,
                            "rate_delta_percentage_points": rates, "length_changes": lengths})
    return comparisons


def comparison_table(reports):
    lines = [
        "| 组别 | 成功/返回 | 思考：明确标识符 | 思考：含文字描述 | 最终代码：明确标识符 | think 闭合 | 提前停止 | 截断 | 有效最终代码 | tokens 均值/P90 | 均值相对首组 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for report in reports:
        cells = [report["source"].replace("|", "\\|"), f"{report['succeeded']}/{report['completed']}"]
        for name in ("thinking_explicit_identifier", "thinking_including_description", "final_code_explicit_identifier",
                     "thinking_closed", "premature_stop", "truncated", "valid_final_code"):
            metric = report["metrics"][name]
            cells.append(f"{metric['hits']}/{metric['total']}" if metric["total"] else "—")
        length = report["lengths"]["completion_tokens"]
        cells.append(f"{length['mean']:.0f}/{length['p90']:.0f}" if length["count"] else "—")
        reference = reports[0]["lengths"]["completion_tokens"]["mean"]
        cells.append(f"{length['mean'] / reference:.2f}×" if length["count"] and reference else "—")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n\n长度比以首组为参照；不同 prompt、底模或生成预算的组只作描述性比较。"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--response-mode", choices=["auto", "thinking", "answer"], default="auto")
    args = parser.parse_args()
    if args.output.suffix != ".json":
        parser.error("--output must be a .json path; the Markdown table uses the same stem")
    reports = [inspect_run(path, args.response_mode) for path in args.responses]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema_version": 2, "reports": reports,
                                     "comparison": compare_reports(reports)}, indent=2) + "\n")
    table = comparison_table(reports)
    args.output.with_suffix(".md").write_text(table + "\n")
    print(table)


if __name__ == "__main__":
    main()
