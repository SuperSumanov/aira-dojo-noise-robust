#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly mode="${1:-check}"
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly control=/research/d7/spc/yzyang4/worktrees/prospective-intake-control-b20dd268
readonly commit=b20dd2682d609c0236c138c08797678cf31a2fc0
readonly script=${control}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh
readonly script_sha=ef6584493de0f5e14a08bde4cc9501f268e43fb04bfd889af438666b1948eead
readonly latest=bf7674a4a3aec4cde8eec3e3fec31f1410e0445e0096f8e9fada3fae8b0ce0d6
readonly source_archives=296
readonly old_pid=3451688
readonly baseline_log_sha=f23d96bf07514144ab40ea9bebb2619a41ce3038e7f71f23d37a931461efc503
readonly complete_sentinels=13
readonly pid_file=${state}/continuous_intake_monitor_20260821.pid
readonly log=${state}/logs/continuous_intake_monitor_20260821.log
readonly runner_lock=${state}/runner.lock
readonly result_root=/research/d7/spc/yzyang4/outcome-blind-intake-natural-renewal-20260902-v2

lock_is_free() {
  (exec 9<"${runner_lock}"; flock -n -s 9)
}

preflight() {
  test "${mode}" = check || test "${mode}" = run
  test "$(git -C "${control}" rev-parse HEAD)" = "${commit}"
  test -z "$(git -C "${control}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${script}" | awk '{print $1}')" = "${script_sha}"
  test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
  test "$(find "${source_root}" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' | wc -l)" = "${source_archives}"
  test ! -e "${state}/BASELINE_INVALID"
  test "$(tr -d '\r\n' <"${pid_file}")" = "${old_pid}"
  ! kill -0 "${old_pid}" 2>/dev/null
  lock_is_free
  test "$(sha256sum "${log}" | awk '{print $1}')" = "${baseline_log_sha}"
  test "$(grep -c 'PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE' "${log}")" = "${complete_sentinels}"
  tail -n 1 "${log}" | grep -Eq 'PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE polls=145 outcomes_read=false$'
  ! tail -n 3 "${log}" | grep -Eq 'PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_FAIL_CLOSED'
  test ! -e "${result_root}"
  printf 'PREFLIGHT_01_DIRECTION=outcome-blind append-only intake renewal only\n'
  printf 'PREFLIGHT_02_CONTROL_COMMIT=%s\n' "${commit}"
  printf 'PREFLIGHT_03_MONITOR_SHA256=%s\n' "${script_sha}"
  printf 'PREFLIGHT_04_INPUT=296 stable archive paths; LATEST and baseline log hash bound\n'
  printf 'PREFLIGHT_05_ESTIMAND=unchanged; no outcome metric and no historical backfill\n'
  printf 'PREFLIGHT_06_SECURITY=credential-first installed intake; umask077\n'
  printf 'PREFLIGHT_07_LEAKAGE=label outcome prediction identity and profile remain closed\n'
  printf 'PREFLIGHT_08_REPRO=clean exact control/scientific worktrees checked by installed monitor\n'
  printf 'PREFLIGHT_09_RESOURCES=CPU only; GPU/API/model-fit/base-update=0/0/0/0\n'
  printf 'PREFLIGHT_10_FAILURE=any drift or first-poll failure terminates fail-closed\n'
  printf 'PREFLIGHT_11_STOP=one fixed 145-poll cycle; no result-conditioned stopping\n'
  printf 'OLD_PID=%s LIVE=false LATEST=%s SOURCE_ARCHIVES=%s\n' "${old_pid}" "${latest}" "${source_archives}"
}

preflight
if [[ "${mode}" == check ]]; then
  exit 0
fi

mkdir -m 0700 "${result_root}"
new_pid=''
on_exit() {
  rc=$?
  if (( rc != 0 )); then
    if [[ "${new_pid}" =~ ^[0-9]+$ ]] && kill -0 "${new_pid}" 2>/dev/null; then
      kill "${new_pid}" 2>/dev/null || true
      wait "${new_pid}" 2>/dev/null || true
    fi
    printf '%s\n' "${rc}" >"${result_root}/FAILED_RC"
  fi
}
trap on_exit EXIT

before_lines="$(wc -l <"${log}")"
before_bytes="$(stat -c %s "${log}")"
bash "${script}" --initialize "${control}" "${commit}" >"${result_root}/initialize.stdout" 2>"${result_root}/initialize.stderr"
new_pid="$(tr -d '\r\n' <"${pid_file}")"
[[ "${new_pid}" =~ ^[0-9]+$ ]]
test "${new_pid}" != "${old_pid}"
kill -0 "${new_pid}"
cmdline="$(tr '\0' ' ' <"/proc/${new_pid}/cmdline")"
grep -Fq "${script} --run ${control} ${commit}" <<<"${cmdline}"

poll_zero_complete=false
for _ in $(seq 1 90); do
  if tail -n "+$((before_lines + 1))" "${log}" | grep -Fq 'poll_end=0 rc=0'; then
    poll_zero_complete=true
    break
  fi
  kill -0 "${new_pid}"
  sleep 1
done
test "${poll_zero_complete}" = true
test "$(head -c "${before_bytes}" "${log}" | sha256sum | awk '{print $1}')" = "${baseline_log_sha}"
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
test "$(find "${source_root}" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' | wc -l)" = "${source_archives}"

cat >"${result_root}/safe_receipt.txt" <<EOF
status=OUTCOME_BLIND_INTAKE_NATURAL_COMPLETION_RENEWED_V2
renewed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${commit}
monitor_script_sha256=${script_sha}
baseline_log_sha256=${baseline_log_sha}
baseline_log_bytes=${before_bytes}
baseline_log_lines=${before_lines}
old_pid=${old_pid}
new_pid=${new_pid}
latest=${latest}
source_archives=${source_archives}
first_new_poll_rc=0
outcomes_read=false
candidate_profile_or_private_identity_read=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
chmod 0400 "${result_root}/safe_receipt.txt" "${result_root}/initialize.stdout" "${result_root}/initialize.stderr"
sha256sum "${result_root}/safe_receipt.txt" "${result_root}/initialize.stdout" "${result_root}/initialize.stderr" >"${result_root}/SHA256SUMS"
chmod 0400 "${result_root}/SHA256SUMS"
printf 'OUTCOME_BLIND_INTAKE_RENEWAL_V2=PASS\nNEW_PID=%s\nLATEST=%s\nSOURCE_ARCHIVES=%s\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${new_pid}" "${latest}" "${source_archives}"
