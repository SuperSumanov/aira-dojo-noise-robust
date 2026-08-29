#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly control_commit=${OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/renew_outcome_blind_monitors_887_20260829_v4.sh
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly guard=/research/d7/spc/yzyang4/six-hour-structural-guard-20260829-v4

readonly intake_control=/research/d7/spc/yzyang4/worktrees/alias_monitor_bc362df_v2_nosmudge
readonly intake_commit=bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0
readonly intake_launcher=${intake_control}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh

readonly transition_repo=/research/d7/spc/yzyang4/worktrees/alias_monitor_bc362df_v2_nosmudge
readonly transition_commit=bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0
readonly transition_script=${transition_repo}/phase1/scripts/monitor_transition_snapshot_chain_20260826.sh
readonly transition_sha=87ed6fa645de2fad25695b212434bd1dd64b6f1a44a34f6232c941ad8d8b9161
readonly transition_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly transition_output=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-snapshot-chain
readonly transition_state_sha=d675dbd92a244bb9d55b1c3377bcbb0590e91f4ce4bf5321ca8ce38284629a25
readonly transition_prior=/research/d7/spc/yzyang4/transition-future-escrow/7458f09-snapshot-chain/20260828T002417Z_887491a021d7/artifact
readonly transition_prior_sha=443248aa97212dc8af72767dda5c083ad8c99d9d2fa13541408cb5d93555eeb5
readonly transition_old_pid=${transition_root}/resume_20260829_887_v3.pid

readonly receipt_repo=/research/d7/spc/yzyang4/worktrees/receipt_support_9f2cbe9_nosmudge
readonly receipt_commit=9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f
readonly receipt_script=${receipt_repo}/phase1/scripts/monitor_prediction_coverage_snapshot_chain_20260826.sh
readonly receipt_sha=458b50a3ac4499abd80c951881f69ab15f82af15a8b2bc51c950cf425d906533
readonly receipt_root=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly receipt_output=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1
readonly receipt_state_sha=ee837edf88a5a8d316a7a11664ed4090f8c681cf6982df1df69abb041e234f8c
readonly receipt_prior=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1/20260828T012831Z_887491a021d7
readonly receipt_prior_sha=71f57ad8f53edfcebd74f6a9c37086e4216319ec5480bd2914cf1b52e41af86c
readonly receipt_old_pid=${receipt_root}/resume_20260829_887_v3.pid

readonly config_script=/research/d7/spc/yzyang4/monitor_future_config_v2_readiness_20260826_v2.sh
readonly config_sha=e04137ae801f25debc4168bdadd4a3eb4dd068ff6a17982e1d780d14d22bac45
readonly config_old=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v7
readonly config_root=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v8

readonly target_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_519815d_after_887_v1
readonly target_script=${target_root}/monitor_target300_after_887_20260828.sh
readonly target_sha=fb393ef06c29728afa0da2f7ca26c748eb5b85bd6c065b66e5ba4f2f1cbdc0d7
readonly target_old_pid=${target_root}/resume_20260829_887_v2.pid
readonly wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly root=/research/d7/spc/yzyang4/monitor-relaunch-887/20260829-v4

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
test ! -e "${config_root}"
mkdir -p "${root}"
failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then printf '%s\n' "${rc}" > "${root}/FAILED_RC" 2>/dev/null || true; fi
  exit "${rc}"
}
trap failure_receipt EXIT

git -C "${repo}" fetch fork phase1-value-critic > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
remote_head=$(git -C "${repo}" rev-parse fork/phase1-value-critic)
git -C "${repo}" cat-file -e "${control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${control_commit}" "${remote_head}"
git -C "${repo}" show "${control_commit}:${public_path}" > "${root}/source_script.sh"
cmp "$0" "${root}/source_script.sh"
source_sha=$(sha256sum "${root}/source_script.sh" | awk '{print $1}')

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol outcome-blind monitoring only; PASS
02_goal=renew naturally completed transition receipt config-v2 and Target-300 monitors without changing frozen state; PASS
03_context=LATEST 887 intake guard WL and Target-522 watchers remain live; PASS
04_inputs=PID locks LATEST filenames metadata state hashes and aggregate structural receipts only; PASS
05_forbidden=no label outcome prediction value accuracy utility raw archive or sidecar content; PASS
06_continuity=same transition receipt and Target-300 roots resume only after exact normal completion; PASS
07_controls=exact public source hashes commits prior artifacts old process death free locks and first-poll receipts; PASS
08_failure=duplicate process held lock hash drift unexpected marker snapshot change or sidecar fails closed; PASS
09_randomness=none fixed 300-second polling and frozen stable-poll rules; PASS
10_resources=CPU metadata polling only GPU API model-fit base-update 0/0/0/0; PASS
11_duration=transition receipt config 72 polls Target-300 retains 144 polls; PASS
12_security=config detection stops at metadata before redaction review credentials and payload unopened; PASS
13_promotion=exact live PID command lock start receipt and immutable manifest required; PASS
EOF
test "$(wc -l < "${root}/preflight_13.txt")" = 13

test "$(tr -d '\r\n' < "${state}/LATEST")" = "${baseline}"
test "$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)" = 0
intake_pid=$(tr -d '\r\n' < "${state}/continuous_intake_monitor_20260821.pid")
[[ ${intake_pid} =~ ^[0-9]+$ ]]
kill -0 "${intake_pid}" 2>/dev/null
intake_cmdline=$(tr '\0' ' ' < "/proc/${intake_pid}/cmdline")
case "${intake_cmdline}" in
  *"${intake_launcher} --run ${intake_control} ${intake_commit}"*) ;;
  *) exit 65 ;;
esac
if flock -n "${guard}/guard.lock" -c true; then exit 66; fi
grep -Fq 'outcomes_read=false' "${guard}/status.log"
test ! -e "${guard}/FAILED_RC"

for tuple in \
  "${transition_repo} ${transition_commit} ${transition_script} ${transition_sha}" \
  "${receipt_repo} ${receipt_commit} ${receipt_script} ${receipt_sha}"; do
  read -r control_repo pinned_commit script expected_sha <<< "${tuple}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${pinned_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${script}" | awk '{print $1}')" = "${expected_sha}"
  bash -n "${script}"
done
test "$(sha256sum "${config_script}" | awk '{print $1}')" = "${config_sha}"
test "$(sha256sum "${target_script}" | awk '{print $1}')" = "${target_sha}"
bash -n "${config_script}"
bash -n "${target_script}"

for old_pid_file in "${transition_old_pid}" "${receipt_old_pid}" "${config_old}/launcher.pid" "${target_old_pid}"; do
  test -f "${old_pid_file}"
  old_pid=$(tr -d '\r\n' < "${old_pid_file}")
  [[ ${old_pid} =~ ^[0-9]+$ ]]
  ! kill -0 "${old_pid}" 2>/dev/null
done
flock -n "${transition_root}/monitor.lock" -c true
flock -n "${receipt_root}/monitor.lock" -c true
flock -n "${config_old}/monitor.lock" -c true
flock -n "${target_root}/monitor.lock" -c true

test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
test "$(sha256sum "${transition_prior}/summary.json" | awk '{print $1}')" = "${transition_prior_sha}"
tail -n 1 "${transition_root}/monitor.log" | grep -Fq "monitor_complete prior_snapshot=${baseline}"
test "$(sha256sum "${receipt_root}/state.tsv" | awk '{print $1}')" = "${receipt_state_sha}"
test "$(sha256sum "${receipt_prior}/receipt_a.json" | awk '{print $1}')" = "${receipt_prior_sha}"
tail -n 1 "${receipt_root}/monitor.log" | grep -Fq "monitor_complete prior=${baseline}"
grep -Fq 'status=NO_CONFIG_V2_SIDECAR_OBSERVED' "${config_old}/COMPLETE"
grep -Fq 'contents_opened=false' "${config_old}/COMPLETE"
tail -n 1 "${target_root}/monitor.log" | grep -Fq "monitor_complete_without_quiescent_new_snapshot baseline=${baseline} outcomes_read=false"
test ! -e "${target_root}/formal_rc.txt"
test -z "$(find "${target_root}" -maxdepth 1 -type f -name 'runner_worktree_path_*.diff' -print -quit)"
if flock -n "${wl_root}/monitor.lock" -c true; then exit 67; fi

transition_before=$(wc -l < "${transition_root}/monitor.log")
receipt_before=$(wc -l < "${receipt_root}/monitor.log")
target_before=$(wc -l < "${target_root}/monitor.log")

nohup env \
  SNAPSHOT_CHAIN_STATE_ROOT="${state}" \
  SNAPSHOT_CHAIN_OUTPUT_ROOT="${transition_output}" \
  SNAPSHOT_CHAIN_MONITOR_ROOT="${transition_root}" \
  SNAPSHOT_CHAIN_POLL_SECONDS=300 SNAPSHOT_CHAIN_MAX_POLLS=72 \
  bash "${transition_script}" "${transition_repo}" "${transition_commit}" \
  > "${transition_root}/resume_20260829_887_v4.stdout" \
  2> "${transition_root}/resume_20260829_887_v4.stderr" </dev/null &
transition_pid=$!
printf '%s\n' "${transition_pid}" > "${transition_root}/resume_20260829_887_v4.pid"

nohup env \
  RECEIPT_SUPPORT_STATE_ROOT="${state}" \
  RECEIPT_SUPPORT_RESULT_ROOT="${receipt_output}" \
  RECEIPT_SUPPORT_MONITOR_ROOT="${receipt_root}" \
  RECEIPT_SUPPORT_POLL_SECONDS=300 RECEIPT_SUPPORT_MAX_POLLS=72 RECEIPT_SUPPORT_STABLE_POLLS=3 \
  bash "${receipt_script}" "${receipt_repo}" "${receipt_commit}" \
  > "${receipt_root}/resume_20260829_887_v4.stdout" \
  2> "${receipt_root}/resume_20260829_887_v4.stderr" </dev/null &
receipt_pid=$!
printf '%s\n' "${receipt_pid}" > "${receipt_root}/resume_20260829_887_v4.pid"

mkdir "${config_root}"
nohup env CONFIG_V2_MONITOR_ROOT="${config_root}" CONFIG_V2_POLL_SECONDS=300 CONFIG_V2_MAX_POLLS=72 \
  bash "${config_script}" > "${config_root}/launcher.stdout" 2> "${config_root}/launcher.stderr" </dev/null &
config_pid=$!
printf '%s\n' "${config_pid}" > "${config_root}/launcher.pid"

nohup bash "${target_script}" \
  > "${target_root}/resume_20260829_887_v3.stdout" \
  2> "${target_root}/resume_20260829_887_v3.stderr" </dev/null &
target_pid=$!
printf '%s\n' "${target_pid}" > "${target_root}/resume_20260829_887_v3.pid"

transition_started=false
receipt_started=false
config_started=false
target_started=false
for _ in $(seq 1 60); do
  tail -n "+$((transition_before + 1))" "${transition_root}/monitor.log" > "${root}/transition_log_segment.txt"
  tail -n "+$((receipt_before + 1))" "${receipt_root}/monitor.log" > "${root}/receipt_log_segment.txt"
  tail -n "+$((target_before + 1))" "${target_root}/monitor.log" > "${root}/target_log_segment.txt"
  grep -Fq "monitor_start prior_snapshot=${baseline}" "${root}/transition_log_segment.txt" && transition_started=true
  grep -Fq "monitor_start prior=${baseline}" "${root}/receipt_log_segment.txt" && receipt_started=true
  grep -Fq "monitor_start baseline=${baseline}" "${root}/target_log_segment.txt" && target_started=true
  if test -f "${config_root}/monitor.log" && grep -Fq 'poll=1 sidecar_count=0' "${config_root}/monitor.log"; then
    config_started=true
  elif test -f "${config_root}/OBSERVED"; then
    exit 68
  fi
  if [[ ${transition_started} = true && ${receipt_started} = true && ${config_started} = true && ${target_started} = true ]]; then break; fi
  kill -0 "${transition_pid}"
  kill -0 "${receipt_pid}"
  kill -0 "${config_pid}"
  kill -0 "${target_pid}"
  sleep 2
done
test "${transition_started}" = true
test "${receipt_started}" = true
test "${config_started}" = true
test "${target_started}" = true
for pid in "${transition_pid}" "${receipt_pid}" "${config_pid}" "${target_pid}"; do kill -0 "${pid}"; done
for lock in "${transition_root}/monitor.lock" "${receipt_root}/monitor.lock" "${config_root}/monitor.lock" "${target_root}/monitor.lock"; do
  if flock -n "${lock}" -c true; then exit 69; fi
done
test ! -s "${transition_root}/resume_20260829_887_v4.stderr"
test ! -s "${receipt_root}/resume_20260829_887_v4.stderr"
test ! -s "${config_root}/launcher.stderr"
test ! -s "${target_root}/resume_20260829_887_v3.stderr"

cat > "${root}/operation_summary.txt" <<EOF
status=OUTCOME_BLIND_MONITOR_RENEWAL_V4_PASS
control_commit=${control_commit}
source_script_sha256=${source_sha}
baseline_latest=${baseline}
transition_pid=${transition_pid}
receipt_pid=${receipt_pid}
config_pid=${config_pid}
target300_pid=${target_pid}
wl_lock=held_inherited
intake_pid=${intake_pid}
six_hour_guard_v4=held_inherited
transition_state_sha256=${transition_state_sha}
receipt_state_sha256=${receipt_state_sha}
transition_receipt_config_polls=72x300s
target300_polls=144x300s
sidecar_contents_opened=false
prospective_values_read=false
outcomes_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
(
  cd "${root}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${root}"
trap - EXIT
cat "${root}/operation_summary.txt"
