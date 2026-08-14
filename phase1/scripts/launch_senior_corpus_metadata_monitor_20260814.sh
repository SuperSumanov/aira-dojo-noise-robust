#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/research/d7/spc/yzyang4/aira-dojo"
LOG_ROOT="/research/d7/spc/yzyang4/logs/senior_corpus_metadata_monitor_20260814"
SCRIPT="$REPO_ROOT/phase1/scripts/monitor_senior_corpus_metadata_20260814.sh"
PID_FILE="$LOG_ROOT/monitor.pid"
STDOUT_LOG="$LOG_ROOT/nohup.log"

mkdir -p "$LOG_ROOT"
if [[ -s "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE")"
  if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null \
      && ps -p "$old_pid" -o args= | grep -Fq "$SCRIPT"; then
    printf 'ALREADY_RUNNING pid=%s log=%s\n' "$old_pid" "$STDOUT_LOG"
    exit 0
  fi
fi

nohup bash "$SCRIPT" > "$STDOUT_LOG" 2>&1 &
monitor_pid=$!
printf '%s\n' "$monitor_pid" > "$PID_FILE"
printf 'STARTED pid=%s log=%s events=%s\n' \
  "$monitor_pid" "$STDOUT_LOG" "$LOG_ROOT/events.log"
