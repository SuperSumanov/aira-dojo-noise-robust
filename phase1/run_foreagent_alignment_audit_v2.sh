#!/usr/bin/env bash
set -euo pipefail

set +u
source "$HOME/env_setup.sh"
set -u

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
scratch=/research/d7/spc/yzyang4/scratch/pbe_alignment_cache_v1
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
manifest="$repo/phase1/foreagent_alignment_manifest_v1.json"
download_log="$scratch/download_log.json"
master="$scratch/all_predictions.compact.jsonl"
staging="$repo/phase1/.foreagent_alignment_audit_v2.staging"
out="$repo/phase1/foreagent_alignment_audit_v2"

cd "$repo"
test ! -e "$staging"
test ! -e "$out"
test "$(sha256sum "$master" | awk '{print $1}')" = \
  480616317ddebb249084dbc8b36b4060fac4b77353fce16b436351eab9c235fe

echo "FOREAGENT_ALIGNMENT_V2_START $(date -Is)"
set +e
"$py" phase1/audit_foreagent_alignments.py \
  --manifest "$manifest" \
  --download-log "$download_log" \
  --master "$master" \
  --out-dir "$staging"
audit_rc=$?
set -e
echo "FOREAGENT_ALIGNMENT_V2_AUDIT_RC=$audit_rc $(date -Is)"
if [[ "$audit_rc" -ne 0 ]]; then
  exit "$audit_rc"
fi

set +e
"$py" phase1/verify_foreagent_alignment_audit.py \
  --manifest "$manifest" \
  --master "$master" \
  --summary "$staging/summary.json"
verify_rc=$?
set -e
echo "FOREAGENT_ALIGNMENT_V2_VERIFY_RC=$verify_rc $(date -Is)"
if [[ "$verify_rc" -ne 0 ]]; then
  exit "$verify_rc"
fi

(
  cd "$staging"
  sha256sum grid.csv per_run.csv per_task.csv stratified.csv summary.json > SHA256SUMS
)
mv -- "$staging" "$out"
echo "FOREAGENT_ALIGNMENT_V2_PROMOTED out=$out $(date -Is)"
cat "$out/SHA256SUMS"
echo "FOREAGENT_ALIGNMENT_V2_DONE $(date -Is)"
