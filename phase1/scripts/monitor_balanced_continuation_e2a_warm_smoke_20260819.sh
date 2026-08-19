#!/usr/bin/env bash
# QOS-aware score-blind 4+2 monitor for the six-task E2-A warm smoke.
set -eo pipefail
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ $# -ne 3 ]]; then echo "usage: $0 SOURCE_ROOT PREPARATION RUN_ROOT" >&2; exit 2; fi
source_root="$1"
preparation="$2"
run_root="$3"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
data_gate="$(cat "$run_root/data_gate_root.txt")"
events="$run_root/monitor_events.log"
MAX_SUBMITTED_TASKS=4
chunks=("0,1,2,3" "4,5")
export_spec="HOME=/uac/y24/yzyang4,E2S_RUN_ROOT=${run_root},E2S_SOURCE_ROOT=${source_root},E2S_DATA_GATE_ROOT=${data_gate},E2S_PREPARATION=${preparation}"
submission_deadline=$(( $(date +%s) + 43200 ))
submitted_job=""
declare -a job_ids=()
event() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$events"; }

submit_chunk() {
  local sequence="$1" indices="$2" attempt=0 output rc error_path
  while (( $(date +%s) < submission_deadline )); do
    attempt=$((attempt + 1))
    error_path="$run_root/logs/chunk_${sequence}_submit_${attempt}.stderr"
    set +e
    output="$(sbatch --parsable --job-name="e2a_warm_${sequence}" \
      --array="$indices" --export="$export_spec" \
      --output="$run_root/slurm/chunk_${sequence}_%A_%a.out" \
      --error="$run_root/slurm/chunk_${sequence}_%A_%a.err" \
      "$run_root/job.sbatch" 2>"$error_path")"
    rc=$?
    set -e
    if [[ "$rc" = 0 && "$output" =~ ^[0-9]+(;.*)?$ ]]; then
      submitted_job="${output%%;*}"
      printf '{"status":"E2A_WARM_CHUNK_SUBMITTED","sequence":%s,"job_id":"%s","indices":"%s","qos_attempts":%s}\n' \
        "$sequence" "$submitted_job" "$indices" "$attempt" \
        >"$run_root/chunk_${sequence}_submission.json"
      event "CHUNK_SUBMITTED sequence=${sequence} indices=${indices} job=${submitted_job} attempts=${attempt}"
      return 0
    fi
    if [[ -z "$output" ]] && grep -qE \
      'QOSMaxSubmitJobPerUserLimit|Job violates accounting/QOS policy' "$error_path"; then
      if (( attempt == 1 || attempt % 5 == 0 )); then
        event "CHUNK_QOS_WAIT sequence=${sequence} attempt=${attempt} no_job_id_observed=true"
      fi
      sleep 60
      continue
    fi
    event "CHUNK_SUBMISSION_FAILED sequence=${sequence} rc=${rc} attempt=${attempt} no_retry=true"
    return 1
  done
  event "CHUNK_QOS_TIMEOUT sequence=${sequence} attempts=${attempt} no_job_id_observed=true"
  return 1
}

wait_job() {
  local job_id="$1" sequence="$2" deadline=$(( $(date +%s) + 10800 )) states
  while true; do
    if squeue -h -j "$job_id" 2>/dev/null | grep -q .; then sleep 30; continue; fi
    states="$(sacct -X -n -P -j "$job_id" -o State 2>/dev/null || true)"
    if printf '%s\n' "$states" | grep -qE \
      '^(COMPLETED|FAILED|CANCELLED|TIMEOUT|NODE_FAIL|OUT_OF_MEMORY|PREEMPTED|BOOT_FAIL|DEADLINE)'; then
      event "CHUNK_TERMINAL sequence=${sequence} job=${job_id}"
      return 0
    fi
    if (( $(date +%s) >= deadline )); then
      event "CHUNK_MONITOR_TIMEOUT sequence=${sequence} job=${job_id}"
      return 1
    fi
    sleep 5
  done
}

validate_chunk() {
  local indices="$1" output="$2"
  "$python_bin" -c 'import json,pathlib,sys; plan=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2]); indices=[int(x) for x in sys.argv[3].split(",")]; rows=[]
for i in indices:
 p=root/f"{i}.json"
 if not p.is_file(): raise SystemExit(f"missing rc {i}")
 v=json.load(open(p)); expected={"slot":i,"assignment_index":plan["warm_smoke_assignment_indices"][i],"task":plan["warm_smoke_tasks"][i],"slurm_job_id":v.get("slurm_job_id"),"capability_rc":0,"producer_rc":0,"verifier_rc":0,"safety_rc":0}
 if v!=expected or not all(isinstance(v.get(k),str) and v[k] for k in ("task","slurm_job_id")): raise SystemExit(f"bad rc {i}: {v}")
 rows.append(v)
json.dump({"status":"E2A_WARM_SCORE_BLIND_CHUNK_PASS","indices":indices,"all_rc_zero":True,"scores_opened":False,"labels_opened":False},open(sys.argv[4],"w"),sort_keys=True,separators=(",",":"));open(sys.argv[4],"a").write("\n")' \
    "$preparation/run_plan.json" "$run_root/job_rc" "$indices" "$output"
}

event "MONITOR_START chunks=4+2 max_submitted_tasks=${MAX_SUBMITTED_TASKS} scores_opened=false labels_opened=false"
for sequence in 0 1; do
  indices="${chunks[$sequence]}"
  if (( $(tr -cd ',' <<<"$indices" | wc -c) + 1 > MAX_SUBMITTED_TASKS )); then exit 2; fi
  if ! submit_chunk "$sequence" "$indices"; then exit 3; fi
  job_id="$submitted_job"
  job_ids+=("$job_id")
  if ! wait_job "$job_id" "$sequence"; then exit 3; fi
  if ! validate_chunk "$indices" "$run_root/chunk_${sequence}_score_blind.verify.json" \
    2>"$run_root/logs/chunk_${sequence}_gate.stderr"; then
    event "CHUNK_GATE_FAILED sequence=${sequence}; later_chunks_not_submitted=true"
    printf '{"status":"E2A_WARM_CHUNK_FAILED","sequence":%s,"formal_submission_allowed":false,"scores_opened":false,"labels_opened":false}\n' \
      "$sequence" >"$run_root/final_status.json"
    exit 4
  fi
done
printf '{"status":"E2A_WARM_SMOKE_ALL_CHUNKS_COMPLETE","job_ids":["%s","%s"],"chunks":["0,1,2,3","4,5"],"max_submitted_tasks":4,"candidate_executions":6,"api_calls":0}\n' \
  "${job_ids[0]}" "${job_ids[1]}" >"$run_root/submission.json"
job_csv="${job_ids[0]},${job_ids[1]}"
sacct -X -n -P -j "$job_csv" -o JobID,State,ExitCode,Elapsed,NodeList \
  >"$run_root/slurm_accounting.txt" 2>"$run_root/slurm_accounting.stderr" || true
event "COMPLETE_COVERAGE_GATE_PASS candidate_executions=6 api_calls=0 scores_opened=false labels_opened=false"

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
printf '{"status":"VERIFIED_E2A_SIX_TASK_PUBLIC_WARM_SMOKE_PASS","job_ids":["%s","%s"],"candidate_executions":6,"api_calls":0,"formal_submission_allowed":true,"scores_opened":false,"labels_opened":false,"gate_receipt_sha256":"%s"}\n' \
  "${job_ids[0]}" "${job_ids[1]}" "$gate_sha" >"$run_root/final_status.json"
find "$run_root" -type f ! -name top_manifest.sha256 -print0 | sort -z | \
  xargs -0 sha256sum >"$run_root/top_manifest.sha256"
event "WARM_SMOKE_GATE_PASS formal_submission_allowed=true gate_sha=${gate_sha}"
