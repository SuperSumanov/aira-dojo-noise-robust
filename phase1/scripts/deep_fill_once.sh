#!/usr/bin/env bash
# Submit the next deep-tree batch, if one is due and a QOS slot is free.
# Mirrors pool_fill_once.sh but drives the 23h deep regime off its own worklist/state.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
# L2 outranks collection for the shared 4-job QOS budget; l2_fill_once.sh clears this.
[ -f /research/d7/spc/yzyang4/scripts/.deep_hold ] && { echo "deep on hold (L2 has priority)"; exit 0; }
WL=/research/d7/spc/yzyang4/scripts/deep_worklist.txt
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/deep_submitted.txt
touch "$STATE"
n=$(squeue -u yzyang4 -h -n pool_deep -t R,PD -o %i 2>/dev/null | grep -vxF "${SLURM_JOB_ID:-none}" | wc -l)
[ "$n" -ge 1 ] && { echo "deep busy ($n)"; exit 0; }
next=$(while read -r s1 s2 tag t4 t5 rest; do
  [ -z "${tag:-}" ] && continue
  grep -qxF "$tag" "$STATE" 2>/dev/null || { echo "$s1 $s2 $tag $t4 $t5"; break; }
done < "$WL")
[ -z "$next" ] && { echo "deep worklist empty"; exit 0; }
set -- $next
CL=litellm_deepseek_flash; case "$3" in gen2*) CL=litellm_gen2;; gen3*) CL=litellm_gen3;; esac
sbatch --export=ALL,PC_S1=$1,PC_S2=$2,PC_TASKS_SC="$4",PC_EXECTO="${5:-7200}",PC_CLIENT=$CL,PC_RM=none,PC_ISSUE=mcts_deep_$3,PC_PAR=4,PC_DEBUG=false \
  /research/d7/spc/yzyang4/scripts/pool_collect_deep.sbatch
rc=$?
if [ $rc -eq 0 ]; then
  echo "$3" >> "$STATE"
  echo "$(date -u +%FT%TZ) submitted deep $3 seeds=[$1,$2] tasks=$4"
else
  echo "$(date -u +%FT%TZ) deep submit FAILED rc=$rc for $3 (QOS full?) - retry next heartbeat"
fi
