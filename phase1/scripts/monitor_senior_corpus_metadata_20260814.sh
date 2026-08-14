#!/usr/bin/env bash
# Eight-hour, read-only monitor for senior corpus drops.
#
# Security boundary: this script records names, sizes, and mtimes only.  It never
# lists archive members, extracts an archive, or reads outcome/API-key content.

set -uo pipefail

SOURCE_ROOT="${SOURCE_ROOT:-/research/d7/spc/yzyang4/external/senior_data/mle}"
STATE_ROOT="${STATE_ROOT:-/research/d7/spc/yzyang4/logs/senior_corpus_metadata_monitor_20260814}"
POLL_SECONDS="${POLL_SECONDS:-300}"
MAX_POLLS="${MAX_POLLS:-97}"

mkdir -p "$STATE_ROOT"
LOCK_DIR="$STATE_ROOT/lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf '%s monitor_already_running lock=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$LOCK_DIR"
  exit 73
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

CURRENT="$STATE_ROOT/current.tsv"
PREVIOUS="$STATE_ROOT/previous.tsv"
EVENTS="$STATE_ROOT/events.log"
: > "$CURRENT"
if [[ ! -f "$PREVIOUS" ]]; then
  : > "$PREVIOUS"
fi

printf '%s monitor_start source=%s poll_seconds=%s max_polls=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SOURCE_ROOT" "$POLL_SECONDS" "$MAX_POLLS" | tee -a "$EVENTS"

for ((poll=0; poll<MAX_POLLS; poll++)); do
  now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if [[ ! -d "$SOURCE_ROOT" ]]; then
    printf '%s source_unavailable poll=%d source=%s\n' "$now" "$poll" "$SOURCE_ROOT" | tee -a "$EVENTS"
  else
    # GNU find's %P/%s/%T@ expose path-relative metadata only; no file is opened.
    find "$SOURCE_ROOT" -mindepth 1 -maxdepth 2 \
      \( -type d -o -type f \) -printf '%y\t%P\t%s\t%T@\n' \
      | LC_ALL=C sort > "$CURRENT"
    current_sha="$(sha256sum "$CURRENT" | awk '{print $1}')"
    previous_sha="$(sha256sum "$PREVIOUS" | awk '{print $1}')"
    if [[ "$current_sha" != "$previous_sha" ]]; then
      directory_count="$(awk -F '\t' '$1 == "d" {n++} END {print n+0}' "$CURRENT")"
      file_count="$(awk -F '\t' '$1 == "f" {n++} END {print n+0}' "$CURRENT")"
      printf '%s metadata_change poll=%d sha256=%s directories=%s files=%s\n' \
        "$now" "$poll" "$current_sha" "$directory_count" "$file_count" | tee -a "$EVENTS"
      diff -u "$PREVIOUS" "$CURRENT" | sed -n '1,240p' | tee -a "$EVENTS" || true
      cp "$CURRENT" "$PREVIOUS"
    elif (( poll % 12 == 0 )); then
      printf '%s heartbeat poll=%d sha256=%s\n' "$now" "$poll" "$current_sha" | tee -a "$EVENTS"
    fi
  fi

  if (( poll + 1 < MAX_POLLS )); then
    sleep "$POLL_SECONDS"
  fi
done

printf '%s monitor_complete polls=%s source=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MAX_POLLS" "$SOURCE_ROOT" | tee -a "$EVENTS"
