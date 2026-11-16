"""Shared response parsing, tokenizer knowledge indicators and run summaries."""

import ast
import math
import re
import statistics


IDENTIFIER = re.compile(r"\buse_fast\b|\b\w*TokenizerFast\b")
FAST_DESCRIPTION = re.compile(r"\bfast[ -]+(?:tokenizers?|tokenization)\b", re.IGNORECASE)
CODE_FENCE = re.compile(r"^```([^\s`]*)[ \t]*$")


def response_mode(request, mode="auto"):
    """Resolve raw thinking from the original request; never change generation settings."""
    if mode not in ("auto", "thinking", "answer"):
        raise ValueError(f"Unknown response mode: {mode}")
    if mode == "auto":
        thinking = request.get("chat_template_kwargs", {}).get("enable_thinking")
        if thinking is False:
            return "answer"
        if thinking is True or request.get("reasoning_effort") in ("minimal", "low", "medium", "high", "xhigh"):
            return "thinking"
    return mode


def split_message(message, mode):
    """Separate generated thought from final answer, including prefilled think tags."""
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    if "</think>" in content:
        thought, answer = content.rsplit("</think>", 1)
        return thought.removeprefix("<think>"), answer, True, "inline"
    if "<think>" in content:
        return content.split("<think>", 1)[1], "", False, "inline"
    if reasoning:
        return reasoning, content, bool(content.strip()), "separate"
    if mode == "thinking":
        return content, "", False, "prefilled"
    return "", content, None, "answer"


def code_blocks(answer):
    """Extract Python/unlabelled fenced blocks, retaining a truncated final block."""
    blocks = []
    pending = None
    python_block = False
    for line in answer.splitlines(keepends=True):
        if pending is not None:
            if line.strip() == "```":
                if python_block:
                    blocks.append(("".join(pending), True))
                pending = None
            else:
                pending.append(line)
        else:
            opening = CODE_FENCE.fullmatch(line.rstrip("\r\n"))
            if opening:
                pending = []
                python_block = opening.group(1) in ("", "py", "python")
    if pending is not None and python_block:
        blocks.append(("".join(pending), False))
    return blocks


def analyze_record(record, mode="auto"):
    """Recompute from raw responses; old cached indicators are deliberately ignored."""
    if "error" in record:
        return {"sample_index": record["sample_index"], "error": record["error"]}
    response = record["response"]
    choice = response["choices"][0]
    finish_reason = choice["finish_reason"]
    reasoning, answer, thinking_closed, thinking_format = split_message(choice["message"], mode)
    blocks = code_blocks(answer)
    final_code = "\n".join(block for block, _ in blocks)
    code = max((block for block, _ in blocks), key=len, default="")
    syntax_error = None
    tree = None
    if code.strip():
        try:
            tree = ast.parse(code)
        except SyntaxError as error:
            syntax_error = str(error)
    auto_tokenizer_default = False
    explicit_slow_tokenizer = False
    explicit_fast_constructor = False
    slow_class_use_fast = False
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "from_pretrained" or not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id == "AutoTokenizer":
                auto_tokenizer_default |= all(keyword.arg not in (None, "use_fast") for keyword in node.keywords)
            use_fast_true = any(
                keyword.arg == "use_fast" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                for keyword in node.keywords
            )
            constructor = node.func.value.id
            explicit_fast_constructor |= constructor.endswith("TokenizerFast") or (
                constructor == "AutoTokenizer" and use_fast_true
            )
            explicit_slow_tokenizer |= constructor == "XLMRobertaTokenizer"
            slow_class_use_fast |= constructor == "XLMRobertaTokenizer" and use_fast_true
    requests_offsets = bool(re.search(r"\breturn_offsets_mapping\s*=\s*True\b", code))
    thinking_identifier = bool(IDENTIFIER.search(reasoning))
    usage = response.get("usage") or {}
    return {
        "sample_index": record["sample_index"],
        "finish_reason": finish_reason,
        "thinking_format": thinking_format,
        "thinking_closed": thinking_closed,
        "premature_stop": finish_reason == "stop" and thinking_closed is False,
        "truncated": finish_reason == "length",
        "thinking_explicit_identifier": thinking_identifier,
        "thinking_including_description": thinking_identifier or bool(FAST_DESCRIPTION.search(reasoning)),
        "final_code_explicit_identifier": bool(IDENTIFIER.search(final_code)),
        "has_final_answer": bool(answer.strip()),
        "has_code": bool(final_code.strip()),
        "code_fences_closed": all(closed for _, closed in blocks) if blocks else None,
        "valid_final_code": bool(code.strip()) and all(closed for _, closed in blocks) and syntax_error is None,
        "explicit_fast_constructor": explicit_fast_constructor,
        "slow_class_use_fast": slow_class_use_fast,
        "auto_tokenizer_default": auto_tokenizer_default,
        "explicit_slow_with_offsets": explicit_slow_tokenizer and requests_offsets,
        "reasoning_chars": len(reasoning),
        "answer_chars": len(answer),
        "primary_code_chars": len(code),
        "completion_tokens": usage.get("completion_tokens"),
        "code_blocks": len(blocks),
        "syntax_error": syntax_error,
    }


RATE_METRICS = (
    "thinking_explicit_identifier", "thinking_including_description", "final_code_explicit_identifier",
    "thinking_closed", "premature_stop", "truncated", "has_final_answer", "has_code", "code_fences_closed",
    "valid_final_code", "explicit_fast_constructor", "slow_class_use_fast", "auto_tokenizer_default",
    "explicit_slow_with_offsets",
)
LENGTH_METRICS = ("completion_tokens", "reasoning_chars", "answer_chars", "primary_code_chars")


def proportion(hits, total):
    """Empirical rate and 95% Wilson interval; unknown values have no denominator."""
    if not total:
        return {"hits": hits, "total": total, "rate": None, "wilson_95": None}
    rate = hits / total
    z_score = 1.959963984540054
    denominator = 1 + z_score**2 / total
    center = (rate + z_score**2 / (2 * total)) / denominator
    radius = z_score * math.sqrt(rate * (1 - rate) / total + z_score**2 / (4 * total**2)) / denominator
    return {"hits": hits, "total": total, "rate": rate,
            "wilson_95": [max(0, center - radius), min(1, center + radius)]}


def length_summary(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None, "min": None, "max": None}
    return {"count": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
            "p90": values[math.ceil(0.9 * len(values)) - 1], "min": values[0], "max": values[-1]}


def summarize(rows):
    successful = [row for row in rows if "error" not in row]
    stopped = [row for row in successful if row["finish_reason"] == "stop"]

    def rates(group):
        return {
            name: proportion(sum(row[name] is True for row in group), sum(row[name] is not None for row in group))
            for name in RATE_METRICS
        }

    return {
        "schema_version": 2,
        "completed": len(rows), "succeeded": len(successful), "failed": len(rows) - len(successful),
        "truncated": sum(row["truncated"] for row in successful),
        "metrics": rates(successful), "stop_only_metrics": rates(stopped),
        "lengths": {name: length_summary(row[name] for row in successful) for name in LENGTH_METRICS},
    }
