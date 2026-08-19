#!/usr/bin/env bash
# Score-blind monitor for the six-task E2-A warm-only smoke.
set -eo pipefail
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ $# -ne 3 ]]; then echo "usage: $0 SOURCE_ROOT PREPARATION RUN_ROOT" >&2; exit 2; fi
source_root="$1"
preparation="$2"
run_root="$3"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
job_id="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["job_id"])' "$run_root/submission.json")"
events="$run_root/monitor_events.log"
event() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$events"; }
deadline=$(( $(date +%s) + 10800 ))
event "MONITOR_START job=${job_id} scores_opened=false labels_opened=false"
while squeue -h -j "$job_id" 2>/dev/null | grep -q .; do
  if (( $(date +%s) >= deadline )); then
    event "MONITOR_TIMEOUT job=${job_id}"
    printf '{"status":"E2A_WARM_SMOKE_MONITOR_TIMEOUT","job_id":"%s"}\n' "$job_id" \
      >"$run_root/final_status.json"
    exit 3
  fi
  sleep 30
done
sacct -X -n -P -j "$job_id" -o JobID,State,ExitCode,Elapsed,NodeList \
  >"$run_root/slurm_accounting.txt" 2>"$run_root/slurm_accounting.stderr" || true
event "JOB_TERMINAL job=${job_id}"

cd "$source_root"
set +e
"$python_bin" -m phase1.verify_balanced_continuation_e2a_warm_smoke_collection \
  --run-root "$run_root" --preparation "$preparation" \
  --receipt "$run_root/warm_smoke_gate.verify.json" \
  >"$run_root/logs/collection_verify.stdout" \
  2>"$run_root/logs/collection_verify.stderr"
gate_rc=$?
set -e
printf '%s\n' "$gate_rc" >"$run_root/warm_smoke_gate.rc"
if [[ "$gate_rc" != 0 ]]; then
  event "WARM_SMOKE_GATE_FAILED rc=${gate_rc}; formal_submission_forbidden=true"
  printf '{"status":"E2A_WARM_SMOKE_GATE_FAILED","gate_rc":%s,"formal_submission_allowed":false,"scores_opened":false,"labels_opened":false}\n' \
    "$gate_rc" >"$run_root/final_status.json"
  exit "$gate_rc"
fi

filename_hits="$(find "$run_root/outputs" "$run_root/receipts" "$run_root/capability" \
  "$run_root/logs" "$run_root/job_rc" -type f -printf '%f\n' \
  | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root/outputs" "$run_root/receipts" "$run_root/capability" \
  "$run_root/logs" "$run_root/job_rc" | wc -l || true)"
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' \
  "$filename_hits" "$content_hits" >"$run_root/final_secret_scan.txt"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then
  event "FINAL_SECRET_SCAN_FAILED filename=${filename_hits} content=${content_hits}"
  exit 7
fi
gate_sha="$(sha256sum "$run_root/warm_smoke_gate.verify.json" | cut -d' ' -f1)"
printf '{"status":"VERIFIED_E2A_SIX_TASK_PUBLIC_WARM_SMOKE_PASS","job_id":"%s","candidate_executions":6,"api_calls":0,"formal_submission_allowed":true,"scores_opened":false,"labels_opened":false,"gate_receipt_sha256":"%s"}\n' \
  "$job_id" "$gate_sha" >"$run_root/final_status.json"
find "$run_root" -type f ! -name top_manifest.sha256 -print0 | sort -z | \
  xargs -0 sha256sum >"$run_root/top_manifest.sha256"
event "WARM_SMOKE_GATE_PASS formal_submission_allowed=true gate_sha=${gate_sha}"
