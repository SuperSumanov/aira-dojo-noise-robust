#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly mode="${1:-check}"
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly selection_sha=0277463211df467fb241776d975b4afab0133009f75f8b9cd53d15785341170f
readonly selection_pid_expected=2930562
readonly prior_context_sha=eec0154fa8528e9d75a8befd2861bcec0dafb7a696f1aec8029446e22928f508
readonly renewal_context=post_gap_repeat_timeout_renewal_1_context.txt

readonly stage=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-monitor-4fc9c3e-selection-v1
readonly stage_output=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-4fc9c3e-selection-v1
readonly stage_old_pid=2931879
readonly stage_commit=4fc9c3e4c9629ac86960a9cca198569e6a80ee2c
readonly stage_execution=66937a1f82ff4d427b382f5bb2ce15481f40d2a3fd7777c84d6596a2cef15856
readonly stage_protocol=b3df170ebb4ae097549cb0225142e94aebfa481aea6c79815f1be2af687d9e1d
readonly stage_producer=63095d5a33f7094a9e79c662913b7fa80c3d07a6308f3db1a10537a21c76a5cf
readonly stage_verifier=ccb7e375f255a22144b9363c6a07b10af0c87048976cdc3676f870be4fb8ba6e
readonly stage_test=44c0d110ae7030d2061dd2a08645b320ce0d190015478ee8a18c59636ba3c069
readonly stage_runner=9b44ffb82739035601665df11d366b8c1a3570cfad767bf728ef83a291e6e4bc
readonly stage_monitor=aef2aff4d1b367c19ba77675374f2d1671bc550ba8ab7fa5ece495971e5d4470

readonly rank=/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-monitor-984876f-v1
readonly rank_output=/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-984876f-v1
readonly rank_old_pid=2931942
readonly rank_commit=984876ff8ca812af64fe9c761180ecf78cf33ff1
readonly rank_execution=50baf5c7a31c9be8786e8f1cabce1f3b9d89834a0a0a508d6a76b5e4e99b41ac
readonly rank_protocol=3c8b8f87b43cae74a57c28d78e3428d824f54969051fadf5086810da467ad323
readonly rank_analyzer=120e55269fde767cdbe3f036bc28a6293788e72c83972529fbef9c48e0274c41
readonly rank_verifier=92ab4533d72d8bd73b75e7ef266798ecf7d25ca4d454ada0571488028695ff93
readonly rank_test=a4e82a14b4f8d3e05174bc2639bafe22e46fec1d3ef5c3c05b7c0b8019818205
readonly rank_runner=dd462b22f85157ebb4172c0d8653656fcf8b8dbbdf98fd7e466412fbb383b794
readonly rank_monitor=11d753a58ecf811a74d371aa759825103b4f2e4f2765072efcaad92ba509b51e

verify_selection() {
  test "$(sha256sum "${selection}/observed.tsv" | awk '{print $1}')" = "${selection_sha}"
  test "$(wc -l <"${selection}/observed.tsv")" = 29
  test "$(tail -n 1 "${selection}/observed.tsv" | cut -f2)" = 517
  test ! -e "${selection}/COMPLETE"
  test ! -e "${selection}/FAILED_RC"
  test ! -e "${selection}/TIMEOUT_RC"
  test ! -e "${selection}/CONTINUITY_GAP"
  test "$(tr -d '\r\n' <"${selection}/monitor.pid")" = "${selection_pid_expected}"
  kill -0 "${selection_pid_expected}"
  if flock -n "${selection}/monitor.lock" true; then return 1; fi
}

verify_waiter() {
  local root="$1" old_pid="$2" source_sha="$3" runner_sha="$4" execution_sha="$5"
  test -d "${root}" && test ! -L "${root}"
  test ! -e "${root}/COMPLETE"
  test ! -e "${root}/FAILED_RC"
  test ! -e "${root}/INTERRUPTED_RC"
  test -f "${root}/TIMEOUT_RC"
  test "$(tr -d '\r\n' <"${root}/TIMEOUT_RC")" = 124
  ! kill -0 "${old_pid}" 2>/dev/null
  flock -n "${root}/monitor.lock" true
  test "$(sha256sum "${root}/source_script.sh" | awk '{print $1}')" = "${source_sha}"
  test "$(sha256sum "${root}/formal_runner.sh" | awk '{print $1}')" = "${runner_sha}"
  test "$(sha256sum "${root}/execution_protocol.json" | awk '{print $1}')" = "${execution_sha}"
  test "$(sha256sum "${root}/post_gap_resume_context.txt" | awk '{print $1}')" = "${prior_context_sha}"
  test ! -e "${root}/${renewal_context}"
}

preflight() {
  test "${mode}" = check || test "${mode}" = run
  verify_selection
  verify_waiter "${stage}" "${stage_old_pid}" "${stage_monitor}" "${stage_runner}" "${stage_execution}"
  verify_waiter "${rank}" "${rank_old_pid}" "${rank_monitor}" "${rank_runner}" "${rank_execution}"
  test ! -e "${stage_output}"
  test ! -e "${rank_output}"
  git -C "${repo}" fetch fork phase1-value-critic >/dev/null
  git -C "${repo}" merge-base --is-ancestor "${stage_commit}" fork/phase1-value-critic
  git -C "${repo}" merge-base --is-ancestor "${rank_commit}" fork/phase1-value-critic
  test "$(git -C "${repo}" show "${stage_commit}:phase1/vertex_cost_contrast_target522_effect_v1.json" | sha256sum | awk '{print $1}')" = "${stage_protocol}"
  test "$(git -C "${repo}" show "${stage_commit}:phase1/freeze_vertex_cost_contrast_target522_selection.py" | sha256sum | awk '{print $1}')" = "${stage_producer}"
  test "$(git -C "${repo}" show "${stage_commit}:phase1/verify_vertex_cost_contrast_target522_selection.py" | sha256sum | awk '{print $1}')" = "${stage_verifier}"
  test "$(git -C "${repo}" show "${stage_commit}:phase1/tests/test_vertex_cost_contrast_target522_runner.py" | sha256sum | awk '{print $1}')" = "${stage_test}"
  test "$(git -C "${repo}" show "${rank_commit}:phase1/target522_linear_contrast_rank_audit_v1.json" | sha256sum | awk '{print $1}')" = "${rank_protocol}"
  test "$(git -C "${repo}" show "${rank_commit}:phase1/audit_target522_linear_contrast_rank.py" | sha256sum | awk '{print $1}')" = "${rank_analyzer}"
  test "$(git -C "${repo}" show "${rank_commit}:phase1/verify_target522_linear_contrast_rank.py" | sha256sum | awk '{print $1}')" = "${rank_verifier}"
  test "$(git -C "${repo}" show "${rank_commit}:phase1/tests/test_target522_linear_contrast_rank.py" | sha256sum | awk '{print $1}')" = "${rank_test}"
  printf 'TARGET522_REPEAT_TIMEOUT_RENEWAL_PREFLIGHT=PASS\n'
  printf 'SELECTION_RUNS=517 REMAINING=5 OLD_STAGE_PID=%s OLD_RANK_PID=%s\n' "${stage_old_pid}" "${rank_old_pid}"
  printf 'OUTCOMES_READ=false IDENTITIES_READ=false GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'
}

preflight
if [[ "${mode}" == check ]]; then
  exit 0
fi

stage_before="$(wc -l <"${stage}/monitor.log")"
rank_before="$(wc -l <"${rank}/monitor.log")"
renewed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
for root in "${stage}" "${rank}"; do
  cat >"${root}/${renewal_context}" <<EOF
status=RENEW_AFTER_SECOND_NATURAL_TIMEOUT
renewed_at_utc=${renewed_at}
previous_timeout_rc=124
prior_context_sha256=${prior_context_sha}
selection_observed_sha256=${selection_sha}
selection_runs=517
selection_target_runs=522
selection_remaining_runs=5
selection_pid=${selection_pid_expected}
selection_lock_held=true
selection_continuity_gap=false
prospective_values_read=false
candidate_profile_or_private_identity_read=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
  chmod 0400 "${root}/${renewal_context}"
done

nohup bash "${stage}/source_script.sh" resume "${stage}" "${stage_commit}" \
  "${stage_execution}" "${stage_protocol}" "${stage_producer}" "${stage_verifier}" \
  "${stage_test}" "${stage_runner}" "${stage_monitor}" \
  >"${stage}/resume_after_repeat_timeout_1.stdout" 2>"${stage}/resume_after_repeat_timeout_1.stderr" </dev/null &
stage_pid=$!

for _ in $(seq 1 30); do
  if kill -0 "${stage_pid}" 2>/dev/null \
    && test "$(tr -d '\r\n' <"${stage}/monitor.pid")" = "${stage_pid}" \
    && ! flock -n "${stage}/monitor.lock" true; then
    break
  fi
  sleep 1
done
kill -0 "${stage_pid}"
test "$(tr -d '\r\n' <"${stage}/monitor.pid")" = "${stage_pid}"
if flock -n "${stage}/monitor.lock" true; then exit 1; fi
test ! -e "${stage}/TIMEOUT_RC"
test ! -e "${stage}/FAILED_RC"

nohup bash "${rank}/source_script.sh" resume "${rank}" "${rank_commit}" \
  "${rank_execution}" "${rank_protocol}" "${rank_analyzer}" "${rank_verifier}" \
  "${rank_test}" "${rank_runner}" "${rank_monitor}" \
  >"${rank}/resume_after_repeat_timeout_1.stdout" 2>"${rank}/resume_after_repeat_timeout_1.stderr" </dev/null &
rank_pid=$!

for _ in $(seq 1 30); do
  if kill -0 "${rank_pid}" 2>/dev/null \
    && test "$(tr -d '\r\n' <"${rank}/monitor.pid")" = "${rank_pid}" \
    && ! flock -n "${rank}/monitor.lock" true; then
    break
  fi
  sleep 1
done

for tuple in "${stage}:${stage_pid}:${stage_before}" "${rank}:${rank_pid}:${rank_before}"; do
  root="${tuple%%:*}"
  rest="${tuple#*:}"
  pid="${rest%%:*}"
  before="${rest##*:}"
  kill -0 "${pid}"
  test "$(tr -d '\r\n' <"${root}/monitor.pid")" = "${pid}"
  if flock -n "${root}/monitor.lock" true; then exit 1; fi
  test ! -e "${root}/TIMEOUT_RC"
  test ! -e "${root}/FAILED_RC"
  test ! -e "${root}/INTERRUPTED_RC"
  test ! -e "${root}/COMPLETE"
  test "$(sha256sum "${root}/post_gap_resume_context.txt" | awk '{print $1}')" = "${prior_context_sha}"
  test -s "${root}/${renewal_context}"
  tail -n "+$((before + 1))" "${root}/monitor.log" | grep -Eq 'waiting poll=[0-9]+ .*prospective_values_read=false'
done

verify_selection
printf 'TARGET522_REPEAT_TIMEOUT_RENEWAL=PASS\nSTAGE_PID=%s\nRANK_PID=%s\nSELECTION_RUNS=517\nREMAINING=5\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${stage_pid}" "${rank_pid}"
