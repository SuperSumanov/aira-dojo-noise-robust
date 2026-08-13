#!/usr/bin/env bash
set -euo pipefail

REPO=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
LARGE=/research/d7/spc/yzyang4/large_data
PY=/research/d7/spc/yzyang4/venvs/critic/bin/python
TD=$(mktemp -d "$LARGE/v12_rebuild.XXXXXX")

cleanup() {
  case "$TD" in
    "$LARGE"/v12_rebuild.*) rm -rf -- "$TD" ;;
    *) echo "refusing unsafe cleanup target: $TD" >&2; exit 97 ;;
  esac
}
trap cleanup EXIT

cd "$REPO"

"$PY" -m phase1.build_exploratory_v12 \
  --runs-root /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo \
  --base phase1/cards_current_v11.jsonl \
  --extension "$TD/extension.jsonl" \
  --combined "$TD/combined.jsonl" \
  --run-map "$TD/run_map.json" \
  --audit "$TD/audit.json" > "$TD/build.log"

cmp phase1/cards_extension_exploratory_v12.jsonl "$TD/extension.jsonl"
cmp "$LARGE/cards_exploratory_v12.jsonl" "$TD/combined.jsonl"
cmp "$LARGE/card_run_map_exploratory_v12.json" "$TD/run_map.json"

python - "$TD/audit.json" phase1/exploratory_v12_audit.json <<'PY'
import json, sys

left = json.load(open(sys.argv[1]))
right = json.load(open(sys.argv[2]))
for value in (left, right):
    value["extension"].pop("path", None)
    value["combined"].pop("path", None)
    value["run_map"].pop("path", None)
assert left == right
PY

"$PY" phase1/build_decision_v10.py \
  --cards "$TD/combined.jsonl" \
  --old-cards phase1/cards_current_v11.jsonl \
  --run-map "$TD/run_map.json" \
  --prior-hold phase1/v11_decision/runsplit_holdruns_v11.json \
  --frozen-hold phase1/runsplit_holdruns.json \
  --base-dir phase1/v11_decision \
  --base-version v11 \
  --out-dir "$TD/decision" \
  --version v12x > "$TD/decision.log"

for role in train frozen extension; do
  for budget in 0 1 2; do
    cmp \
      "phase1/v12_exploratory_decision/decision_${role}_v12x_b${budget}.jsonl" \
      "$TD/decision/decision_${role}_v12x_b${budget}.jsonl"
  done
done
cmp \
  phase1/v12_exploratory_decision/runsplit_holdruns_v12x.json \
  "$TD/decision/runsplit_holdruns_v12x.json"

python - "$TD/decision/decision_v12x_audit.json" \
  phase1/v12_exploratory_decision/decision_v12x_audit.json <<'PY'
import json, sys

left = json.load(open(sys.argv[1]))
right = json.load(open(sys.argv[2]))
for value in (left, right):
    value["inputs"].pop("cards", None)
    value["inputs"].pop("run_map", None)
assert left == right
PY

echo "EXPLORATORY_V12_DETERMINISTIC_REBUILD_PASS"
