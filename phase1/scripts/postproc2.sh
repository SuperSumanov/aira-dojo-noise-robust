#!/usr/bin/env bash
# Second-wave post-processing for the 8-hour unattended window. Cluster-side so a client
# crash costs nothing: by the time anyone looks, the analyses exist.
#   qwen judge (full program context) -> analysis, fixing the 38%-coverage fairness flaw
#   whale/leaf LOTO folds             -> C2 extension (12 folds; primary 10-fold stays frozen)
#   ctx 05b8192                       -> suite refresh with every trained cell present
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
A=/research/d7/spc/yzyang4/aira-dojo
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
L=/research/d7/spc/yzyang4/logs/postproc2.log
cd "$A" || exit 1
echo "$(date -u +%FT%TZ) postproc2 up" >> "$L"
for i in $(seq 1 110); do
  if [ -f phase1/judge_qwen_full.jsonl ] && ! pgrep -f llm_judge >/dev/null \
     && [ ! -f phase1/.qjudge_done ]; then
    $P phase1/judge_analyze.py phase1/judge_qwen_full.jsonl \
       --dump phase1/judge_scores_qwen.json > phase1/judge_qwen_report.txt 2>&1
    touch phase1/.qjudge_done
    echo "$(date -u +%FT%TZ) qwen judge analysed" >> "$L"
  fi
  nf=$(grep -c '^4000,loto:' phase1/loto_v4.csv 2>/dev/null || echo 0)
  if [ "$nf" -ge 12 ] && [ ! -f phase1/.c2ext_done ]; then
    $P phase1/c2_verdict.py > phase1/c2_verdict_12fold.txt 2>&1
    touch phase1/.c2ext_done
    echo "$(date -u +%FT%TZ) C2 recomputed at $nf folds" >> "$L"
  fi
  if [ -f phase1/ctx_sweep.csv ] && [ ! -f phase1/.suite_v3 ] \
     && ! pgrep -f 'rm_train_hf' >/dev/null; then
    $P phase1/predictor_suite.py --train-cap 24000 --test-cap 6000 \
       --out phase1/suite_results_v3.csv > /research/d7/spc/yzyang4/logs/suite_v3.log 2>&1
    touch phase1/.suite_v3
    echo "$(date -u +%FT%TZ) suite v3 written" >> "$L"
  fi
  [ -f phase1/.qjudge_done ] && [ -f phase1/.c2ext_done ] && [ -f phase1/.suite_v3 ] \
    && { echo "$(date -u +%FT%TZ) all done" >> "$L"; exit 0; }
  sleep 300
done
