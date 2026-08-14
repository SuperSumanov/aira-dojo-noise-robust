#!/usr/bin/env bash
set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set -u
umask 077

source_root="${1:?source root required}"
run_root="${2:?run root required}"
job_id="${3:?job id required}"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
events="${run_root}/monitor_events.txt"

printf '%s MONITOR_START job=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$job_id" >>"$events"
while squeue -h -j "$job_id" | grep -q .; do
  sleep 20
done
printf '%s SLURM_TERMINAL job=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$job_id" >>"$events"
sacct -j "$job_id" --parsable2 --noheader --format=JobIDRaw,State,ExitCode,Elapsed,AllocTRES >"${run_root}/slurm_accounting.txt"

verify_rc=-1
if [[ -f "${run_root}/job_rc/0.json" && -f "${run_root}/job_rc/1.json" ]]; then
  set +e
  PYTHONPATH="$source_root" "$python_bin" -m phase1.verify_balanced_continuation_qwen_execution_smoke --source-root "$source_root" --source-run-root /research/d7/spc/yzyang4/balanced-e1-real-e59a759d-a1 --probe-root /research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1 --output-root "${run_root}/outputs" --workspace-root "${run_root}/workspaces" --job-rc-root "${run_root}/job_rc" --receipt "${run_root}/independent_verification.json" >"${run_root}/verifier.stdout" 2>"${run_root}/verifier.stderr"
  verify_rc=$?
  set -e
fi
printf '%s VERIFY_DONE rc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$verify_rc" >>"$events"
printf '%s\n' "$verify_rc" >"${run_root}/verifier.rc"
if [[ "$verify_rc" != 0 ]]; then
  exit "$verify_rc"
fi
printf '%s MONITOR_DONE\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$events"
