#!/usr/bin/env bash
# The 2x2 that adjudicates the L2 contradiction: v2-trained and v3-trained models (seed 7,
# saved this time), each evaluated on BOTH flip sets offline afterwards. Separates "training
# data killed the budget behavior" from "the v2 eval split was the quirk". Fires only after
# all four T3 rounds have checkpointed -- T3 keeps GPU priority.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
S=/research/d7/spc/yzyang4/scripts
D=/research/d7/spc/yzyang4/aira-dojo/phase1
R0=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo
STATE=$S/.l2x2_submitted
[ -f "$STATE" ] && exit 0
for r in 1 2 3 4; do
  for a in c g; do
    n=$(find "$R0/user_yzyang4_issue_mcts_data_t3v2$a$r" -name journal.jsonl 2>/dev/null | wc -l)
    [ "$n" -ge 4 ] || exit 0
  done
done
B2="--pairs $D/budget_pairs_v2.jsonl --flip-eval $D/budget_flip_v2.jsonl --save-adapter $D/ckpt_l2_v2data"
B3="--pairs $D/budget_pairs_v3.jsonl --flip-eval $D/budget_flip_v3.jsonl --save-adapter $D/ckpt_l2_v3data"
C="--cards $D/cards_current.jsonl --sizes 8000 --max-len 2048 --eval-cap 2400 --eval-stratify --eval-len-control 0.15 --budget-cond --budget-pos tail"
if sbatch --job-name=l2x2 --export=ALL,ARM0="$B2 $C --out $D/l2x2_v2data.csv",ARM1="$B3 $C --out $D/l2x2_v3data.csv",SEED=7 "$S/train_pool.sbatch" >/dev/null 2>&1; then
  touch "$STATE"; echo "$(date -u +%FT%TZ) submitted l2 2x2 (both arms saved)"
else
  echo "l2x2: QOS full, retry next heartbeat"
fi
