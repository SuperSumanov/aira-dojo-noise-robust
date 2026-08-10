#!/usr/bin/env bash
# Third wave: analyse the qwen-max judge once it lands. Separate from postproc2 so the
# earlier gate's completion markers are not disturbed.
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
A=/research/d7/spc/yzyang4/aira-dojo
P=/research/d7/spc/yzyang4/venvs/critic/bin/python3
L=/research/d7/spc/yzyang4/logs/postproc3.log
cd "$A" || exit 1
echo "$(date -u +%FT%TZ) postproc3 up" >> "$L"
for i in $(seq 1 100); do
  if [ -f phase1/judge_qwenmax.jsonl ] && ! pgrep -f llm_judge >/dev/null      && [ ! -f phase1/.qmax_done ]; then
    $P phase1/judge_analyze.py phase1/judge_qwenmax.jsonl        --dump phase1/judge_scores_qwenmax.json > phase1/judge_qwenmax_report.txt 2>&1
    touch phase1/.qmax_done
    echo "$(date -u +%FT%TZ) qwen-max judge analysed" >> "$L"
    exit 0
  fi
  sleep 240
done
