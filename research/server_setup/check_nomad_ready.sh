#!/usr/bin/env bash
# Readiness check for a 2nd-task T0 replication (nomad2018): queue idle? data prepared? where?
source ~/env_setup.sh 2>/dev/null
echo "=== env (data/mlebench vars) ==="
grep -iE 'mlebench|data_dir|prepared|cache' ~/env_setup.sh 2>/dev/null
echo "=== squeue (should be empty) ==="
squeue -u yzyang4 2>/dev/null
echo "=== nomad2018 prepared anywhere under research ==="
find /research/d7/spc/yzyang4 -maxdepth 6 -iname '*nomad*' 2>/dev/null | head -30
echo "=== spaceship prepared (reference path) ==="
find /research/d7/spc/yzyang4 -maxdepth 6 -iname '*spaceship*' -type d 2>/dev/null | head -10
echo "CHECK_DONE"
