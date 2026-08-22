#!/usr/bin/env bash
set -euo pipefail

readonly ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
readonly PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python

"${PYTHON}" - "${ROOT}" <<'PY'
import json
import pathlib
import sys
from collections import Counter

root = pathlib.Path(sys.argv[1])
paths = sorted(root.glob("intakes/0821-*/source_provenance.json"))
if not paths:
    paths = sorted(root.glob("**/0821-*/source_provenance.json"))

def walk(value, prefix=""):
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, type(value[key]).__name__
            yield from walk(value[key], path)
    elif isinstance(value, list) and value:
        path = f"{prefix}[]"
        yield path, type(value[0]).__name__
        yield from walk(value[0], path)

schemas = Counter()
matched = Counter()
needles = ("client", "model", "generator", "hardware", "time_limit", "execution_timeout")
parse_errors = 0
record_count = 0
for path in paths:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        parse_errors += 1
        continue
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        parse_errors += 1
        continue
    record_count += len(payload)
    fields = tuple(walk(payload))
    schemas[fields] += 1
    lowered = [name.lower() for name, _ in fields]
    for needle in needles:
        if any(needle in name for name in lowered):
            matched[needle] += 1

print(
    f"files={len(paths)} records={record_count} parse_errors={parse_errors} "
    f"distinct_schemas={len(schemas)}"
)
for fields, count in sorted(schemas.items(), key=lambda item: (-item[1], item[0])):
    print(f"schema_count={count}")
    for name, kind in fields:
        print(f"field={name} type={kind}")
for needle in needles:
    print(f"files_with_{needle}_field={matched[needle]}")
print("PROVENANCE_SCHEMA_ONLY_COMPLETE")
PY
