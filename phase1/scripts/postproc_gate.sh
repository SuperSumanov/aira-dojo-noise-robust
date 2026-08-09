#!/usr/bin/env bash
# Overnight post-processing, cluster-side so it survives client crashes.
#
# Three things are in flight and each has an analysis that should run the moment it lands.
# Doing this here rather than in a client-side watcher means a disconnect costs nothing:
# by morning the numbers exist whether or not anyone was watching.
#
#   judge_code8k.jsonl  -> judge_analyze (the 1500-token run left 79% of answers salvaged
#                          from cut-off reasoning; this rerun is the one that counts)
#   ctx_sweep.csv       -> nothing to compute, the CSV is the result
#   rm_scores_sibling   -> selective_exec (cost-aware selection: the reframed main experiment)
#
# Each step writes a marker so a restart does not redo finished work.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
A=/research/d7/spc/yzyang4/aira-dojo
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
L=/research/d7/spc/yzyang4/logs/postproc.log
cd "$A" || exit 1
echo "$(date -u +%FT%TZ) postproc gate up" >> "$L"

for i in $(seq 1 300); do          # ~25h at 5 min
  # 1. judge rerun -> analysis
  if [ -f phase1/judge_code8k.jsonl ] && ! pgrep -f llm_judge >/dev/null \
     && [ ! -f phase1/.judge8k_done ]; then
    echo "$(date -u +%FT%TZ) analysing judge_code8k" >> "$L"
    $P phase1/judge_analyze.py phase1/judge_code8k.jsonl \
       --dump phase1/judge_scores8k.json > phase1/judge8k_report.txt 2>&1
    $P phase1/judge_trunc_check.py phase1/judge_code8k.jsonl \
       >> phase1/judge8k_report.txt 2>&1
    touch phase1/.judge8k_done
    echo "$(date -u +%FT%TZ) judge8k analysis written" >> "$L"
  fi

  # 2. sibling scores -> selective execution (the cost-aware experiment)
  if [ -f phase1/rm_scores_sibling.json ] && [ ! -f phase1/.selective_done ]; then
    echo "$(date -u +%FT%TZ) running selective_exec" >> "$L"
    $P phase1/selective_exec.py phase1/rm_scores_sibling.json \
       > phase1/selective_exec_report.txt 2>&1
    touch phase1/.selective_done
    echo "$(date -u +%FT%TZ) selective_exec written" >> "$L"
  fi

  # 3. once the context sweep has all three cells, refresh the suite table so the
  #    trained-critic rows sit next to the cheap ones in a single comparison
  ncells=$(( $(wc -l < phase1/ctx_sweep.csv 2>/dev/null || echo 1) - 1 ))
  if [ "$ncells" -ge 3 ] && [ ! -f phase1/.suite_refreshed ]; then
    echo "$(date -u +%FT%TZ) ctx sweep complete ($ncells cells), refreshing suite" >> "$L"
    $P phase1/predictor_suite.py --train-cap 24000 --test-cap 6000 \
       --out phase1/suite_results_v2.csv > /research/d7/spc/yzyang4/logs/suite_v2.log 2>&1
    touch phase1/.suite_refreshed
    echo "$(date -u +%FT%TZ) suite v2 written" >> "$L"
  fi

  [ -f phase1/.judge8k_done ] && [ -f phase1/.selective_done ] \
    && [ -f phase1/.suite_refreshed ] && { echo "$(date -u +%FT%TZ) all done" >> "$L"; exit 0; }
  sleep 300
done
echo "$(date -u +%FT%TZ) postproc gate timed out" >> "$L"
