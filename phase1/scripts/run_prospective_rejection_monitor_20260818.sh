#!/usr/bin/env bash
set -euo pipefail
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
SCIENTIFIC_REPO=/research/d7/spc/yzyang4/worktrees/prospective_production_90842c4
SCIENTIFIC_COMMIT=90842c49dbd73d41d405a5ecdad2224ee447b375
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
REGISTRY_REL=phase1/results/prospective_structural_rejection_20260816/structural_rejections.json
REGISTRY_SHA=d32cd70b7c755a8ad340cf376fd88f54ca1bea0a50cffbc5fa4cb58bc97ffb01
ADDITIONAL_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260816/structural_rejections_0815.json
ADDITIONAL_REGISTRY_SHA=64e009d3ff1460101b84ff269e12d437ae95a4b0df27fe5a904dc259e09555c2
EXTRA_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260818/structural_rejections_0816.json
EXTRA_REGISTRY_SHA=02f51081e6cdbc6451a3ffdc3d4f14761e627c28bf9c646529fcfb5755b219a6
POLL_SECONDS=60
END_UTC=2026-08-18T09:56:30Z
END_EPOCH=1787046990

mode="${1:-}"
control_repo="${2:-}"
control_commit="${3:-}"
if [[ -z "$control_repo" || ! "$control_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: monitor (--initialize|--run) CONTROL_REPO FULL_CONTROL_COMMIT' >&2
  exit 64
fi
registry="$control_repo/$REGISTRY_REL"
additional_registry="$control_repo/$ADDITIONAL_REGISTRY_REL"
extra_registry="$control_repo/$EXTRA_REGISTRY_REL"
log_root="$STATE_ROOT/logs"
monitor_log="$log_root/monitor_rejection_20260818_resume.log"
pid_file="$STATE_ROOT/rejection_monitor_20260818_resume.pid"

verify_contracts() {
  test -x "$PYTHON"
  test -d "$SOURCE_ROOT"
  test "$(git -C "$control_repo" rev-parse HEAD)" = "$control_commit"
  test -z "$(git -C "$control_repo" status --porcelain --untracked-files=all)"
  test "$(git -C "$SCIENTIFIC_REPO" rev-parse HEAD)" = "$SCIENTIFIC_COMMIT"
  test -z "$(git -C "$SCIENTIFIC_REPO" status --porcelain --untracked-files=all)"
  test "$(sha256sum "$registry" | awk '{print $1}')" = "$REGISTRY_SHA"
  test "$(sha256sum "$additional_registry" | awk '{print $1}')" = "$ADDITIONAL_REGISTRY_SHA"
  test "$(sha256sum "$extra_registry" | awk '{print $1}')" = "$EXTRA_REGISTRY_SHA"
  test "$(tr -d '\r\n' < "$STATE_ROOT/production_commit.txt")" = "$SCIENTIFIC_COMMIT"
  test ! -e "$STATE_ROOT/BASELINE_INVALID"
  test "$(date -u +%s)" -lt "$END_EPOCH"
}

runner() {
  (
    cd "$control_repo"
    "$PYTHON" -m phase1.prospective_production_runner \
      --source-root "$SOURCE_ROOT" \
      --state-root "$STATE_ROOT" \
      --repo-root "$SCIENTIFIC_REPO" \
      --expected-commit "$SCIENTIFIC_COMMIT" \
      --structural-rejection-registry "$registry" \
      --expect-structural-rejection-registry-sha256 "$REGISTRY_SHA" \
      --additional-structural-rejection-registry "$additional_registry" \
      --expect-additional-structural-rejection-registry-sha256 "$ADDITIONAL_REGISTRY_SHA" \
      --extra-structural-rejection-registry "$extra_registry" \
      --expect-extra-structural-rejection-registry-sha256 "$EXTRA_REGISTRY_SHA" \
      --minimum-age-seconds 21600 \
      --minimum-observations 3 \
      --minimum-observation-interval-seconds 300 \
      --minimum-stable-span-seconds 600 \
      "$@"
  )
}

if [[ "$mode" == --initialize ]]; then
  verify_contracts
  mkdir -p "$log_root"
  runner --observe-only > "$log_root/rejection_binding_smoke_20260818.log" 2>&1

  echo 'PREFLIGHT_01_DIRECTION=prospective score-channel mechanism; structural intake only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=$control_commit"
  echo "PREFLIGHT_03_SCIENTIFIC_COMMIT=$SCIENTIFIC_COMMIT"
  echo "PREFLIGHT_04_REJECTION_REGISTRY_SHA256=$REGISTRY_SHA"
  echo "PREFLIGHT_04B_ADDITIONAL_REJECTION_REGISTRY_SHA256=$ADDITIONAL_REGISTRY_SHA"
  echo "PREFLIGHT_04C_EXTRA_REJECTION_REGISTRY_SHA256=$EXTRA_REGISTRY_SHA"
  echo 'PREFLIGHT_05_INPUT=stable append-only senior archives; exact path size mtime and SHA binding'
  echo 'PREFLIGHT_06_ESTIMAND=unchanged; malformed archive creates no scientific transaction'
  echo 'PREFLIGHT_07_EXPECTED=three exact malformed archives skipped; valid later archives processed'
  echo 'PREFLIGHT_08_SECURITY=credential-first journal audit; env member never read; umask077'
  echo 'PREFLIGHT_09_LEAKAGE=outcomes and label vault closed; scorer and accumulator under strace'
  echo 'PREFLIGHT_10_REPRO=clean control and frozen scientific commits; immutable registry and snapshots'
  echo 'PREFLIGHT_11_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_12_FAILURE=any binding or subprocess mismatch stops monitor fail-closed'
  echo "PREFLIGHT_13_RUNTIME=fixed end $END_UTC; one ready archive per poll; snapshot checkpointing"

  if [[ -s "$pid_file" ]]; then
    old_pid="$(cat "$pid_file")"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
      printf 'ALREADY_RUNNING pid=%s log=%s\n' "$old_pid" "$monitor_log"
      exit 0
    fi
  fi
  nohup bash "$control_repo/phase1/scripts/run_prospective_rejection_monitor_20260818.sh" \
    --run "$control_repo" "$control_commit" >> "$monitor_log" 2>&1 </dev/null &
  monitor_pid=$!
  printf '%s\n' "$monitor_pid" > "$pid_file"
  printf 'PROSPECTIVE_REJECTION_MONITOR_STARTED pid=%s log=%s\n' \
    "$monitor_pid" "$monitor_log"
  exit 0
fi

if [[ "$mode" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_contracts
poll=0
while (( $(date -u +%s) < END_EPOCH )); do
  printf '%s poll_start=%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll"
  set +e
  runner --require-strace
  runner_rc=$?
  set -e
  printf '%s poll_end=%d rc=%d\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$runner_rc"
  if (( runner_rc != 0 )); then
    printf '%s PROSPECTIVE_REJECTION_MONITOR_FAIL_CLOSED poll=%d rc=%d\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$runner_rc"
    exit "$runner_rc"
  fi
  poll=$((poll + 1))
  remaining=$((END_EPOCH - $(date -u +%s)))
  if (( remaining > 0 )); then
    if (( remaining < POLL_SECONDS )); then
      sleep "$remaining"
    else
      sleep "$POLL_SECONDS"
    fi
  fi
done
printf '%s PROSPECTIVE_REJECTION_MONITOR_COMPLETE polls=%d fixed_end=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$poll" "$END_UTC"
