#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly control_commit=${OUTCOME_BLIND_GUARD_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/guard_outcome_blind_continuity_887_20260829_v4.sh
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly root=/research/d7/spc/yzyang4/six-hour-structural-guard-20260829-v4
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly intake_log=${state}/logs/continuous_intake_monitor_20260821.log
readonly intake_control=/research/d7/spc/yzyang4/worktrees/alias_monitor_bc362df_v2_nosmudge
readonly intake_commit=bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0
readonly intake_launcher=${intake_control}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly transition=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly receipt=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly config_v7=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v7
readonly config_v8=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v8
readonly target=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_519815d_after_887_v1
readonly wl=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly within=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/formal-monitor-70a48e3-target522-v1
readonly lineage=/research/d7/spc/yzyang4/tree-content-lineage-forward-target522/formal-monitor-bee9e97-target522-v1
readonly selective=/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522/formal-monitor-349b9ca-target522-v1
readonly task_balance=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5-r3

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'OUTCOME_BLIND_GUARD_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
mkdir -p "${root}"
exec 9>"${root}/guard.lock"
flock -n 9
printf '%s\n' "$$" > "${root}/guard.pid"

failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${root}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

git -C "${repo}" fetch fork phase1-value-critic > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
remote_head=$(git -C "${repo}" rev-parse fork/phase1-value-critic)
git -C "${repo}" cat-file -e "${control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${control_commit}" "${remote_head}"
git -C "${repo}" show "${control_commit}:${public_path}" > "${root}/source_script.sh"
cmp "$0" "${root}/source_script.sh"
source_sha=$(sha256sum "${root}/source_script.sh" | awk '{print $1}')

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol only; PASS
02_goal=observe outcome-blind structural continuity for a fresh six-hour window; PASS
03_control_commit=${control_commit}; PASS
04_scope=LATEST PID lock marker filename count and aggregate outcomes_read false summary only; PASS
05_forbidden=no label outcome prediction value accuracy utility sidecar content or raw archive content; PASS
06_population=no cohort identities rows or scientific values are opened; PASS
07_randomness=none fixed 300-second polling for 72 intervals; PASS
08_controls=exact public script intake command and unique live or exact normal-completion monitor states; PASS
09_failure=dead intake failed watcher unknown duplicate hash drift or sidecar appearance fails closed or hands off; PASS
10_resources=metadata polling only GPU API model-fit base-update 0/0/0/0; PASS
11_resume=fresh v4 root starts only after immutable v3 normal completion; PASS
12_security=config-v2 stops at filename metadata before redaction or review; PASS
13_promotion=all polls or explicit successor handoff plus manifest required before COMPLETE; PASS
EOF
test "$(wc -l < "${root}/preflight_13.txt")" = 13

live_pids() {
  local root_path=$1 pid_file pid
  for pid_file in "${root_path}"/*.pid; do
    test -f "${pid_file}" || continue
    pid=$(tr -d '\r\n' < "${pid_file}")
    [[ ${pid} =~ ^[0-9]+$ ]] || continue
    if kill -0 "${pid}" 2>/dev/null; then printf '%s\n' "${pid}"; fi
  done | LC_ALL=C sort -nu
}

lock_is_free() {
  local lock_path=$1
  test -f "${lock_path}" && test ! -L "${lock_path}"
  (
    exec 8< "${lock_path}"
    flock -n -s 8
  )
}

assert_live_locked_or_tail() {
  local root_path=$1 expected_tail=$2
  local count
  test -d "${root_path}"
  test ! -e "${root_path}/FAILED_RC"
  test ! -e "${root_path}/CONTINUITY_GAP"
  count=$(live_pids "${root_path}" | wc -l)
  if ! lock_is_free "${root_path}/monitor.lock"; then
    test "${count}" -ge 1
  else
    tail -n 1 "${root_path}/monitor.log" | grep -Fq "${expected_tail}"
  fi
}

assert_live_or_complete() {
  local root_path=$1
  local count
  test -d "${root_path}"
  test ! -e "${root_path}/FAILED_RC"
  count=$(live_pids "${root_path}" | wc -l)
  if ! lock_is_free "${root_path}/monitor.lock"; then
    test "${count}" -ge 1
  else
    test -e "${root_path}/COMPLETE"
  fi
}

intake_pid=$(tr -d '\r\n' < "${state}/continuous_intake_monitor_20260821.pid")
[[ ${intake_pid} =~ ^[0-9]+$ ]]
kill -0 "${intake_pid}" 2>/dev/null
intake_cmdline=$(tr '\0' ' ' < "/proc/${intake_pid}/cmdline")
case "${intake_cmdline}" in
  *"${intake_launcher} --run ${intake_control} ${intake_commit}"*) ;;
  *) exit 75 ;;
esac
printf '%s\n' "${intake_pid}" > "${root}/intake.pid"

for poll in $(seq 0 72); do
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  latest=$(tr -d '\r\n' < "${state}/LATEST")
  [[ ${latest} =~ ^[0-9a-f]{64}$ ]]
  intake_summary=$(grep 'PROSPECTIVE_ARCHIVE_OBSERVATION_COMPLETE' "${intake_log}" | tail -n 1)
  grep -Fq 'outcomes_read=false' <<< "${intake_summary}"
  test "$(tr -d '\r\n' < "${state}/continuous_intake_monitor_20260821.pid")" = "${intake_pid}"
  kill -0 "${intake_pid}" 2>/dev/null

  sidecar_count=$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)
  if test "${sidecar_count}" != 0; then
    printf 'status=CONFIG_V2_SIDECAR_METADATA_OBSERVED_STOP\nobserved_at_utc=%s\ncount=%s\ncontents_opened=false\n' \
      "${now}" "${sidecar_count}" > "${root}/SIDECAR_METADATA_OBSERVED"
    break
  fi
  if test "${latest}" != "${baseline}"; then
    printf 'status=SUCCESSOR_IDENTITY_OBSERVED_HANDOFF\nobserved_at_utc=%s\nsnapshot_sha256=%s\nprospective_values_read=false\n' \
      "${now}" "${latest}" > "${root}/SUCCESSOR_OBSERVED"
    break
  fi

  assert_live_or_complete "${selection}"
  assert_live_or_complete "${within}"
  assert_live_or_complete "${lineage}"
  assert_live_or_complete "${selective}"
  assert_live_locked_or_tail "${transition}" "monitor_complete prior_snapshot=${baseline}"
  assert_live_locked_or_tail "${receipt}" "monitor_complete prior=${baseline}"
  assert_live_locked_or_tail "${target}" "monitor_complete_without_quiescent_new_snapshot baseline=${baseline} outcomes_read=false"
  assert_live_locked_or_tail "${wl}" "monitor_complete prior_snapshot=${baseline}"
  test ! -e "${target}/formal_rc.txt"
  test -z "$(find "${target}" -maxdepth 1 -type f -name 'runner_worktree_path_*.diff' -print -quit)"

  active_config=${config_v7}
  if test -s "${config_v8}/monitor.log" || test -e "${config_v8}/OBSERVED"; then
    active_config=${config_v8}
  fi
  test ! -e "${active_config}/FAILED_RC"
  test ! -e "${active_config}/OBSERVED"
  config_live=$(live_pids "${active_config}" | wc -l)
  if ! lock_is_free "${active_config}/monitor.lock"; then
    test "${config_live}" -ge 1
  else
    grep -Fq 'status=NO_CONFIG_V2_SIDECAR_OBSERVED' "${active_config}/COMPLETE"
    grep -Fq 'contents_opened=false' "${active_config}/COMPLETE"
  fi

  test ! -e "${task_balance}/FAILED_RC"
  task_balance_live=$(live_pids "${task_balance}" | wc -l)
  if ! lock_is_free "${task_balance}/monitor.lock"; then
    test "${task_balance_live}" -ge 1
  elif test -e "${task_balance}/COMPLETE"; then
    :
  elif test -e "${task_balance}/TIMEOUT_RC"; then
    test "$(tr -d '\r\n' < "${task_balance}/TIMEOUT_RC")" = 124
  else
    exit 79
  fi

  printf '%s poll=%s latest=%s intake_pid=%s sidecar_count=0 transition=healthy receipt=healthy config=healthy target300=healthy wl=healthy task_balance=healthy %s\n' \
    "${now}" "${poll}" "${latest}" "${intake_pid}" "${intake_summary}" >> "${root}/status.log"
  if (( poll == 72 )); then break; fi
  sleep 300
done

printf 'completed_at_utc=%s\ncontrol_commit=%s\nsource_script_sha256=%s\nprospective_values_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${control_commit}" "${source_sha}" > "${root}/READY"
(
  cd "${root}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${root}"
trap - EXIT
