#!/usr/bin/env bash
set -euo pipefail

export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
ops=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
log=/research/d7/spc/yzyang4/logs/probe_contract_ab_v2_chain_20260813.log
py=/research/d7/spc/yzyang4/venvs/exp/bin/python
grader=/research/d7/spc/yzyang4/venvs/exp/bin/mlebench
replay_sbatch="$repo/phase1/probe_contract_ab_safety_v2/prereg/probe_contract_ab_v2_replay_20260813.sbatch"
independent="$ops/prereg/verify_probe_contract_ab_v2_independent.py"
commit=$(cat "$ops/prereg/expected_commit.txt")
generation_job=${1:?generation job id required}
deadline=$(( $(date +%s) + 25200 ))
export PYTHONPATH="$repo/src:$repo/phase1:$repo"

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
        record "$label queue=$(printf '%s' "$queue" | tr '\n' ';')"
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
    if printf '%s\n' "$accounting" | awk -F'|' \
      'NF>=3 && $2 !~ /^COMPLETED/ {bad=1} NF>=3 && $3 != "0:0" {bad=1} END {exit bad}'; then
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
  record "CHAIN_DONE verdict=INVALID stage=generation rc=$generation_rc"
  exit "$generation_rc"
fi

cd "$repo"
test "$(git rev-parse HEAD)" = "$commit"
test -z "$(git status --short)"
test -f "$ops/generation_manifest.json"
set +e
"$py" -m phase1.extract_probe_contract_ab_manifest \
  --version v2 \
  --generation-manifest "$ops/generation_manifest.json" \
  --out "$ops/replay_manifest.jsonl" \
  --audit "$ops/replay_manifest.audit.json" >> "$log" 2>&1
extract_rc=$?
set -e
record "EXTRACT_RC=$extract_rc"
if [[ "$extract_rc" -ne 0 ]]; then
  record "CHAIN_DONE verdict=INVALID stage=extraction rc=$extract_rc"
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
  record "CHAIN_DONE verdict=INVALID stage=replay rc=$replay_rc"
  exit "$replay_rc"
fi

set +e
"$py" -m phase1.validate_probe_contract_ab \
  --version v2 \
  --manifest "$ops/replay_manifest.jsonl" \
  --extraction-audit "$ops/replay_manifest.audit.json" \
  --generation-manifest "$ops/generation_manifest.json" \
  --replay-dir "$ops/replay" \
  --data-dir /research/d7/spc/yzyang4/mle-bench-data \
  --output "$ops/probe_contract_ab_result.json" >> "$log" 2>&1
validator_rc=$?
set -e
record "VALIDATOR_RC=$validator_rc"
if [[ "$validator_rc" -ne 0 ]]; then
  record "CHAIN_DONE verdict=INVALID stage=primary_validator rc=$validator_rc"
  exit "$validator_rc"
fi

set +e
"$py" "$independent" \
  --root "$ops" \
  --data-dir /research/d7/spc/yzyang4/mle-bench-data \
  --grader "$grader" \
  --output "$ops/independent_probe_contract_ab_result.json" >> "$log" 2>&1
independent_rc=$?
set -e
record "INDEPENDENT_RC=$independent_rc"
if [[ "$independent_rc" -ne 0 ]]; then
  record "CHAIN_DONE verdict=INVALID stage=independent_verifier rc=$independent_rc"
  exit "$independent_rc"
fi
if [[ -f "$ops/probe_contract_ab_result.json" ]]; then
  "$py" - "$ops/probe_contract_ab_result.json" >> "$log" <<'PY'
import json
import sys

obj = json.load(open(sys.argv[1], encoding="utf-8"))
summary = obj["summary"]
print("AB_SUMMARY", json.dumps({
    "verdict": obj["verdict"],
    "gates": obj["gates"],
    "original_coverage_120": summary["original_coverage_120"],
    "contract_coverage_120": summary["contract_coverage_120"],
    "coverage_gain": summary["coverage_gain"],
    "contract_probe_valid": summary["contract_probe_valid"],
    "original_full_valid": summary["original_full_valid"],
    "contract_full_valid": summary["contract_full_valid"],
    "paired_full_scores": summary["paired_full_scores"],
    "median_relative_oriented_full_delta": summary["median_relative_oriented_full_delta"],
    "catastrophic_harm_count": summary["catastrophic_harm_count"],
}, sort_keys=True))
PY
fi
touch "$ops/CHAIN_COMPLETE"
record "CHAIN_DONE stage=double_verified rc=0"
