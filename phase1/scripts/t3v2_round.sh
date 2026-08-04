#!/usr/bin/env bash
# One T3v2 round = one control batch + one guided batch, paired seeds, per the pre-registered
# protocol (phase1/实验记录/2026-08-04/T3v2_预注册.md). NOT gated into the heartbeat: the
# protocol requires the sidecar smoke to pass before round 1, so launches stay manual.
#
# Usage: bash t3v2_round.sh <round: 1..4>
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
CKPT=/research/d7/spc/yzyang4/aira-dojo/phase1/ckpt_lookahead_v3/N24000
R=${1:?round number 1..4}
case $R in
  1) S1=905; S2=906;;
  2) S1=907; S2=908;;
  3) S1=909; S2=910;;
  4) S1=911; S2=912;;
  *) echo "round must be 1..4"; exit 1;;
esac
[ -f "$CKPT/rm_meta.json" ] || { echo "ABORT: checkpoint not ready at $CKPT"; exit 1; }
source ~/env_setup.sh >/dev/null 2>&1
/research/d7/spc/yzyang4/venvs/critic/bin/python3 $S/balance_guard.py deepseek 10 || { echo "ABORT: balance"; exit 1; }
TASKS="spooky-author-identification;tabular-playground-series-dec-2021"
sbatch --export=ALL,PC_S1=$S1,PC_S2=$S2,PC_TASKS_SC="$TASKS",PC_EXECTO=1500,PC_CLIENT=litellm_deepseek_flash,PC_RM=none,PC_ISSUE=mcts_data_t3v2c$R,PC_PAR=4,PC_DEBUG=false $S/pool_collect.sbatch
sbatch --export=ALL,PC_S1=$S1,PC_S2=$S2,PC_TASKS_SC="$TASKS",PC_EXECTO=1500,PC_CLIENT=litellm_deepseek_flash,PC_RM=local,PC_RM_DIR=$CKPT,PC_ISSUE=mcts_data_t3v2g$R,PC_PAR=4,PC_DEBUG=false $S/pool_collect.sbatch
echo "round $R submitted (control t3v2c$R + guided t3v2g$R, seeds $S1/$S2)"
