#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

readonly control_commit=${TASK_BALANCE_SUPERVISOR_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/supervise_task_balance_v3_v4_to_v5_20260828.sh
readonly continuation_path=phase1/scripts/resume_task_balance_v3_first_successor_after_v4_20260828.sh
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly previous=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v4
readonly next=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5
readonly launcher=${next}.launcher
readonly root=/research/d7/spc/yzyang4/task-balance-v3-first-successor/supervisor-v4-to-v5-v1
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

finish_success() {
  local credential_files filename_hits
  filename_hits=$(find "${root}" -type f -printf '%f\n' \
    | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
  test "${filename_hits}" = 0
  credential_files=$(grep -R -E -i -l "${credential_pattern}" "${root}" \
    --exclude=security_scan_receipt.txt --exclude=SHA256SUMS || true)
  test -z "${credential_files}"
  printf '%s\n' \
    'boundary_aware_credential_file_hits=0' \
    'credential_filename_hits=0' \
    'prospective_outcomes_or_prediction_values_read=false' \
    'gpu_api_model_fit_base_update=0/0/0/0' \
    > "${root}/security_scan_receipt.txt"
  (
    cd "${root}"
    find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
      | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
    touch COMPLETE
  )
  chmod -R a-w "${root}"
  trap - EXIT
  exit 0
}

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'TASK_BALANCE_SUPERVISOR_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
mkdir -p "${root}"
exec 9>"${root}/supervisor.lock"
flock -n 9
printf '%s\n' "$$" > "${root}/supervisor.pid"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${root}/FAILED_RC"; fi; exit "${rc}"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

git -C "${repo}" fetch fork phase1-value-critic > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
remote_head=$(git -C "${repo}" rev-parse fork/phase1-value-critic)
git -C "${repo}" cat-file -e "${control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${control_commit}" "${remote_head}"
git -C "${repo}" show "${control_commit}:${public_path}" > "${root}/source_script.sh"
cmp "$0" "${root}/source_script.sh"
git -C "${repo}" show "${control_commit}:${continuation_path}" > "${root}/continuation_script.sh"

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_goal=wait for the authoritative v4 latch and launch exactly one v5 continuation only after clean timeout; PASS
03_control_commit=${control_commit}; PASS
04_remote_head_at_start=${remote_head}; PASS
05_previous_root=${previous}; PASS
06_next_root=${next}; PASS
07_duplicate_control=non-authoritative earlier observer is never consumed; PASS
08_selection=no snapshot or candidate value accepted from caller; PASS
09_handoff=v5 exact Git object validates prior timeout and preserves any prior candidate; PASS
10_forbidden=no label,outcome,prediction value,accuracy,effect,utility,raw archive read; PASS
11_resources=CPU state watcher only,GPU/API/model-fit/base-update 0/0/0/0; PASS
12_failure=prior failure,duplicate next root,held prior lock after timeout,or dead launched PID fails closed; PASS
13_output=status and launch receipts only,no balance values or classification; PASS
EOF

for poll in $(seq 0 4320); do
  if test -f "${previous}/COMPLETE"; then
    test -f "${previous}/READY"
    test ! -e "${previous}/FAILED_RC"
    test ! -e "${next}"
    printf '%s\n' \
      'status=AUTHORITATIVE_V4_COMPLETE_NO_V5_LAUNCHED' \
      "completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "control_commit=${control_commit}" \
      'formal_run_pending=true' \
      'balance_values_or_classification_read=false' \
      'gpu_api_model_fit_base_update=0/0/0/0' \
      > "${root}/READY"
    finish_success
  fi
  if test -e "${previous}/FAILED_RC"; then
    printf '%s prior_failed rc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$(tr -d '\r\n' < "${previous}/FAILED_RC")" >> "${root}/monitor.log"
    exit 3
  fi
  if test -f "${previous}/TIMEOUT_RC"; then
    test "$(tr -d '\r\n' < "${previous}/TIMEOUT_RC")" = 124
    previous_pid=$(tr -d '\r\n' < "${previous}/monitor.pid")
    for settle in $(seq 0 60); do
      if ! kill -0 "${previous_pid}" 2>/dev/null && flock -n "${previous}/monitor.lock" true; then
        break
      fi
      test "${settle}" -lt 60
      sleep 1
    done
    test ! -e "${next}"
    test ! -e "${launcher}"
    mkdir -p "${launcher}"
    nohup env TASK_BALANCE_HANDOFF_CONTROL_COMMIT="${control_commit}" \
      bash "${root}/continuation_script.sh" \
      > "${launcher}/stdout" 2> "${launcher}/stderr" < /dev/null &
    launched_pid=$!
    printf '%s\n' "${launched_pid}" > "${launcher}/pid"
    sleep 5
    kill -0 "${launched_pid}"
    test -f "${next}/monitor.pid"
    test "$(tr -d '\r\n' < "${next}/monitor.pid")" = "${launched_pid}"
    ! flock -n "${next}/monitor.lock" true
    printf '%s\n' \
      'status=AUTHORITATIVE_V4_TIMEOUT_V5_LAUNCHED' \
      "launched_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "control_commit=${control_commit}" \
      "v5_pid=${launched_pid}" \
      "continuation_script_sha256=$(sha256sum "${root}/continuation_script.sh" | awk '{print $1}')" \
      'balance_values_or_classification_read=false' \
      'gpu_api_model_fit_base_update=0/0/0/0' \
      > "${root}/READY"
    finish_success
  fi
  printf '%s waiting poll=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" >> "${root}/monitor.log"
  sleep 5
done

printf '%s\n' 124 > "${root}/TIMEOUT_RC"
trap - EXIT
exit 0
