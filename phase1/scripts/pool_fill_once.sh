#!/usr/bin/env bash
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
WL=/research/d7/spc/yzyang4/scripts/pool_worklist.txt
STATE=/research/d7/spc/yzyang4/aira-dojo-runs/pool_submitted.txt
n=$(squeue -u yzyang4 -h -n pool_collect -t R,PD -o %i 2>/dev/null | grep -vxF "${SLURM_JOB_ID:-none}" | wc -l)
[ "$n" -ge 1 ] && { echo "pool busy ($n)"; exit 0; }
next=$(while read -r s1 s2 tag t4 t5 rest; do grep -qF "$tag" "$STATE" 2>/dev/null || { echo "$s1 $s2 $tag $t4 $t5"; break; }; done < "$WL")
[ -z "$next" ] && { echo "pool worklist empty"; exit 0; }
set -- $next
# balance guard: refuse to burn a batch the account cannot finish (provider by tag)
PROV=deepseek; FLOOR=25; case "$3" in gen2*) PROV=qwen; FLOOR=0;; esac
if ! /research/d7/spc/yzyang4/venvs/critic/bin/python3 \
     /research/d7/spc/yzyang4/scripts/balance_guard.py "$PROV" "$FLOOR"; then
  echo "$(date -u +%FT%TZ) HOLD $3: $PROV balance below floor"
  exit 0
fi
TS="${4:-}"
ET="${5:-1500}"
if [ -n "$TS" ]; then
  CL=litellm_deepseek_flash; case "$3" in gen2*) CL=litellm_gen2;; gen3*) CL=litellm_gen3;; esac
  RM=none; case "$3" in t3g*) RM=local;; esac
  sbatch --export=ALL,PC_S1=$1,PC_S2=$2,PC_TASKS_SC=$TS,PC_EXECTO=$ET,PC_CLIENT=$CL,PC_RM=$RM,PC_ISSUE=mcts_data_$3,PC_PAR=4,PC_DEBUG=false /research/d7/spc/yzyang4/scripts/pool_collect.sbatch
else
  CL2=litellm_deepseek_flash; case "$3" in gen2*) CL2=litellm_gen2;; gen3*) CL2=litellm_gen3;; esac
  RM2=none; case "$3" in t3g*) RM2=local;; esac
  sbatch --export=ALL,PC_S1=$1,PC_S2=$2,PC_CLIENT=$CL2,PC_RM=$RM2,PC_ISSUE=mcts_data_$3,PC_PAR=4,PC_DEBUG=false /research/d7/spc/yzyang4/scripts/pool_collect.sbatch
fi
rc=$?
if [ $rc -eq 0 ]; then
  echo "$3" >> "$STATE"
  echo "$(date -u +%FT%TZ) submitted $3 seeds=[$1,$2] tasks=${TS:-default-tabular}"
else
  echo "$(date -u +%FT%TZ) submit FAILED rc=$rc for $3 (QOS full?) - will retry on next heartbeat"
fi
