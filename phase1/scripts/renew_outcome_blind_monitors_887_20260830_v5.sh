#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly control_commit=${OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/renew_outcome_blind_monitors_887_20260830_v5.sh
readonly guard_public_path=phase1/scripts/guard_outcome_blind_continuity_887_20260830_v5.sh
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly root=/research/d7/spc/yzyang4/monitor-relaunch-887/20260830-v5
readonly guard_root=/research/d7/spc/yzyang4/six-hour-structural-guard-20260830-v5
readonly old_guard=/research/d7/spc/yzyang4/six-hour-structural-guard-20260829-v4
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly intake_log=${state}/logs/continuous_intake_monitor_20260821.log

readonly intake_control=/research/d7/spc/yzyang4/worktrees/alias_monitor_bc362df_v2_nosmudge
readonly intake_commit=bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0
readonly intake_launcher=${intake_control}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh
readonly intake_sha=b88eda114aa360a0f53b3ff5fca9180c6db7e4624362461a7c1cde76be4af841

readonly transition_repo=${intake_control}
readonly transition_commit=${intake_commit}
readonly transition_script=${transition_repo}/phase1/scripts/monitor_transition_snapshot_chain_20260826.sh
readonly transition_sha=87ed6fa645de2fad25695b212434bd1dd64b6f1a44a34f6232c941ad8d8b9161
readonly transition_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly transition_output=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-snapshot-chain
readonly transition_state_sha=d675dbd92a244bb9d55b1c3377bcbb0590e91f4ce4bf5321ca8ce38284629a25

readonly receipt_repo=/research/d7/spc/yzyang4/worktrees/receipt_support_9f2cbe9_nosmudge
readonly receipt_commit=9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f
readonly receipt_script=${receipt_repo}/phase1/scripts/monitor_prediction_coverage_snapshot_chain_20260826.sh
readonly receipt_sha=458b50a3ac4499abd80c951881f69ab15f82af15a8b2bc51c950cf425d906533
readonly receipt_root=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly receipt_output=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1
readonly receipt_state_sha=ee837edf88a5a8d316a7a11664ed4090f8c681cf6982df1df69abb041e234f8c

readonly wl_repo=${intake_control}
readonly wl_commit=${intake_commit}
readonly wl_script=${wl_repo}/phase1/scripts/monitor_wl_snapshot_chain_20260826.sh
readonly wl_sha=4cec4fd7cb2382f6e7f4e071b31212cfa45901de9dcfcc7730f18cad4e619daa
readonly wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly wl_output=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain
readonly wl_state_sha=c80e94c8cc9ca25f7d5db2243ec0878443e4ceac4e0f7b41bae6b4a4d6922154

readonly config_script=/research/d7/spc/yzyang4/monitor_future_config_v2_readiness_20260826_v2.sh
readonly config_sha=e04137ae801f25debc4168bdadd4a3eb4dd068ff6a17982e1d780d14d22bac45
readonly config_old=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v8
readonly config_root=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260830_v9

readonly target_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_519815d_after_887_v1
readonly target_script=${target_root}/monitor_target300_after_887_20260828.sh
readonly target_sha=fb393ef06c29728afa0da2f7ca26c748eb5b85bd6c065b66e5ba4f2f1cbdc0d7

readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly within=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/formal-monitor-70a48e3-target522-v1
readonly lineage=/research/d7/spc/yzyang4/tree-content-lineage-forward-target522/formal-monitor-bee9e97-target522-v1
readonly selective=/research/d7/spc/yzyang4/tree-content-selective-parent-forward-target522/formal-monitor-349b9ca-target522-v1

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
test ! -e "${guard_root}"
test ! -e "${config_root}"
mkdir -p "${root}"
failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then printf '%s\n' "${rc}" >"${root}/FAILED_RC" 2>/dev/null || true; fi
  exit "${rc}"
}
trap failure_receipt EXIT

lock_is_free() {
  local lock_path=$1
  test -f "${lock_path}" && test ! -L "${lock_path}"
  (exec 8<"${lock_path}"; flock -n -s 8)
}

assert_dead_pid_file() {
  local pid_file=$1 pid
  test -f "${pid_file}"
  pid=$(tr -d '\r\n' <"${pid_file}")
  [[ ${pid} =~ ^[0-9]+$ ]]
  ! kill -0 "${pid}" 2>/dev/null
}

assert_live_locked() {
  local root_path=$1 pid_file=$2 pid
  test -f "${pid_file}"
  pid=$(tr -d '\r\n' <"${pid_file}")
  [[ ${pid} =~ ^[0-9]+$ ]]
  kill -0 "${pid}" 2>/dev/null
  if lock_is_free "${root_path}/monitor.lock"; then return 1; fi
}

git -C "${repo}" fetch fork phase1-value-critic >"${root}/fetch.stdout" 2>"${root}/fetch.stderr"
remote_head=$(git -C "${repo}" rev-parse fork/phase1-value-critic)
git -C "${repo}" cat-file -e "${control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${control_commit}" "${remote_head}"
git -C "${repo}" show "${control_commit}:${public_path}" >"${root}/source_script.sh"
git -C "${repo}" show "${control_commit}:${guard_public_path}" >"${root}/guard_source.sh"
cmp "$0" "${root}/source_script.sh"
source_sha=$(sha256sum "${root}/source_script.sh" | awk '{print $1}')
guard_sha=$(sha256sum "${root}/guard_source.sh" | awk '{print $1}')
bash -n "${root}/source_script.sh"
bash -n "${root}/guard_source.sh"

cat >"${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol outcome-blind continuity only; PASS
02_goal=renew the naturally expired intake and support monitors before new senior archives become eligible; PASS
03_context=old intake completed 145 polls and old guard failed only after poll 71 while baseline remained 887; PASS
04_inputs=PID locks LATEST marker names exact script and state hashes and outcomes_read false summaries only; PASS
05_forbidden=no label outcome prediction value accuracy utility raw archive or sidecar payload; PASS
06_continuity=same state roots fixed scorer fixed prior snapshot and append-only intake; PASS
07_controls=public exact source old completion receipts dead PIDs free locks and fixed script hashes; PASS
08_failure=duplicate process held old lock hash drift new marker sidecar or first-poll failure stops closed; PASS
09_randomness=none fixed monitor intervals and existing frozen scorer seeds; PASS
10_resources=CPU metadata polling and fixed CPU scorer only GPU API model-fit base-update 0/0/0/0; PASS
11_duration=intake 145x300s support 72x300s Target-300 retains 144x300s guard six hours; PASS
12_security=credential-first intake and filename-only config detection with payload unopened; PASS
13_promotion=all child PIDs commands locks first polls and immutable launcher manifest required; PASS
EOF
test "$(wc -l <"${root}/preflight_13.txt")" = 13

test "$(tr -d '\r\n' <"${state}/LATEST")" = "${baseline}"
test "$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)" = 0
test ! -e "${state}/BASELINE_INVALID"
for marker in candidate.tsv READY COMPLETE FAILED_RC CONTINUITY_GAP; do test ! -e "${selection}/${marker}"; done

old_intake_pid=$(tr -d '\r\n' <"${state}/continuous_intake_monitor_20260821.pid")
[[ ${old_intake_pid} =~ ^[0-9]+$ ]]
! kill -0 "${old_intake_pid}" 2>/dev/null
tail -n 1 "${intake_log}" | grep -Fq 'PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE polls=145 outcomes_read=false'
test "$(tr -d '\r\n' <"${old_guard}/FAILED_RC")" = 1
tail -n 1 "${old_guard}/status.log" | grep -Fq "poll=71 latest=${baseline}"
tail -n 1 "${old_guard}/status.log" | grep -Fq 'outcomes_read=false'
lock_is_free "${old_guard}/guard.lock"

assert_dead_pid_file "${transition_root}/resume_20260829_887_v4.pid"
assert_dead_pid_file "${receipt_root}/resume_20260829_887_v4.pid"
assert_dead_pid_file "${config_old}/launcher.pid"
assert_dead_pid_file "${target_root}/resume_20260829_887_v3.pid"
assert_dead_pid_file "${wl_root}/renew_20260829_887_v2.pid"
lock_is_free "${transition_root}/monitor.lock"
lock_is_free "${receipt_root}/monitor.lock"
lock_is_free "${config_old}/monitor.lock"
lock_is_free "${target_root}/monitor.lock"
lock_is_free "${wl_root}/monitor.lock"
tail -n 1 "${transition_root}/monitor.log" | grep -Fq "monitor_complete prior_snapshot=${baseline}"
tail -n 1 "${receipt_root}/monitor.log" | grep -Fq "monitor_complete prior=${baseline}"
grep -Fq 'status=NO_CONFIG_V2_SIDECAR_OBSERVED' "${config_old}/COMPLETE"
grep -Fq 'contents_opened=false' "${config_old}/COMPLETE"
tail -n 1 "${target_root}/monitor.log" | grep -Fq "monitor_complete_without_quiescent_new_snapshot baseline=${baseline} outcomes_read=false"
tail -n 1 "${wl_root}/monitor.log" | grep -Fq "monitor_complete prior_snapshot=${baseline}"
test ! -e "${target_root}/formal_rc.txt"
test -z "$(find "${target_root}" -maxdepth 1 -type f -name 'runner_worktree_path_*.diff' -print -quit)"

test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
test "$(sha256sum "${receipt_root}/state.tsv" | awk '{print $1}')" = "${receipt_state_sha}"
test "$(sha256sum "${wl_root}/state.tsv" | awk '{print $1}')" = "${wl_state_sha}"

for tuple in \
  "${intake_launcher} ${intake_sha}" \
  "${transition_script} ${transition_sha}" \
  "${receipt_script} ${receipt_sha}" \
  "${wl_script} ${wl_sha}" \
  "${config_script} ${config_sha}" \
  "${target_script} ${target_sha}"; do
  read -r script expected_sha <<<"${tuple}"
  test "$(sha256sum "${script}" | awk '{print $1}')" = "${expected_sha}"
  bash -n "${script}"
done
test "$(git -C "${intake_control}" rev-parse HEAD)" = "${intake_commit}"
test -z "$(git -C "${intake_control}" status --porcelain --untracked-files=all)"
test "$(git -C "${receipt_repo}" rev-parse HEAD)" = "${receipt_commit}"
test -z "$(git -C "${receipt_repo}" status --porcelain --untracked-files=all)"

assert_live_locked "${selection}" "${selection}/monitor.pid"
assert_live_locked "${within}" "${within}/monitor.pid"
assert_live_locked "${lineage}" "${lineage}/monitor.pid"
assert_live_locked "${selective}" "${selective}/monitor.pid"

intake_before=$(wc -l <"${intake_log}")
bash "${intake_launcher}" --initialize "${intake_control}" "${intake_commit}" \
  >"${root}/intake_initialize.stdout" 2>"${root}/intake_initialize.stderr"
test ! -s "${root}/intake_initialize.stderr"
intake_pid=$(tr -d '\r\n' <"${state}/continuous_intake_monitor_20260821.pid")
[[ ${intake_pid} =~ ^[0-9]+$ ]]
test "${intake_pid}" != "${old_intake_pid}"
kill -0 "${intake_pid}" 2>/dev/null
intake_cmdline=$(tr '\0' ' ' <"/proc/${intake_pid}/cmdline")
case "${intake_cmdline}" in
  *"${intake_launcher} --run ${intake_control} ${intake_commit}"*) ;;
  *) exit 75 ;;
esac

transition_before=$(wc -l <"${transition_root}/monitor.log")
receipt_before=$(wc -l <"${receipt_root}/monitor.log")
target_before=$(wc -l <"${target_root}/monitor.log")
wl_before=$(wc -l <"${wl_root}/monitor.log")

nohup env SNAPSHOT_CHAIN_STATE_ROOT="${state}" SNAPSHOT_CHAIN_OUTPUT_ROOT="${transition_output}" \
  SNAPSHOT_CHAIN_MONITOR_ROOT="${transition_root}" SNAPSHOT_CHAIN_POLL_SECONDS=300 SNAPSHOT_CHAIN_MAX_POLLS=72 \
  bash "${transition_script}" "${transition_repo}" "${transition_commit}" \
  >"${transition_root}/resume_20260830_887_v5.stdout" 2>"${transition_root}/resume_20260830_887_v5.stderr" </dev/null &
transition_pid=$!
printf '%s\n' "${transition_pid}" >"${transition_root}/resume_20260830_887_v5.pid"

nohup env RECEIPT_SUPPORT_STATE_ROOT="${state}" RECEIPT_SUPPORT_RESULT_ROOT="${receipt_output}" \
  RECEIPT_SUPPORT_MONITOR_ROOT="${receipt_root}" RECEIPT_SUPPORT_POLL_SECONDS=300 \
  RECEIPT_SUPPORT_MAX_POLLS=72 RECEIPT_SUPPORT_STABLE_POLLS=3 \
  bash "${receipt_script}" "${receipt_repo}" "${receipt_commit}" \
  >"${receipt_root}/resume_20260830_887_v5.stdout" 2>"${receipt_root}/resume_20260830_887_v5.stderr" </dev/null &
receipt_pid=$!
printf '%s\n' "${receipt_pid}" >"${receipt_root}/resume_20260830_887_v5.pid"

mkdir "${config_root}"
nohup env CONFIG_V2_MONITOR_ROOT="${config_root}" CONFIG_V2_POLL_SECONDS=300 CONFIG_V2_MAX_POLLS=72 \
  bash "${config_script}" >"${config_root}/launcher.stdout" 2>"${config_root}/launcher.stderr" </dev/null &
config_pid=$!
printf '%s\n' "${config_pid}" >"${config_root}/launcher.pid"

nohup bash "${target_script}" >"${target_root}/resume_20260830_887_v4.stdout" \
  2>"${target_root}/resume_20260830_887_v4.stderr" </dev/null &
target_pid=$!
printf '%s\n' "${target_pid}" >"${target_root}/resume_20260830_887_v4.pid"

nohup env WL_CHAIN_STATE_ROOT="${state}" WL_CHAIN_OUTPUT_ROOT="${wl_output}" \
  WL_CHAIN_MONITOR_ROOT="${wl_root}" WL_CHAIN_POLL_SECONDS=300 WL_CHAIN_MAX_POLLS=72 \
  bash "${wl_script}" "${wl_repo}" "${wl_commit}" \
  >"${wl_root}/renew_20260830_887_v3.stdout" 2>"${wl_root}/renew_20260830_887_v3.stderr" </dev/null &
wl_pid=$!
printf '%s\n' "${wl_pid}" >"${wl_root}/renew_20260830_887_v3.pid"

transition_started=false
receipt_started=false
config_started=false
target_started=false
wl_started=false
for _ in $(seq 1 60); do
  tail -n "+$((transition_before + 1))" "${transition_root}/monitor.log" >"${root}/transition_log_segment.txt"
  tail -n "+$((receipt_before + 1))" "${receipt_root}/monitor.log" >"${root}/receipt_log_segment.txt"
  tail -n "+$((target_before + 1))" "${target_root}/monitor.log" >"${root}/target_log_segment.txt"
  tail -n "+$((wl_before + 1))" "${wl_root}/monitor.log" >"${root}/wl_log_segment.txt"
  grep -Fq "monitor_start prior_snapshot=${baseline}" "${root}/transition_log_segment.txt" && transition_started=true
  grep -Fq "monitor_start prior=${baseline}" "${root}/receipt_log_segment.txt" && receipt_started=true
  grep -Fq "monitor_start baseline=${baseline}" "${root}/target_log_segment.txt" && target_started=true
  grep -Fq "monitor_start prior_snapshot=${baseline}" "${root}/wl_log_segment.txt" && wl_started=true
  if test -f "${config_root}/monitor.log" && grep -Fq 'poll=1 sidecar_count=0' "${config_root}/monitor.log"; then
    config_started=true
  elif test -f "${config_root}/OBSERVED"; then
    exit 68
  fi
  if [[ ${transition_started} = true && ${receipt_started} = true && ${config_started} = true \
      && ${target_started} = true && ${wl_started} = true ]]; then break; fi
  for pid in "${transition_pid}" "${receipt_pid}" "${config_pid}" "${target_pid}" "${wl_pid}"; do kill -0 "${pid}"; done
  sleep 2
done
test "${transition_started}" = true
test "${receipt_started}" = true
test "${config_started}" = true
test "${target_started}" = true
test "${wl_started}" = true
for pid in "${intake_pid}" "${transition_pid}" "${receipt_pid}" "${config_pid}" "${target_pid}" "${wl_pid}"; do kill -0 "${pid}"; done
for lock in "${transition_root}/monitor.lock" "${receipt_root}/monitor.lock" "${config_root}/monitor.lock" \
    "${target_root}/monitor.lock" "${wl_root}/monitor.lock"; do
  if lock_is_free "${lock}"; then exit 69; fi
done
test ! -s "${transition_root}/resume_20260830_887_v5.stderr"
test ! -s "${receipt_root}/resume_20260830_887_v5.stderr"
test ! -s "${config_root}/launcher.stderr"
test ! -s "${target_root}/resume_20260830_887_v4.stderr"
test ! -s "${wl_root}/renew_20260830_887_v3.stderr"

chmod 0500 "${root}/guard_source.sh"
nohup env OUTCOME_BLIND_GUARD_CONTROL_COMMIT="${control_commit}" bash "${root}/guard_source.sh" \
  >"${root}/guard.stdout" 2>"${root}/guard.stderr" </dev/null &
guard_pid=$!
printf '%s\n' "${guard_pid}" >"${root}/guard.pid"
for _ in $(seq 1 60); do
  if test -s "${guard_root}/status.log" || test -e "${guard_root}/SUCCESSOR_OBSERVED" \
      || test -e "${guard_root}/SIDECAR_METADATA_OBSERVED" || test -e "${guard_root}/FAILED_RC"; then break; fi
  kill -0 "${guard_pid}"
  sleep 2
done
test ! -e "${guard_root}/FAILED_RC"
guard_state=unknown
if test -s "${guard_root}/status.log"; then
  grep -Fq "latest=${baseline}" "${guard_root}/status.log"
  grep -Fq 'outcomes_read=false' "${guard_root}/status.log"
  kill -0 "${guard_pid}"
  if lock_is_free "${guard_root}/guard.lock"; then exit 70; fi
  guard_state=live_at_baseline
elif test -e "${guard_root}/SUCCESSOR_OBSERVED"; then
  grep -Fq 'prospective_values_read=false' "${guard_root}/SUCCESSOR_OBSERVED"
  for _ in $(seq 1 30); do test -e "${guard_root}/COMPLETE" && break; sleep 1; done
  test -e "${guard_root}/COMPLETE"
  guard_state=successor_identity_handoff
elif test -e "${guard_root}/SIDECAR_METADATA_OBSERVED"; then
  grep -Fq 'contents_opened=false' "${guard_root}/SIDECAR_METADATA_OBSERVED"
  for _ in $(seq 1 30); do test -e "${guard_root}/COMPLETE" && break; sleep 1; done
  test -e "${guard_root}/COMPLETE"
  guard_state=sidecar_metadata_stop
else
  exit 71
fi

intake_segment_lines=$(( $(wc -l <"${intake_log}") - intake_before ))
test "${intake_segment_lines}" -ge 1
cat >"${root}/operation_summary.txt" <<EOF
status=OUTCOME_BLIND_MONITOR_RENEWAL_V5_PASS
control_commit=${control_commit}
source_script_sha256=${source_sha}
guard_script_sha256=${guard_sha}
baseline_latest=${baseline}
old_intake_pid=${old_intake_pid}
new_intake_pid=${intake_pid}
transition_pid=${transition_pid}
receipt_pid=${receipt_pid}
config_pid=${config_pid}
target300_pid=${target_pid}
wl_pid=${wl_pid}
guard_pid=${guard_pid}
guard_state=${guard_state}
old_guard_failure=rc1_after_poll71_and_intake_normal_145_poll_completion
intake_segment_lines_at_receipt=${intake_segment_lines}
sidecar_contents_opened=false
prospective_values_read=false
outcomes_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
(
  cd "${root}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${root}"
trap - EXIT
cat "${root}/operation_summary.txt"
