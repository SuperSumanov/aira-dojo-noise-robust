#!/usr/bin/env bash
set -euo pipefail
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
POLL_SECONDS=300
MAX_POLLS=97

mode="${1:-}"
repo_root="${2:-}"
expected_commit="${3:-}"
if [[ -z "$repo_root" || ! "$expected_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: monitor (--initialize|--run) REPO_ROOT FULL_COMMIT' >&2
  exit 64
fi
script="$repo_root/phase1/scripts/run_prospective_production_monitor_20260814.sh"
log_root="$STATE_ROOT/logs"
monitor_log="$log_root/monitor.log"
pid_file="$STATE_ROOT/monitor.pid"

metadata_snapshot() {
  local output="$1"
  find "$SOURCE_ROOT" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' \
    -printf '%P\t%s\t%T@\n' | LC_ALL=C sort > "$output"
}

verify_fixed_worktree() {
  test -x "$PYTHON"
  test -d "$SOURCE_ROOT"
  test "$(git -C "$repo_root" rev-parse HEAD)" = "$expected_commit"
  test -z "$(git -C "$repo_root" status --porcelain --untracked-files=all)"
}

runner() {
  "$PYTHON" -m phase1.prospective_production_runner \
    --source-root "$SOURCE_ROOT" \
    --state-root "$STATE_ROOT" \
    --repo-root "$repo_root" \
    --expected-commit "$expected_commit" \
    --minimum-age-seconds 21600 \
    --minimum-observations 3 \
    --minimum-observation-interval-seconds 300 \
    --minimum-stable-span-seconds 600 \
    "$@"
}

if [[ "$mode" == --initialize ]]; then
  verify_fixed_worktree
  mkdir -p "$STATE_ROOT" "$log_root"
  if [[ -s "$STATE_ROOT/production_commit.txt" ]]; then
    test "$(tr -d '\r\n' < "$STATE_ROOT/production_commit.txt")" = "$expected_commit"
  else
    printf '%s\n' "$expected_commit" > "$STATE_ROOT/production_commit.txt"
  fi
  test ! -e "$STATE_ROOT/BASELINE_INVALID"

  if [[ ! -e "$STATE_ROOT/observations.json" ]]; then
    before="$STATE_ROOT/baseline_metadata.before.tsv"
    after="$STATE_ROOT/baseline_metadata.after.tsv"
    metadata_snapshot "$before"
    runner --observe-only > "$log_root/baseline_runner.log" 2>&1
    metadata_snapshot "$after"
    if ! cmp -s "$before" "$after"; then
      printf '%s baseline changed during seal\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        > "$STATE_ROOT/BASELINE_INVALID"
      exit 65
    fi
    {
      printf 'status=PROSPECTIVE_BASELINE_METADATA_SEALED\n'
      printf 'sealed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'git_commit=%s\n' "$expected_commit"
      printf 'archives=%s\n' "$(wc -l < "$before")"
      printf 'metadata_sha256=%s\n' "$(sha256sum "$before" | awk '{print $1}')"
      printf 'outcomes_read=false\n'
    } > "$STATE_ROOT/baseline_receipt.txt"
  fi

  echo 'PREFLIGHT_01_DIRECTION=run-clean decision-local benchmark plus first-960 prospective confirmation'
  echo "PREFLIGHT_02_GIT_COMMIT=$expected_commit"
  echo 'PREFLIGHT_03_INPUT=single stable senior tar.gz per append-only drop; initial metadata baseline sealed'
  echo 'PREFLIGHT_04_ESTIMAND=no outcome metric during collection; fixed first-960 order unchanged'
  echo 'PREFLIGHT_05_TEST=focused local plus remote sklearn suite and one synthetic transaction smoke'
  echo 'PREFLIGHT_06_EXPECTED=baseline archives ignored; only post-baseline paths become candidates'
  echo 'PREFLIGHT_07_SECURITY=umask077; env member never read; scorer and accumulator under strace'
  echo 'PREFLIGHT_08_LEAKAGE=fixed receipt, run denylist, endpoint ID and exact-code SHA denylist'
  echo 'PREFLIGHT_09_REPRO=detached exact-clean commit, immutable snapshots, commands and SHA manifests'
  echo 'PREFLIGHT_10_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_11_OUTPUT=state outside repo; LATEST advances only after full transaction verification'
  echo 'PREFLIGHT_12_FAILURE=nonzero exits stop monitor; no partial transaction becomes latest'
  echo 'PREFLIGHT_13_RUNTIME=97 polls x 300s; one ready archive per poll; checkpointed by immutable snapshot'

  if [[ -s "$pid_file" ]]; then
    old_pid="$(cat "$pid_file")"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null \
        && ps -p "$old_pid" -o args= | grep -Fq "$script --run"; then
      printf 'ALREADY_RUNNING pid=%s log=%s\n' "$old_pid" "$monitor_log"
      exit 0
    fi
  fi
  nohup bash "$script" --run "$repo_root" "$expected_commit" \
    >> "$monitor_log" 2>&1 </dev/null &
  monitor_pid=$!
  printf '%s\n' "$monitor_pid" > "$pid_file"
  printf 'PROSPECTIVE_MONITOR_STARTED pid=%s log=%s\n' "$monitor_pid" "$monitor_log"
  exit 0
fi

if [[ "$mode" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_fixed_worktree
test "$(tr -d '\r\n' < "$STATE_ROOT/production_commit.txt")" = "$expected_commit"
test -s "$STATE_ROOT/baseline_receipt.txt"
test ! -e "$STATE_ROOT/BASELINE_INVALID"

for ((poll=0; poll<MAX_POLLS; poll++)); do
  printf '%s poll_start=%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll"
  set +e
  (cd "$repo_root" && runner --require-strace)
  runner_rc=$?
  set -e
  printf '%s poll_end=%d rc=%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$runner_rc"
  if (( runner_rc != 0 )); then
    printf '%s PROSPECTIVE_MONITOR_FAIL_CLOSED poll=%d rc=%d\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$runner_rc"
    exit "$runner_rc"
  fi
  if (( poll + 1 < MAX_POLLS )); then
    sleep "$POLL_SECONDS"
  fi
done

printf '%s PROSPECTIVE_MONITOR_COMPLETE polls=%d\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MAX_POLLS"
