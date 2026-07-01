#!/usr/bin/env bash
# Cheap pre-launch validation: do the nomad/s3e18 exp configs compose (Hydra --cfg job, no GPU/LLM)?
# Also report whether s3e18 data is prepared.
source ~/env_setup.sh
PY=/research/d7/spc/yzyang4/venvs/aira/bin/python
cd /research/d7/spc/yzyang4/aira-dojo || exit 1
echo "=== s3e18 data prepared? ==="
ls /research/d7/spc/yzyang4/mle-bench-data/playground-series-s3e18/prepared/public/ 2>/dev/null && echo "S3E18_PREPARED=yes" || echo "S3E18_PREPARED=no"
for exp in deepseek_greedy_hce_nomad deepseek_greedy_hce_s3e18; do
  echo "=== dry-run $exp ==="
  "$PY" -m dojo.main_run +_exp=mlebench/$exp task.arm=consistency metadata.seed=1 --cfg job 2>&1 \
    | grep -iE "error|could not|invalid|^  name:|arm:|hce_eval:|step_limit:" | head -15
done
echo "CFG_CHECK_DONE"
