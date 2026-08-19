#!/usr/bin/env bash
# QOS-aware, score-blind two-wave E2-A monitor; opens D_val only after 60/60 coverage.
set -eo pipefail
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ $# -ne 3 ]]; then echo "usage: $0 RUN_ROOT SOURCE_ROOT DATA_GATE" >&2; exit 2; fi
run_root="$1"
source_root="$2"
data_gate="$3"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
events="$run_root/monitor_events.log"
credential_env=/research/d7/spc/yzyang4/aira-dojo/.env
if [[ ! -f "$credential_env" || -L "$credential_env" \
  || "$(stat -c %a "$credential_env")" != 600 ]]; then exit 2; fi
if ! (
  set -a
  source "$credential_env"
  set +a
  [[ -n "${PRIMARY_KEY_QWEN3_CODER_FLASH:-}" ]]
); then exit 2; fi
engineering="$($python_bin -c 'import json,sys;print(",".join(map(str,json.load(open(sys.argv[1]))["engineering_wave_indices"])))' "$run_root/preparation/run_plan.json")"
remaining="$($python_bin -c 'import json,sys;print(",".join(map(str,json.load(open(sys.argv[1]))["remaining_wave_indices"])))' "$run_root/preparation/run_plan.json")"
export_spec="E2A_RUN_ROOT=${run_root},E2A_SOURCE_ROOT=${source_root},E2A_DATA_GATE_ROOT=${data_gate}"
submission_deadline=$(( $(date +%s) + 28800 ))
submitted_job=""
event() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$events"; }

submit_wave() {
  local wave="$1" indices="$2" dependency="$3" attempt=0 output rc error_path
  local -a dependency_args=()
  if [[ "$dependency" != none ]]; then dependency_args=(--dependency "$dependency"); fi
  while (( $(date +%s) < submission_deadline )); do
    attempt=$((attempt + 1))
    error_path="$run_root/logs/${wave}_submit_${attempt}.stderr"
    set +e
    output="$(sbatch --parsable --job-name="e2a_${wave}" \
      "${dependency_args[@]}" --array="${indices}%4" --export="$export_spec" \
      --output="$run_root/slurm/${wave}_%A_%a.out" \
      --error="$run_root/slurm/${wave}_%A_%a.err" \
      "$run_root/job.sbatch" 2>"$error_path")"
    rc=$?
    set -e
    if [[ "$rc" = 0 && "$output" =~ ^[0-9]+(;.*)?$ ]]; then
      submitted_job="${output%%;*}"
      printf '{"status":"E2A_WAVE_SUBMITTED","wave":"%s","job_id":"%s","indices":"%s","dependency":"%s","qos_attempts":%s}\n' \
        "$wave" "$submitted_job" "$indices" "$dependency" "$attempt" \
        >"$run_root/${wave}_submission.json"
      event "${wave}_SUBMITTED job=${submitted_job} attempts=${attempt} dependency=${dependency}"
      return 0
    fi
    if [[ -z "$output" ]] && grep -qE \
      'QOSMaxSubmitJobPerUserLimit|Job violates accounting/QOS policy' "$error_path"; then
      if (( attempt == 1 || attempt % 5 == 0 )); then
        event "${wave}_QOS_WAIT attempt=${attempt} no_job_id_observed=true"
      fi
      sleep 60
      continue
    fi
    event "${wave}_SUBMISSION_FAILED rc=${rc} attempt=${attempt} no_retry=true"
    return 1
  done
  event "${wave}_QOS_TIMEOUT attempts=${attempt} no_job_id_observed=true"
  return 1
}

wait_job() {
  local job_id="$1" wave="$2" deadline=$(( $(date +%s) + 21600 )) states
  while true; do
    if squeue -h -j "$job_id" 2>/dev/null | grep -q .; then sleep 30; continue; fi
    states="$(sacct -X -n -P -j "$job_id" -o State 2>/dev/null || true)"
    if printf '%s\n' "$states" | grep -qE \
      '^(COMPLETED|FAILED|CANCELLED|TIMEOUT|NODE_FAIL|OUT_OF_MEMORY|PREEMPTED|BOOT_FAIL|DEADLINE)'; then
      event "${wave}_TERMINAL job=${job_id}"
      return 0
    fi
    if (( $(date +%s) >= deadline )); then event "${wave}_MONITOR_TIMEOUT"; return 1; fi
    sleep 5
  done
}

validate_wave() {
  local key="$1" output="$2"
  "$python_bin" -c 'import json,pathlib,sys;p=json.load(open(sys.argv[1]));root=pathlib.Path(sys.argv[2]);indices=p[sys.argv[3]]; rows=[]
for i in indices:
 q=root/f"{i}.json"
 if not q.is_file(): raise SystemExit(f"missing rc {i}")
 v=json.load(open(q)); expected={"index":i,"rollout_id":v.get("rollout_id"),"task":v.get("task"),"slurm_job_id":v.get("slurm_job_id"),"capability_rc":0,"worker_rc":0,"verifier_rc":0,"safety_rc":0}
 if v!=expected or not all(isinstance(v.get(k),str) and v[k] for k in ("rollout_id","task","slurm_job_id")): raise SystemExit(f"bad rc {i}: {v}")
 rows.append(v)
json.dump({"status":"E2A_SCORE_BLIND_WAVE_PASS","indices":indices,"all_rc_zero":True,"scores_opened":False,"sealed_values_opened":False},open(sys.argv[4],"w"),sort_keys=True,separators=(",",":"));open(sys.argv[4],"a").write("\n")' \
    "$run_root/preparation/run_plan.json" "$run_root/job_rc" "$key" "$output"
}

event "MONITOR_START engineering=${engineering} remaining=${remaining} scores_opened=false sealed_values_opened=false"
if ! submit_wave engineering "$engineering" none; then exit 3; fi
engineering_job="$submitted_job"
if ! wait_job "$engineering_job" ENGINEERING; then exit 3; fi
set +e
validate_wave engineering_wave_indices "$run_root/engineering_gate.verify.json" \
  2>"$run_root/logs/engineering_gate.stderr"
engineering_rc=$?
set -e
if [[ "$engineering_rc" != 0 ]]; then
  event "ENGINEERING_GATE_FAILED rc=${engineering_rc}; remaining_not_submitted=true"
  printf '{"status":"E2A_STOPPED_ENGINEERING_FAILURE","formal_coverage_complete":false,"scores_opened":false,"sealed_values_opened":false}\n' \
    >"$run_root/final_status.json"
  exit "$engineering_rc"
fi
event "ENGINEERING_GATE_PASS scores_opened=false sealed_values_opened=false"

if ! submit_wave remaining "$remaining" "afterok:${engineering_job}"; then exit 4; fi
remaining_job="$submitted_job"
if ! wait_job "$remaining_job" REMAINING; then exit 4; fi
set +e
validate_wave remaining_wave_indices "$run_root/remaining_gate.verify.json" \
  2>"$run_root/logs/remaining_gate.stderr"
remaining_rc=$?
set -e
if [[ "$remaining_rc" != 0 ]]; then
  event "REMAINING_GATE_FAILED rc=${remaining_rc}; sealed_values_opened=false"
  printf '{"status":"E2A_STOPPED_REMAINING_FAILURE","formal_coverage_complete":false,"scores_opened":false,"sealed_values_opened":false}\n' \
    >"$run_root/final_status.json"
  exit "$remaining_rc"
fi
event "COMPLETE_COVERAGE_GATE_PASS rollouts=60 candidate_attempts=120 operator_calls=60 sealed_values_opened=false"

cd "$source_root"
set +e
"$python_bin" -m phase1.verify_balanced_continuation_e2a_collection \
  --assignment-result "$run_root/preparation/assignment" \
  --assignment-receipt "$run_root/preflight_receipts/assignment.verify.json" \
  --worker-output-root "$run_root/worker_outputs" \
  --worker-receipt-root "$run_root/worker_receipts" \
  --workspace-root "$run_root/workspaces" --sealed-root "$run_root/sealed" \
  --real-contract "$run_root/preparation/real_contract.json" \
  --output "$run_root/collection" \
  >"$run_root/logs/collection.stdout" 2>"$run_root/logs/collection.stderr"
collection_rc=$?
set -e
printf '%s\n' "$collection_rc" >"$run_root/collection.rc"
if [[ "$collection_rc" != 0 ]]; then
  event "COLLECTION_FAILED rc=${collection_rc}"
  exit "$collection_rc"
fi
set +e
"$python_bin" -m phase1.verify_balanced_continuation_e2a_archive \
  --result-dir "$run_root/collection" \
  --output "$run_root/collection.independent.verify.json" \
  >"$run_root/logs/archive_verify.stdout" 2>"$run_root/logs/archive_verify.stderr"
archive_rc=$?
set -e
printf '%s\n' "$archive_rc" >"$run_root/archive_verify.rc"
if [[ "$archive_rc" != 0 ]]; then
  event "INDEPENDENT_ARCHIVE_VERIFICATION_FAILED rc=${archive_rc}"
  exit "$archive_rc"
fi

sacct -j "${engineering_job},${remaining_job}" \
  --format=JobID,JobName,State,ExitCode,Elapsed,AllocTRES,NodeList -P \
  >"$run_root/slurm_accounting.txt" 2>"$run_root/logs/sacct.stderr" || true
filename_hits="$(find "$run_root/preparation" "$run_root/preflight_receipts" \
  "$run_root/worker_outputs" "$run_root/worker_receipts" "$run_root/sealed" \
  "$run_root/collection" "$run_root/capability" "$run_root/job_logs" \
  "$run_root/collection.independent.verify.json" \
  -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
content_hits="$(grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
  "$run_root/preparation" "$run_root/preflight_receipts" \
  "$run_root/worker_outputs" "$run_root/worker_receipts" "$run_root/sealed" \
  "$run_root/collection" "$run_root/capability" "$run_root/job_logs" \
  "$run_root/collection.independent.verify.json" | wc -l || true)"
printf 'FILENAME_SECRET_HITS=%s\nCONTENT_SECRET_HITS=%s\n' "$filename_hits" "$content_hits" \
  >"$run_root/final_secret_scan.txt"
if [[ "$filename_hits" != 0 || "$content_hits" != 0 ]]; then exit 7; fi
verdict="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["verdict"])' "$run_root/collection/summary.json")"
summary_sha="$(sha256sum "$run_root/collection/summary.json" | cut -d' ' -f1)"
archive_sha="$(sha256sum "$run_root/collection.independent.verify.json" | cut -d' ' -f1)"
printf '{"status":"VERIFIED_COMPLETE_REAL_E2A_COLLECTION","verdict":"%s","collection_summary_sha256":"%s","independent_archive_receipt_sha256":"%s","primary_method_claim_allowed":false,"post_outcome_replacement_count":0}\n' \
  "$verdict" "$summary_sha" "$archive_sha" >"$run_root/final_status.json"
find "$run_root" -type f ! -name top_manifest.sha256 -print0 | sort -z | \
  xargs -0 sha256sum >"$run_root/top_manifest.sha256"
event "E2A_COMPLETE verdict=${verdict} summary_sha=${summary_sha} primary_method_claim_allowed=false"
