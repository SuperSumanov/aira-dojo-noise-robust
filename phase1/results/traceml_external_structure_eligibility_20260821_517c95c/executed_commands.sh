#!/usr/bin/env bash
# Exact formal command skeleton. All outputs were written outside the clean worktree.
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -euo pipefail

commit=517c95c87edceb9d5841696982a34638db9d2fe2
worktree=/research/d7/spc/yzyang4/worktrees/traceml-audit-517c95c-nosmudge2
inputs=/research/d7/spc/yzyang4/external/traceml-61faec615b179f186dbe9c82ee59d17e14817e96/data/paired
outputs=/research/d7/spc/yzyang4/traceml-external-structure-audit/517c95c-61faec6-v2
python=/research/d7/spc/yzyang4/venvs/exp/bin/python
state_sha=b7fb37b040258bbb958c5ba1bc78952729fb69daabc75797974ef2cf19b74e02
action_sha=d23a471ab1dcfbda16836827a763f829c9de12071b32bfcc88f69d4411a8d2e4
revision=61faec615b179f186dbe9c82ee59d17e14817e96

# Before these commands, the focused test file was run with Python -B and
# pytest's cache provider disabled; it reported 12 passed.
for run in 1 2; do
  "${python}" "${worktree}/phase1/traceml_external_structure_audit.py" \
    --state "${inputs}/state.parquet" --expect-state-sha256 "${state_sha}" \
    --action "${inputs}/action.parquet" --expect-action-sha256 "${action_sha}" \
    --revision "${revision}" --source-commit "${commit}" \
    --output "${outputs}/producer_${run}.json"
done
cmp "${outputs}/producer_1.json" "${outputs}/producer_2.json"
producer_sha=$(sha256sum "${outputs}/producer_1.json" | awk '{print $1}')

for run in 1 2; do
  "${python}" "${worktree}/phase1/verify_traceml_external_structure_audit.py" \
    --state "${inputs}/state.parquet" --expect-state-sha256 "${state_sha}" \
    --action "${inputs}/action.parquet" --expect-action-sha256 "${action_sha}" \
    --revision "${revision}" --source-commit "${commit}" \
    --producer-source "${worktree}/phase1/traceml_external_structure_audit.py" \
    --producer-result "${outputs}/producer_1.json" \
    --expect-producer-result-sha256 "${producer_sha}" \
    --output "${outputs}/verifier_${run}.json"
done
cmp "${outputs}/verifier_1.json" "${outputs}/verifier_2.json"
