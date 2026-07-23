#!/usr/bin/env bash
# pool_fill_once.sh — keep exactly ONE self-chaining collection batch queued/running.
# Portable: set COLLECT_HOME (state/logs base) and DOJO_REPO (dojo-reproduce checkout). See HANDOFF doc.
set -u
: "${COLLECT_HOME:?export COLLECT_HOME=/research/.../<you>}"
: "${DOJO_REPO:?export DOJO_REPO=/path/to/aira-dojo-reproduce}"
SLURM_CONF_FILE="${SLURM_CONF:-/opt1/slurm/gpu-slurm.conf}"; export SLURM_CONF="$SLURM_CONF_FILE"
STATE_DIR="$COLLECT_HOME/collect_state"; LOGS="$COLLECT_HOME/logs"
mkdir -p "$STATE_DIR" "$LOGS"
WL="$STATE_DIR/pool_worklist.txt"
STATE="$STATE_DIR/pool_submitted.txt"
[ -f "$WL" ] || { cp "$DOJO_REPO/scripts/collect/pool_worklist.template.txt" "$WL"; echo "initialized worklist from template"; }
touch "$STATE"

n=$(squeue -u "$USER" -h -n pool_collect -t R,PD -o %i 2>/dev/null | grep -vxF "${SLURM_JOB_ID:-none}" | wc -l)
[ "$n" -ge 1 ] && { echo "pool busy ($n)"; exit 0; }
next=$(while read -r s1 s2 tag t4 t5 rest; do
  [ -z "${s1:-}" ] && continue; case "$s1" in \#*) continue;; esac
  grep -qF "$tag" "$STATE" 2>/dev/null || { echo "$s1 $s2 $tag ${t4:-} ${t5:-}"; break; }
done < "$WL")
[ -z "$next" ] && { echo "pool worklist empty"; exit 0; }
set -- $next
TS="${4:-}"; ET="${5:-1500}"
COMMON=(--export=ALL,PC_S1=$1,PC_S2=$2,PC_EXECTO=$ET,PC_ISSUE=mcts_data_$3${TS:+,PC_TASKS_SC=$TS}
        --output="$LOGS/pool_collect_%j.out"
        --account="${POOL_ACCOUNT:-gpu}" --qos="${POOL_QOS:-gpu}" --partition="${POOL_PARTITION:-gpu_8h}"
        --exclude="${POOL_EXCLUDE:-projgpu8,projgpu33,gpu36,gpu38}")
if sbatch "${COMMON[@]}" "$DOJO_REPO/scripts/collect/pool_collect.sbatch"; then
  echo "$3" >> "$STATE"
  echo "$(date -u +%FT%TZ) submitted $3 seeds=[$1,$2] tasks=${TS:-default-tabular} execto=$ET"
else
  echo "$(date -u +%FT%TZ) submit FAILED for $3 (QOS full?) — retry later (this script is safe to re-run/cron)"
fi
