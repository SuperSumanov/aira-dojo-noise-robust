"""Extract private hints, regenerate full policy responses, and attach provenance."""

import asyncio
import copy
import json

from . import prompts
from .helper import parts
from .tree import Episode, operator, synthetic_id


def inject_hint(messages: list[dict], hint: str, code: str | None = None) -> list[dict]:
    """Copy messages and prepend guidance with optional source code to the last user prompt."""
    augmented = copy.deepcopy(messages)
    user = next((message for message in reversed(augmented) if message["role"] == "user"), None)
    if user is None or not isinstance(user.get("content"), str):
        raise ValueError("Expected an original text user prompt")
    advice = hint
    if code is not None:
        advice += "\n\nImplementation example to learn from:\n```python\n" + code.rstrip() + "\n```"
    user["content"] = (
        "\n\n<hindsight_notes>\n"
        + advice
        + "\nUse these hindsight notes as useful experience while solving the original task."
        " Choose and develop your own coherent approach; adapt the suggestions where appropriate."
        " Return a complete standalone answer in the original task's requested format without explicitly mentioning the hindsight."
        "\n</hindsight_notes>"
    ) + user["content"]
    return augmented


async def extract_hint(stage, target, donor, nodes, client, *, trace=None):
    """Extract guidance from source trajectories, summarizing long inputs in parts and optionally recording calls."""
    if stage == "debug":
        generate_hint = client.debug_hint
    elif stage == "improve":
        generate_hint = client.improve_hint
    else:
        raise ValueError(f"Invalid hint stage: {stage}")

    async def ask(messages, *, part=False):
        """Call the selected hint endpoint and optionally record the part or synthesis input and result."""
        result = await generate_hint(messages, part=part)
        if trace is not None:
            request_stage = stage + ("_hint_part" if part else "_hint")
            trace.append({"stage": request_stage, "messages": messages, "result": result})
        return result

    extraction = prompts.hint(target, donor, nodes, stage)
    if len(extraction[1]["content"]) > 250000:
        payload = json.loads(extraction[1]["content"])
        chunks = []
        for key in ("target_trajectory", "donor_trajectory"):
            for entry in payload[key]:
                chunk = {**payload, "target_trajectory": [], "donor_trajectory": []}
                chunk[key] = [entry]
                chunks.append([extraction[0], {"role": "user", "content": json.dumps(chunk, ensure_ascii=False)}])
        extracted = await asyncio.gather(*(ask(chunk, part=True) for chunk in chunks))
        payload["target_trajectory"] = []
        payload["donor_trajectory"] = []
        payload["trajectory_guidance"] = [part["hint"] for part in extracted]
        extraction = [extraction[0], {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    return (await ask(extraction))["hint"]


def generation_options(recorded: dict | None = None) -> dict:
    """Build reasoning-enabled sampling settings while preserving explicitly recorded operator parameters."""
    options = {
        "temperature": 0.6,
        "top_p": 0.95,
        "chat_template_kwargs": {"enable_thinking": True, "reasoning_effort": "medium"},
    }
    if recorded:
        for key in ("temperature", "top_p", "top_k", "min_p", "max_tokens", "seed", "repetition_penalty"):
            if key in recorded:
                options[key] = recorded[key]
        template = recorded.get("chat_template_kwargs", {})
        if template.get("enable_thinking") is False or template.get("enable_reasoning") is False:
            raise ValueError("Hindsight regeneration requires a reasoning-enabled policy")
        options["chat_template_kwargs"].update(template)
        if "reasoning_effort" in recorded:
            options["chat_template_kwargs"]["reasoning_effort"] = recorded["reasoning_effort"]
    return options


async def regenerate(stage, target, donor, nodes, client, *, include_code, generation, hint=None, trace=None):
    """Generate a full response from a hint-augmented prompt and return the hint, settings, and model result."""
    if hint is None:
        hint = await extract_hint(stage, target, donor, nodes, client)
    original = nodes[target.root]["operators_metrics"][0]["prompt_messages"]
    code = nodes[donor.terminal]["code"]
    augmented = inject_hint(original, hint, code if include_code else None)
    result = await client.generate(augmented, generation)
    if trace is not None:
        trace.update({"messages": augmented, "generation": generation, "result": result})
    return {**result, "hint": hint, "include_code": include_code, "generation": generation}


def reference(node: dict) -> dict:
    """Return a compact step and id reference for source provenance."""
    return {"step": node["step"], "id": node["id"]}


def append_rewrite(output, stage, target: Episode, donor: Episode, original, result, source_journal):
    """Append a regenerated node and required ancestors, restoring the original prompt and inheriting the donor metric."""
    root, executed = original[target.root], original[donor.terminal]
    pending = list(root.get("parents", []))
    existing = {node["step"] for node in output}
    while pending:
        parent = pending.pop()
        if parent not in existing:
            existing.add(parent)
            pending.extend(original[parent].get("parents", []))
            output.append(
                {
                    "step": parent,
                    "id": synthetic_id("context", original[parent]["id"]),
                    "parents": original[parent].get("parents", []).copy(),
                    "children": [],
                    "operators_used": [],
                    "operators_metrics": [],
                    "is_buggy": True,
                    "code": "",
                    "metric": None,
                    "hindsight": {
                        "kind": "context",
                        "source_journal": source_journal,
                        "source_node": reference(original[parent]),
                    },
                }
            )
    _, answer, block = parts(result["completion"])
    added = {
        "metric": executed["metric"],
        "metric_maximize": executed["metric_maximize"],
        "is_buggy": None,
        "code": block.group("code").rstrip(),
        "plan": answer[: block.start()].strip(),
        "analysis": None,
        "term_out": None,
        "_term_out": None,
        "exit_code": None,
        "exec_time": None,
        "current_best_node": 0,
    }
    reward_fields = (
        "competition_id",
        "median_threshold",
        "gold_threshold",
        "silver_threshold",
        "bronze_threshold",
        "is_lower_better",
    )
    for field in reward_fields:
        key = "metric_info/" + field
        if key in executed:
            added[key] = copy.deepcopy(executed[key])
    if "metric_info" in executed:
        added["metric_info"] = {
            key: copy.deepcopy(value) for key, value in executed["metric_info"].items() if key in reward_fields
        }
    added["step"] = max([*original, *(node["step"] for node in output)]) + 1
    added["id"] = synthetic_id(stage, root["id"], executed["id"], result["cache_key"])
    added["parents"] = root.get("parents", []).copy()
    added["children"] = []
    call = copy.deepcopy(root["operators_metrics"][0])
    call["completion_text"] = result["completion"]
    call["usage"] = {}
    added["operators_used"] = [operator(root)]
    added["operators_metrics"] = [call]
    added["hindsight"] = {
        "kind": "rewrite",
        "stage": stage,
        "source_journal": source_journal,
        "prompt_source": reference(root),
        "source_parents": [reference(original[parent]) for parent in root.get("parents", [])],
        "target_trajectory": [reference(original[step]) for step in target.steps],
        "donor_trajectory": [reference(original[step]) for step in donor.steps],
        "response_origin": "regenerated",
        "execution_status": "not_run",
        "metric_origin": "inherited",
        "metric_source": reference(executed),
        "hint_includes_code": result["include_code"],
        "generation_cache_key": result["cache_key"],
        "generation": result["generation"],
        "generation_model": result["model"],
    }
    output.append(added)
    return {
        "root": target.root,
        "terminal": target.terminal,
        "donor_root": donor.root,
        "donor_terminal": donor.terminal,
        "added_steps": [added["step"]],
        "hint": result["hint"],
        "generation_cache_key": result["cache_key"],
    }
