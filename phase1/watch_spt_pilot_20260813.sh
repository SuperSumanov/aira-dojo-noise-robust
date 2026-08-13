#!/usr/bin/env bash
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

if [[ $# -ne 1 ]]; then
  echo "usage: $0 JOB_ID" >&2
  exit 2
fi
job_id=$1
ops=/research/d7/spc/yzyang4/spt_ops/spt_label_blind_pilot_v1
log="$ops/watcher.log"

printf '%s WATCH_START job=%s\n' "$(date --iso-8601=seconds)" "$job_id" >> "$log"
while squeue -h -j "$job_id" | grep -q .; do
  row=$(squeue -h -j "$job_id" -o '%i|%T|%M|%N' | head -n 1)
  printf '%s queue=%s results=%s status=%s\n' \
    "$(date --iso-8601=seconds)" "$row" \
    "$(find "$ops/results" -mindepth 2 -maxdepth 2 -name result.json 2>/dev/null | wc -l)" \
    "$(find "$ops/status" -maxdepth 1 -name 'index_*.json' 2>/dev/null | wc -l)" >> "$log"
  sleep 300
done
accounting=$(sacct -n -P -j "$job_id" --format=JobIDRaw,State,ExitCode,Elapsed,AllocTRES | head -n 1)
printf '%s accounting=%s\n' "$(date --iso-8601=seconds)" "$accounting" >> "$log"
if [[ -f "$ops/analysis/verdict.txt" ]]; then
  printf '%s verdict=%s\n' "$(date --iso-8601=seconds)" \
    "$(tr -d '[:space:]' < "$ops/analysis/verdict.txt")" >> "$log"
else
  printf '%s verdict=NO_ANALYSIS\n' "$(date --iso-8601=seconds)" >> "$log"
fi
