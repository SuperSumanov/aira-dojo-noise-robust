#!/usr/bin/env bash
# Launch the self-throttling T1 matrix submitter DETACHED (survives ssh disconnect / Claude close).
# No args -> submitter defaults to spaceship-titanic + nomad2018 (30 runs).
mkdir -p /research/d7/spc/yzyang4/aira-dojo-runs
nohup bash /research/d7/spc/yzyang4/scripts/submit_t1_matrix.sh "$@" \
  > /research/d7/spc/yzyang4/aira-dojo-runs/matrix_submit.log 2>&1 < /dev/null &
echo "MATRIX_LAUNCHED pid=$! log=/research/d7/spc/yzyang4/aira-dojo-runs/matrix_submit.log"
