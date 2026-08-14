#!/usr/bin/env bash
# Score-blind stage gate followed by complete-coverage D_val collection.
set -eo pipefail

if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 5 ]]; then
  echo "usage: $0 RUN_ROOT SOURCE_ROOT DATA_GATE STAGE1_JOB STAGE2_JOB" >&2
  exit 2
fi
run_root="$1"
source_root="$2"
data_gate="$3"
stage_one_job="$4"
stage_two_job="$5"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
events="$run_root/monitor_events.log"
external_log_root="/research/d7/spc/yzyang4/logs/$(basename "$run_root")"
mkdir -p "$external_log_root"

event() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$events"
}

wait_job_absent() {
  local job_id="$1"
  local label="$2"
  local deadline=$(( $(date +%s) + 10800 ))
  while squeue -h -j "$job_id" 2>/dev/null | grep -q .; do
    if (( $(date +%s) >= deadline )); then
      event "${label}_MONITOR_TIMEOUT job=${job_id}"
      return 1
    fi
    sleep 30
  done
  event "${label}_LEFT_QUEUE job=${job_id}"
}

validate_indices() {
  local plan_key="$1"
  "$python_bin" - "$run_root/preparation/run_plan.json" "$run_root/job_rc" "$plan_key" <<'PY'
import json, pathlib, sys
plan = json.load(open(sys.argv[1]))
root = pathlib.Path(sys.argv[2])
indices = plan[sys.argv[3]]
for index in indices:
    path = root / f"{index}.json"
    if not path.is_file():
        raise SystemExit(f"missing rc receipt: {index}")
    value = json.load(open(path))
    if value != {
        "index": index,
        "slurm_job_id": value.get("slurm_job_id"),
        "capability_rc": 0,
        "worker_rc": 0,
        "verifier_rc": 0,
        "safety_rc": 0,
    } or not isinstance(value["slurm_job_id"], str):
        raise SystemExit(f"nonzero/malformed rc receipt: {index}: {value}")
print(json.dumps({"indices": indices, "all_rc_zero": True}, sort_keys=True, separators=(",", ":")))
PY
}

event "MONITOR_START stage1=${stage_one_job} stage2=${stage_two_job}"
if ! wait_job_absent "$stage_one_job" STAGE1; then
  scancel "$stage_two_job" 2>/dev/null || true
  exit 3
fi
set +e
validate_indices stage_one_engineering_gate_indices \
  >"$run_root/preflight_stage1_gate.json" \
  2>"${external_log_root}/stage1_gate.stderr"
stage_one_gate_rc=$?
set -e
if [[ "$stage_one_gate_rc" != 0 ]]; then
  scancel "$stage_two_job" 2>/dev/null || true
  event "STAGE1_ENGINEERING_GATE_FAILED rc=${stage_one_gate_rc}; stage2_cancel_requested"
  printf '{"status":"E1_STOPPED_STAGE1_ENGINEERING_FAILURE","stage_one_gate_rc":%s,"sealed_values_opened":false}\n' \
    "$stage_one_gate_rc" >"$run_root/final_status.json"
  exit "$stage_one_gate_rc"
fi
cat >"$run_root/preflight_item10_pass.txt" <<'EOF'
PASS 10: both tasks completed one entire frozen replicate block; all four capability/worker/verifier/safety receipts are zero; stage two was gated only by Slurm afterok and these engineering receipts, never by D_search or D_val values
EOF
event "STAGE1_ENGINEERING_GATE_PASS sealed_values_opened=false"

if ! wait_job_absent "$stage_two_job" STAGE2; then
  exit 4
fi
set +e
validate_indices stage_two_remaining_indices \
  >"$run_root/preflight_stage2_gate.json" \
  2>"${external_log_root}/stage2_gate.stderr"
stage_two_gate_rc=$?
set -e
if [[ "$stage_two_gate_rc" != 0 ]]; then
  event "STAGE2_EXECUTION_GATE_FAILED rc=${stage_two_gate_rc} sealed_values_opened=false"
  printf '{"status":"E1_STOPPED_STAGE2_ENGINEERING_FAILURE","stage_two_gate_rc":%s,"sealed_values_opened":false}\n' \
    "$stage_two_gate_rc" >"$run_root/final_status.json"
  exit "$stage_two_gate_rc"
fi
event "COMPLETE_COVERAGE_ENGINEERING_GATE_PASS rollouts=8 sealed_values_opened=false"

sacct -j "${stage_one_job},${stage_two_job}" \
  --format=JobID,JobName,State,ExitCode,Elapsed,AllocTRES,NodeList -P \
  >"$run_root/slurm_accounting.txt" 2>"${external_log_root}/sacct.stderr" || true
cd "$source_root"
set +e
"$python_bin" -m phase1.verify_balanced_continuation_e1_collection \
  --assignment-result "$run_root/preparation/assignment" \
  --assignment-receipt "$run_root/preflight_receipts/assignment.verify.json" \
  --worker-output-root "$run_root/worker_outputs" \
  --worker-receipt-root "$run_root/worker_receipts" \
  --workspace-root "$run_root/workspaces" \
  --sealed-root "$run_root/sealed" \
  --real-contract "$run_root/preparation/real_contract.json" \
  --output "$run_root/collection" \
  >"${external_log_root}/collection.stdout" \
  2>"${external_log_root}/collection.stderr"
collection_rc=$?
set -e
printf '%s\n' "$collection_rc" >"$run_root/collection.rc"
if [[ "$collection_rc" != 0 ]]; then
  event "COLLECTION_FAILED rc=${collection_rc}"
  printf '{"status":"E1_COLLECTION_FAILED","collection_rc":%s}\n' "$collection_rc" \
    >"$run_root/final_status.json"
  exit "$collection_rc"
fi

filename_hits="$(find "$run_root/preparation" "$run_root/preflight_receipts" \
  "$run_root/worker_outputs" "$run_root/worker_receipts" "$run_root/sealed" \
  "$run_root/collection" "$run_root/capability" "$run_root/job_logs" "$run_root/slurm" \
  -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root/preparation" "$run_root/preflight_receipts" "$run_root/worker_outputs" \
  "$run_root/worker_receipts" "$run_root/sealed" "$run_root/collection" \
  "$run_root/capability" "$run_root/job_logs" "$run_root/slurm" | wc -l || true)"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then
  event "FINAL_SECRET_SCAN_FAILED filename=${filename_hits} content=${content_hits}"
  exit 7
fi
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"$run_root/final_safety_scan.txt"
summary_sha="$(sha256sum "$run_root/collection/summary.json" | awk '{print $1}')"
printf '{"status":"VERIFIED_COMPLETE_REAL_E1_COLLECTION","collection_rc":0,"collection_summary_sha256":"%s","primary_gate_claim_allowed":false,"e2_e3_unlocked":false}\n' \
  "$summary_sha" >"$run_root/final_status.json"

find \
  "$run_root/preparation" "$run_root/preflight_receipts" "$run_root/worker_outputs" \
  "$run_root/worker_receipts" "$run_root/sealed" "$run_root/job_rc" \
  "$run_root/collection" "$run_root/capability" "$run_root/job_logs" "$run_root/slurm" \
  -type f -print0 | sort -z | xargs -0 sha256sum >"$run_root/top_manifest.sha256"
find "$run_root/workspaces" -name workspace_marker.json -type f -print0 | sort -z | \
  xargs -0 sha256sum >>"$run_root/top_manifest.sha256"
sha256sum \
  "$run_root/source_commit.txt" "$run_root/data_gate_root.txt" \
  "$run_root/preflight_before_stage1.txt" "$run_root/preflight_item10_pass.txt" \
  "$run_root/preflight_matrix.json" "$run_root/preflight_safety_scan.txt" \
  "$run_root/final_safety_scan.txt" "$run_root/final_status.json" \
  >>"$run_root/top_manifest.sha256"
event "E1_COMPLETE summary_sha=${summary_sha} primary_gate_claim_allowed=false e2_e3_unlocked=false"
