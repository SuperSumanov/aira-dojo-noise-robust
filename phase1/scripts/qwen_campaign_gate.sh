#!/usr/bin/env bash
# Persistent heartbeat for the Qwen (gen2Q*) cross-generator campaign.
#
# Two gaps this closes, both found in preflight 2026-08-08:
#   1. pool_collect.sbatch chains the next batch by calling pool_fill_once.sh at exit, but a
#      submit that hits the 4-job QOS cap only prints "will retry on next heartbeat" -- and
#      no heartbeat existed, so the chain died silently.
#   2. The campaign must stop on its own at a batch cap; the account exposes no balance
#      readout, so batch count is the spend control.
#
# Idempotent: pool_fill_once.sh records submitted tags in pool_submitted.txt and refuses to
# run while a pool_collect job exists, so a duplicate heartbeat cannot double-submit.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
LOG=/research/d7/spc/yzyang4/logs/qwen_campaign.log
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/pool_submitted.txt
CAP="${QWEN_CAP:-8}"          # max gen2Q batches this campaign may submit
echo "$(date -u +%FT%TZ) qwen campaign heartbeat up (cap=$CAP)" >> "$LOG"

while :; do
  done_n=$(grep -c '^gen2Q' "$STATE" 2>/dev/null || echo 0)
  if [ "$done_n" -ge "$CAP" ]; then
    echo "$(date -u +%FT%TZ) cap reached ($done_n/$CAP) -- heartbeat exiting" >> "$LOG"
    exit 0
  fi
  njobs=$(squeue -u yzyang4 -h 2>/dev/null | wc -l)
  npool=$(squeue -u yzyang4 -h -n pool_collect -t R,PD 2>/dev/null | wc -l)
  if [ "$njobs" -lt 4 ] && [ "$npool" -lt 1 ]; then
    echo "$(date -u +%FT%TZ) slot free (jobs=$njobs) submitted=$done_n/$CAP" >> "$LOG"
    bash /research/d7/spc/yzyang4/scripts/pool_fill_once.sh >> "$LOG" 2>&1
  fi
  sleep 600
done
