"""Narrow wire-type repair for submit_review's number-or-null metric.

No metric estimation, score extraction, defaulting or loosening of other fields.
On explicitly buggy reviews a textual metric becomes null (never a score).
Otherwise unknown strings stay unchanged for the existing schema validator.
"""
import json
import math


def normalize_review(output, schema, function_name):
    if function_name != 'submit_review' or not isinstance(output, dict):
        return output
    metric_schema = schema.get('properties', {}).get('metric', {})
    if metric_schema.get('type') not in (['number', 'null'], ['null', 'number']):
        return output
    value = output.get('metric')
    if not isinstance(value, str):
        return output
    if output.get('is_bug') is True:
        # The review contract says failed execution has no validation metric.
        # This can restore diagnostic text, never make a buggy node successful.
        return dict(output, metric=None)
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return output
    if parsed is not None:
        try:
            if type(parsed) not in (int, float) or not math.isfinite(parsed):return output
        except OverflowError:
            return output
    return dict(output, metric=parsed)


def patch_parser(source):
    anchor='        jsonschema.Draft7Validator(func_spec.json_schema).validate(output)'
    if source.count(anchor) != 1:
        raise ValueError('parser source anchor changed')
    return source.replace(anchor,
        '        from dojo.core.solvers.llm_helpers.backends.review_metric import normalize_review\n'
        '        output = normalize_review(output, func_spec.json_schema, func_spec.name)\n'+anchor, 1)
