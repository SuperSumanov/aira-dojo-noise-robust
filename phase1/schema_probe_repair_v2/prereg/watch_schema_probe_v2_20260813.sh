#!/usr/bin/env bash
set -euo pipefail

export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/schema_probe_ops/schema_probe_repair_v2
log=/research/d7/spc/yzyang4/logs/schema_probe_v2_chain_20260813.log
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
replay_sbatch=/research/d7/spc/yzyang4/scripts/schema_probe_replay_v2_20260813.sbatch
commit=c1dc17420e95b9e2994a474c25afdcb85063ab36
generation_job=${1:?generation job id required}
deadline=$(( $(date +%s) + 25200 ))
export PYTHONPATH="$repo/src:$repo"

record() {
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$*" >> "$log"
}

wait_for_job() {
  local job_id=$1
  local label=$2
  local last_heartbeat=0
  while (( $(date +%s) < deadline )); do
    local queue
    queue=$(squeue -h -j "$job_id" -o '%i|%T|%M|%R' 2>/dev/null || true)
    if [[ -n "$queue" ]]; then
      if (( $(date +%s) - last_heartbeat >= 300 )); then
        record "$label queue=$queue senior_ref=$(git -C /research/d7/spc/yzyang4/aira-dojo-reproduce rev-parse --short HEAD 2>/dev/null || printf unavailable)"
        last_heartbeat=$(date +%s)
      fi
      sleep 30
      continue
    fi
    local accounting
    accounting=$(sacct -X -n -P -j "$job_id" -o JobIDRaw,State,ExitCode 2>/dev/null | sed '/^$/d' || true)
    if [[ -z "$accounting" ]]; then
      sleep 20
      continue
    fi
    record "$label accounting=$(printf '%s' "$accounting" | tr '\n' ';')"
    if printf '%s\n' "$accounting" | awk -F'|' 'NF>=3 && $2 !~ /^COMPLETED/ {bad=1} NF>=3 && $3 != "0:0" {bad=1} END {exit bad}'; then
      return 0
    fi
    return 1
  done
  record "$label MONITOR_TIMEOUT job=$job_id"
  return 2
}

: > "$log"
record "CHAIN_START generation_job=$generation_job commit=$(git -C "$repo" rev-parse HEAD)"
set +e
wait_for_job "$generation_job" generation
generation_rc=$?
set -e
record "GENERATION_WAIT_RC=$generation_rc"
if [[ "$generation_rc" -ne 0 ]]; then
  record "CHAIN_DONE decision=FAIL stage=generation rc=$generation_rc"
  exit "$generation_rc"
fi

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test -f "$ops/generation_manifest.json"
test -f "$ops/generation_manifest.audit.json"
set +e
"$py" phase1/extract_schema_probe_repair_manifest.py \
  --run-root "$ops/runs/aira-dojo" \
  --run-manifest "$ops/generation_manifest.json" \
  --issue schema_probe_repair_v2 \
  --seed 862 \
  --tasks spaceship-titanic tweet-sentiment-extraction \
  --out "$ops/replay_manifest.jsonl" \
  --audit "$ops/replay_manifest.audit.json" >> "$log" 2>&1
extract_rc=$?
set -e
record "EXTRACT_RC=$extract_rc"
if [[ "$extract_rc" -ne 0 ]]; then
  record "CHAIN_DONE decision=FAIL stage=static_contract rc=$extract_rc"
  exit "$extract_rc"
fi

manifest_sha=$(sha256sum "$ops/replay_manifest.jsonl" | awk '{print $1}')
replay_job=$(sbatch --parsable --export=ALL,EXPECTED_MANIFEST_SHA="$manifest_sha" "$replay_sbatch")
printf '%s\n' "$replay_job" > "$ops/replay_job_id.txt"
record "REPLAY_SUBMITTED job=$replay_job manifest_sha=$manifest_sha"
set +e
wait_for_job "$replay_job" replay
replay_rc=$?
set -e
record "REPLAY_WAIT_RC=$replay_rc"
if [[ "$replay_rc" -ne 0 ]]; then
  record "CHAIN_DONE decision=FAIL stage=replay rc=$replay_rc"
  exit "$replay_rc"
fi

set +e
"$py" phase1/validate_schema_probe_contract.py \
  --manifest "$ops/replay_manifest.jsonl" \
  --audit "$ops/replay_manifest.audit.json" \
  --out-dir "$ops/replay" >> "$log" 2>&1
validator_rc=$?
set -e
record "VALIDATOR_RC=$validator_rc"
if [[ -f "$ops/replay/schema_probe_validation.json" ]]; then
  "$py" - "$ops/replay/schema_probe_validation.json" >> "$log" <<'PY'
import json
import sys

obj = json.load(open(sys.argv[1], encoding="utf-8"))
print("VALIDATION_SUMMARY", json.dumps({
    "decision": obj["decision"],
    "probe_pass_count": obj["probe_pass_count"],
    "full_transition_count": obj["full_transition_count"],
    "rows": [{
        "competition": row["competition"],
        "probe_pass": row["probe_pass"],
        "probe_host_capture_s": row["probe_host_capture_s"],
        "probe_score": row["probe_score"],
        "valid_full_transition": row["valid_full_transition"],
        "final_rc": row["final_rc"],
    } for row in obj["rows"]],
}, sort_keys=True))
PY
fi
record "CHAIN_DONE stage=validator rc=$validator_rc"
exit "$validator_rc"

