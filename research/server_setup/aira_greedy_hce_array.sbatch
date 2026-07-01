#!/bin/bash
#SBATCH --job-name=t1_arr
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --cpus-per-task=6
#SBATCH --time=05:00:00
#SBATCH --array=0-29%4
#SBATCH --output=/research/d7/spc/yzyang4/aira-dojo-runs/t1_arr_%A_%a.out
#SBATCH --error=/research/d7/spc/yzyang4/aira-dojo-runs/t1_arr_%A_%a.out

source ~/env_setup.sh
VENV=/research/d7/spc/yzyang4/venvs/aira
export PATH="$VENV/bin:$PATH"
cd /research/d7/spc/yzyang4/aira-dojo || exit 1

# 30 combos = TASKS(2) x ARMS(3) x SEEDS(5).  idx -> (task, arm, seed)
TASKS=(spaceship-titanic nomad2018-predict-transparent-conductors)
EXPS=(mlebench/deepseek_greedy_hce_spaceship mlebench/deepseek_greedy_hce_nomad)
ARMS=(full naive consistency)
IDX=${SLURM_ARRAY_TASK_ID}
ti=$(( IDX / 15 ))
ai=$(( (IDX % 15) / 5 ))
SEED=$(( (IDX % 5) + 1 ))
TASK=${TASKS[$ti]}; EXP=${EXPS[$ti]}; ARM=${ARMS[$ai]}
ISSUE="t1_${ARM}_${TASK}"

# resumable: skip if this combo already produced a journal
if ls /research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo/user_yzyang4_issue_${ISSUE}/*seed_${SEED}_*/checkpoint/journal.jsonl >/dev/null 2>&1; then
  echo "SKIP idx=$IDX $ISSUE seed=$SEED already has a journal"; exit 0
fi

echo "=== T1 array idx=$IDX task=$TASK arm=$ARM seed=$SEED issue=$ISSUE on $(hostname) ==="; date -u +%FT%TZ
CUDA_VISIBLE_DEVICES=0 "$VENV/bin/python" -m dojo.main_run +_exp=$EXP \
  task.arm=$ARM \
  logger.use_wandb=False \
  metadata.git_issue_id=$ISSUE \
  metadata.seed="$SEED" \
  solver.step_limit=20 \
  solver.time_limit_secs=14400
echo "T1_ARR_${IDX}_DONE rc=$? $(date -u +%FT%TZ)"
