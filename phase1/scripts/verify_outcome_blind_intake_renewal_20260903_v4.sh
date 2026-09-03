#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly control=/research/d7/spc/yzyang4/worktrees/prospective-intake-control-b20dd268
readonly commit=b20dd2682d609c0236c138c08797678cf31a2fc0
readonly monitor=${control}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh
readonly monitor_sha=ef6584493de0f5e14a08bde4cc9501f268e43fb04bfd889af438666b1948eead
readonly latest=55aae3150a3e7b91533bf392d9b3b40fc00a20e33545808f80d11e4a656c6ae7
readonly source_archives=306
readonly baseline_log_sha=ee4630d5ff729718eb99b6bd5a5b1b899cd7657ac1aaa7746a30d81fd3081188
readonly pid_file=${state}/continuous_intake_monitor_20260821.pid
readonly log=${state}/logs/continuous_intake_monitor_20260821.log
readonly result_root=/research/d7/spc/yzyang4/outcome-blind-intake-natural-renewal-20260903-v4

test -d "${result_root}" && test ! -L "${result_root}"
test ! -e "${result_root}/FAILED_RC"
(cd "${result_root}" && sha256sum -c SHA256SUMS >/dev/null)
test "$(git -C "${control}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${control}" status --porcelain --untracked-files=all)"
test "$(sha256sum "${monitor}" | awk '{print $1}')" = "${monitor_sha}"

receipt=${result_root}/safe_receipt.txt
new_pid=$(awk -F= '$1=="new_pid" {print $2}' "${receipt}")
before_bytes=$(awk -F= '$1=="baseline_log_bytes" {print $2}' "${receipt}")
before_lines=$(awk -F= '$1=="baseline_log_lines" {print $2}' "${receipt}")
[[ "${new_pid}" =~ ^[0-9]+$ && "${before_bytes}" =~ ^[0-9]+$ && "${before_lines}" =~ ^[0-9]+$ ]]
test "$(tr -d '\r\n' <"${pid_file}")" = "${new_pid}"
kill -0 "${new_pid}"
cmdline=$(tr '\0' ' ' <"/proc/${new_pid}/cmdline")
grep -Fq "${monitor} --run ${control} ${commit}" <<<"${cmdline}"
test "$(head -c "${before_bytes}" "${log}" | sha256sum | awk '{print $1}')" = "${baseline_log_sha}"
tail -n "+$((before_lines + 1))" "${log}" | grep -Fq 'poll_end=0 rc=0'
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
test "$(find "${source_root}" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' | wc -l)" = "${source_archives}"
grep -Fxq 'first960_runs=589' "${receipt}"
grep -Fxq 'outcomes_read=false' "${receipt}"
grep -Fxq 'candidate_profile_or_private_identity_read=false' "${receipt}"
grep -Fxq 'gpu_paid_api_model_fit_base_update=0/0/0/0' "${receipt}"

printf 'INDEPENDENT_RENEWAL_V4_VERIFICATION=PASS\n'
printf 'NEW_PID=%s LIVE=true\n' "${new_pid}"
printf 'LATEST=%s SOURCE_ARCHIVES=%s\n' "${latest}" "${source_archives}"
printf 'OUTCOME_LABEL_PREDICTION_IDENTITY_PROFILE_READ=false\n'
