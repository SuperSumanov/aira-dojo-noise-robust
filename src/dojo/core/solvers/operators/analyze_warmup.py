"""Review CV and harness warmup feedback without exposing hidden test results."""

import json

from dojo.core.solvers.operators.analyze import analyze_schema_with_eval, analyze_schema_without_eval
from dojo.core.solvers.utils.response import wrap_code
from dojo.tasks.mlebench.warmup.grade import FEEDBACK_PREFIX


def analyze_warmup_op(analyze_llm, cfg, task_description, input_node, fetch_metric=True):
    feedback_entry = input_node._term_out[-1] if input_node._term_out else ""
    if not feedback_entry.startswith(FEEDBACK_PREFIX):
        raise ValueError("Warmup analysis requires task-generated feedback")
    feedback = json.loads(feedback_entry.removeprefix(FEEDBACK_PREFIX))
    allowed = {
        "status",
        "score",
        "metric",
        "lower_is_better",
        "num_samples",
        "num_submission_rows",
        "version",
        "error",
    }
    if set(feedback) - allowed:
        raise ValueError("Unexpected fields in public warmup feedback")
    schema = json.loads(analyze_schema_with_eval if fetch_metric else analyze_schema_without_eval)
    schema["properties"]["summary"]["description"] = (
        "If there is a clear bug and no cross validaiton (CV) result, propose a fix. Otherwise, write a short summary (2-3 sentences) describing the empirical findings. DO NOT suggest fixes or improvements."
        "If there is CV and warmup grading, compare script CV and independent warmup grading; Detect potential bugs in generated test output or severe overfitting issue in CV, "
        "and propose fixes when supported by the code. Never treat the warmup score as golden; it is only a small set for debugging."
        "Some differences between the CV and warmup scores are expected, but large differences (eg. warmup score -> 0 while CV score is high) may indicate a problem."
    )
    if fetch_metric:
        schema["properties"]["metric"][
            "description"
        ] = "The script's own CV metric, never the harness warmup score. Null if unavailable."
    return analyze_llm(
        query_data={
            "task_desc": task_description,
            "code": wrap_code(input_node.code),
            "execution_output": wrap_code(input_node.term_out, lang=""),
            "warmup_feedback": json.dumps(feedback),
        },
        json_schema=json.dumps(schema),
        function_name="submit_review",
        function_description="Review execution and warmup feedback; preserve the CV metric.",
    )
