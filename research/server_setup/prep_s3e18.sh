#!/usr/bin/env bash
# Prepare playground-series-s3e18 data via mle-bench (needs Kaggle rules accepted + proxy in kaggle.json).
source ~/env_setup.sh
export PATH=/research/d7/spc/yzyang4/venvs/aira/bin:$PATH
echo "=== preparing playground-series-s3e18 ==="; date -u +%FT%TZ
echo n | mlebench prepare -c playground-series-s3e18 --data-dir /research/d7/spc/yzyang4/mle-bench-data
echo "PREP_S3E18_DONE rc=$? $(date -u +%FT%TZ)"
ls -la /research/d7/spc/yzyang4/mle-bench-data/playground-series-s3e18/ 2>/dev/null
