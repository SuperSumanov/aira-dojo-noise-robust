"""Regression tests for the analysis operator's structured-output schema."""

import json

import jsonschema

from dojo.core.solvers.operators.analyze import analyze_schema_with_eval


def test_analysis_schema_accepts_null_metric_for_buggy_execution() -> None:
    schema = json.loads(analyze_schema_with_eval)

    jsonschema.Draft7Validator(schema).validate(
        {
            "is_bug": True,
            "summary": "Cast the material id to an integer before building the path.",
            "metric": None,
        }
    )


def test_analysis_schema_accepts_numeric_metric_for_successful_execution() -> None:
    schema = json.loads(analyze_schema_with_eval)

    jsonschema.Draft7Validator(schema).validate(
        {"is_bug": False, "summary": "Cross-validation completed.", "metric": 0.8123}
    )
