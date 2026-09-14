#!/bin/bash
set -eo pipefail
umask 077
source /uac/y24/yzyang4/env_setup.sh
set -u
task_root=/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy
test -s "$task_root/plan.json"
task_attempt=${1:-initial}
task_mode=download
task_timeout=7200s
case "$task_attempt" in
  initial) task_stem=download ;;
  after-reclaim)
    test -s /research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq/archive-reclamation-20260914.json
    read -r task_prior_pid < "$task_root/download-launch.pid"
    [[ "$task_prior_pid" =~ ^[0-9]+$ ]]
    if kill -0 "$task_prior_pid" 2>/dev/null; then
      printf 'Prior PID still exists; refusing a second launcher.\n' >&2
      exit 1
    fi
    task_stem=download-after-reclaim ;;
  image-only)
    read -r task_prior_pid < "$task_root/download-after-reclaim-launch.pid"
    [[ "$task_prior_pid" =~ ^[0-9]+$ ]]
    if kill -0 "$task_prior_pid" 2>/dev/null; then exit 1; fi
    task_stem=download-image-only
    task_mode=image
    task_timeout=1800s ;;
  *) exit 2 ;;
esac
test ! -e "$task_root/$task_stem-launch.pid"
test ! -e "$task_root/$task_stem.log"
set -C
nohup timeout --signal=TERM --kill-after=30s "$task_timeout" /research/d7/spc/yzyang4/venvs/aira/bin/python -u -B /research/d7/spc/yzyang4/prepare_local_generator_assets_20260914.py "$task_mode" "$task_root" > "$task_root/$task_stem.log" 2>&1 < /dev/null &
task_pid=$!
printf '%s\n' "$task_pid" > "$task_root/$task_stem-launch.pid"
printf 'DOWNLOAD_PID=%s ROOT=%s\n' "$task_pid" "$task_root"
