#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly mode="${1:-check}"
readonly public_commit="${NOFIT_SUPPORT_RENEWAL_PUBLIC_COMMIT:-}"
readonly public_repo=/research/d7/spc/yzyang4/aira-dojo
readonly public_path=phase1/scripts/renew_outcome_blind_no_fit_support_20260901_v2.sh
readonly protocol_path=phase1/outcome_blind_no_fit_support_renewal_v2.json
readonly action_root=/research/d7/spc/yzyang4/outcome-blind-no-fit-support-renewal-20260901-v2

readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly latest=e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d
readonly prior=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly source_archives=283
readonly expected_all_physical_runs=543
readonly expected_eligible_runs=517
readonly expected_endpoints=13581
readonly expected_pairs=3325
readonly expected_tasks=38

readonly control=/research/d7/spc/yzyang4/worktrees/alias_monitor_bc362df_v2_nosmudge
readonly control_commit=bc362dfe95287f199f6bc4a1dc8f781f3b1b6ee0
readonly wl_script=${control}/phase1/scripts/monitor_wl_snapshot_chain_20260826.sh
readonly wl_script_sha=4cec4fd7cb2382f6e7f4e071b31212cfa45901de9dcfcc7730f18cad4e619daa
readonly wl_scorer_commit=031edb34400781ca026bc9833ac7f850312ffb1c
readonly wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly wl_output=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain
readonly wl_state_sha=d6fdf8658e72ff8bb100feb01cfb952c3d510eb8addfb651ff5b80b57c6fd363
readonly wl_log_sha=6b48b8b615f70aaf3cb4e60bc176d9a9ffae899fac208044354df3ac529fb0bd
readonly v1_partial_basename=20260901T122214Z_e9e12c639fde
readonly v1_partial=${wl_output}/${v1_partial_basename}

readonly receipt_control=/research/d7/spc/yzyang4/worktrees/receipt_support_9f2cbe9_nosmudge
readonly receipt_commit=9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f
readonly receipt_script=${receipt_control}/phase1/scripts/monitor_prediction_coverage_snapshot_chain_20260826.sh
readonly receipt_script_sha=458b50a3ac4499abd80c951881f69ab15f82af15a8b2bc51c950cf425d906533
readonly receipt_root=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly receipt_output=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1
readonly receipt_state_sha=6a1ac64a49221f3879a165e608b3cb8298aab221f3ff1bcd20764c1fe47d38bc
readonly receipt_log_sha=6e4379797c1d7edee3214b9fd242da7cca17658d2602d149686f25a15043d4f3

readonly transition_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly transition_state_sha=ac66b2deb9054b05e9fab803587d1ee38478f88cbadc86aebfa9f4a9f7ebad4e
readonly transition_log_sha=a23e382f0a8ccb2684dbd29bed68ae0ea1d61c7a6a1727f03195033697f9ec43
readonly intake_pid_file=${state}/continuous_intake_monitor_20260821.pid

readonly v1_action=/research/d7/spc/yzyang4/outcome-blind-no-fit-support-renewal-20260901-v1
readonly v1_deploy=/research/d7/spc/yzyang4/no-fit-support-deploy-7d89d1b-20260901-v1
readonly v2_deploy=/research/d7/spc/yzyang4/no-fit-support-deploy-7d89d1b-20260901-v2
readonly cleanup=/research/d7/spc/yzyang4/no-fit-support-v1-orphan-cleanup-20260901-v1
readonly cleanup_receipt_sha=45d186e7f0d8581820a928e26aed9d1497d6037f02dbbba34cf4a60b96518618

lock_is_free() {
  local path=$1
  test -f "${path}"
  test ! -L "${path}"
  (exec 8<"${path}"; flock -n -s 8)
}

all_pid_owners_dead() {
  local root=$1 pid_file pid
  while IFS= read -r pid_file; do
    pid=$(tr -cd '0-9' <"${pid_file}" || true)
    test -n "${pid}"
    ! kill -0 "${pid}" 2>/dev/null
  done < <(find "${root}" -maxdepth 1 -type f -name '*.pid' -print | LC_ALL=C sort)
}

assert_inventory() {
  /research/d7/spc/yzyang4/venvs/exp/bin/python - \
    "${state}/snapshots/${latest}/accumulator/summary.json" \
    "${expected_all_physical_runs}" "${expected_eligible_runs}" "${expected_endpoints}" \
    "${expected_pairs}" "${expected_tasks}" <<'PY'
import json
import pathlib
import sys
inventory = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["inventory"]
actual = (
    inventory["all_physical_runs"], inventory["eligible_runs"],
    inventory["eligible_endpoints"], inventory["eligible_structural_pairs"],
    inventory["eligible_tasks"],
)
assert actual == tuple(int(value) for value in sys.argv[2:])
PY
}

verify_public_binding() {
  [[ "${public_commit}" =~ ^[0-9a-f]{40}$ ]]
  test "$(sha256sum "$0" | awk '{print $1}')" = \
    "$(git -C "${public_repo}" show "${public_commit}:${public_path}" | sha256sum | awk '{print $1}')"
  [[ "$(git -C "${public_repo}" show "${public_commit}:${protocol_path}" | sha256sum | awk '{print $1}')" =~ ^[0-9a-f]{64}$ ]]
}

assert_failed_v1_chain() {
  test "$(sha256sum "${v1_action}/FAILED_RC" | awk '{print $1}')" = 4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865
  test "$(sha256sum "${v1_deploy}/FAILED_RC" | awk '{print $1}')" = 56292515f7d3a7110811eb8de26b3f75f82a0766aa5a1fd66ebcfcb84fe6d5ff
  test "$(sha256sum "${v2_deploy}/FAILED_RC" | awk '{print $1}')" = 4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865
  test "$(sha256sum "${cleanup}/safe_receipt.txt" | awk '{print $1}')" = "${cleanup_receipt_sha}"
  (cd "${cleanup}" && sha256sum -c SHA256SUMS >/dev/null)
  test ! -e "${v1_action}/safe_receipt.txt"
  test -d "${v1_partial}"
  test "$(find "${v1_partial}" -xdev -type f -printf '.' | wc -c)" = 28
  test ! -e "${v1_partial}/COMPLETE"
  test ! -e "${v1_partial}/FAILURE"
  test ! -e "${v1_partial}/producer.rc.txt"
}

preflight() {
  test "${mode}" = check || test "${mode}" = run
  command -v setsid >/dev/null
  verify_public_binding
  assert_failed_v1_chain
  test "$(git -C "${control}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control}" status --porcelain --untracked-files=all)"
  test "$(git -C "${receipt_control}" rev-parse HEAD)" = "${receipt_commit}"
  test -z "$(git -C "${receipt_control}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${wl_script}" | awk '{print $1}')" = "${wl_script_sha}"
  test "$(sha256sum "${receipt_script}" | awk '{print $1}')" = "${receipt_script_sha}"

  test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
  assert_inventory
  test "$(find "${source_root}" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' | wc -l)" = "${source_archives}"
  test "$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)" = 0

  test "$(sha256sum "${wl_root}/state.tsv" | awk '{print $1}')" = "${wl_state_sha}"
  test "$(sha256sum "${wl_root}/monitor.log" | awk '{print $1}')" = "${wl_log_sha}"
  test "$(cut -f1 "${wl_root}/state.tsv")" = "${prior}"
  test "$(cut -f4 "${wl_root}/state.tsv")" = 494
  all_pid_owners_dead "${wl_root}"
  lock_is_free "${wl_root}/monitor.lock"

  test "$(sha256sum "${receipt_root}/state.tsv" | awk '{print $1}')" = "${receipt_state_sha}"
  test "$(sha256sum "${receipt_root}/monitor.log" | awk '{print $1}')" = "${receipt_log_sha}"
  test "$(cut -f1 "${receipt_root}/state.tsv")" = "${prior}"
  all_pid_owners_dead "${receipt_root}"
  lock_is_free "${receipt_root}/monitor.lock"

  test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
  test "$(sha256sum "${transition_root}/monitor.log" | awk '{print $1}')" = "${transition_log_sha}"
  all_pid_owners_dead "${transition_root}"
  lock_is_free "${transition_root}/monitor.lock"

  intake_pid=$(tr -cd '0-9' <"${intake_pid_file}")
  [[ "${intake_pid}" =~ ^[0-9]+$ ]]
  kill -0 "${intake_pid}"
  grep -Fq 'run_prospective_continuous_intake_monitor_20260821.sh --run' \
    < <(tr '\0' ' ' <"/proc/${intake_pid}/cmdline")
  test ! -e "${action_root}"
  printf 'NOFIT_SUPPORT_RENEWAL_V2_PREFLIGHT=PASS\n'
  printf 'LATEST=%s PRIOR=%s ELIGIBLE_RUNS=%s DELTA=23 WL_MINIMUM_NEW_RUNS=12\n' \
    "${latest}" "${prior}" "${expected_eligible_runs}"
  printf 'V1_STATE_PROMOTION=false V1_ORPHANS_CLEARED=true TRANSITION_RESTARTED=false\n'
  printf 'GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0 VALUES_OUTCOMES_IDENTITIES_PROFILE_READ=false/false/false/false\n'
}

terminate_group() {
  local pid=$1
  if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -TERM -- "-${pid}" 2>/dev/null || true
  fi
}

await_group_exit() {
  local pid=$1
  for _ in $(seq 1 30); do
    if ! kill -0 "${pid}" 2>/dev/null; then return 0; fi
    sleep 1
  done
  kill -KILL -- "-${pid}" 2>/dev/null || true
  for _ in $(seq 1 10); do
    if ! kill -0 "${pid}" 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}

preflight
if [[ "${mode}" = check ]]; then exit 0; fi

mkdir -m 0700 "${action_root}"
wl_pid=''
receipt_pid=''
success=false
on_exit() {
  local rc=$?
  if [[ "${success}" != true ]]; then
    terminate_group "${wl_pid}"
    terminate_group "${receipt_pid}"
    if [[ "${wl_pid}" =~ ^[0-9]+$ ]]; then await_group_exit "${wl_pid}" || true; fi
    if [[ "${receipt_pid}" =~ ^[0-9]+$ ]]; then await_group_exit "${receipt_pid}" || true; fi
    printf '%s\n' "${rc}" >"${action_root}/FAILED_RC"
  fi
}
trap on_exit EXIT

wl_before=$(wc -l <"${wl_root}/monitor.log")
receipt_before=$(wc -l <"${receipt_root}/monitor.log")

setsid env WL_CHAIN_STATE_ROOT="${state}" WL_CHAIN_OUTPUT_ROOT="${wl_output}" \
  WL_CHAIN_MONITOR_ROOT="${wl_root}" WL_CHAIN_POLL_SECONDS=300 WL_CHAIN_MAX_POLLS=72 \
  WL_CHAIN_MINIMUM_NEW_RUNS=12 \
  bash "${wl_script}" "${control}" "${control_commit}" \
  >"${action_root}/wl.stdout" 2>"${action_root}/wl.stderr" </dev/null &
wl_pid=$!
printf '%s\n' "${wl_pid}" >"${wl_root}/renew_20260901_e9_no_fit_v2.pid"

setsid env RECEIPT_SUPPORT_STATE_ROOT="${state}" \
  RECEIPT_SUPPORT_WL_STATE="${wl_root}/state.tsv" \
  RECEIPT_SUPPORT_TRANSITION_STATE="${transition_root}/state.tsv" \
  RECEIPT_SUPPORT_RESULT_ROOT="${receipt_output}" \
  RECEIPT_SUPPORT_MONITOR_ROOT="${receipt_root}" \
  RECEIPT_SUPPORT_POLL_SECONDS=300 RECEIPT_SUPPORT_MAX_POLLS=72 RECEIPT_SUPPORT_STABLE_POLLS=3 \
  bash "${receipt_script}" "${receipt_control}" "${receipt_commit}" \
  >"${action_root}/receipt.stdout" 2>"${action_root}/receipt.stderr" </dev/null &
receipt_pid=$!
printf '%s\n' "${receipt_pid}" >"${receipt_root}/renew_20260901_e9_no_fit_v2.pid"

test "$(ps -o pgid= -p "${wl_pid}" | tr -d ' ')" = "${wl_pid}"
test "$(ps -o pgid= -p "${receipt_pid}" | tr -d ' ')" = "${receipt_pid}"

new_output=''
receipt_started=false
for _ in $(seq 1 180); do
  candidates=$(find "${wl_output}" -mindepth 1 -maxdepth 1 -type d -name "*_${latest:0:12}" \
    ! -name "${v1_partial_basename}" -print | LC_ALL=C sort)
  if [[ "$(printf '%s\n' "${candidates}" | sed '/^$/d' | wc -l)" = 1 ]]; then
    new_output=${candidates}
    if [[ -f "${new_output}/matrix.txt" && -f "${new_output}/preflight13.txt" ]]; then
      grep -Fxq 'protocol=wl-snapshot-chain-monitor-v1' "${new_output}/matrix.txt"
      grep -Fxq "control_commit=${control_commit}" "${new_output}/matrix.txt"
      grep -Fxq "scorer_commit=${wl_scorer_commit}" "${new_output}/matrix.txt"
      grep -Fxq "script_sha256=${wl_script_sha}" "${new_output}/matrix.txt"
      grep -Fxq "prior_snapshot=${prior}" "${new_output}/matrix.txt"
      grep -Fxq "current_snapshot=${latest}" "${new_output}/matrix.txt"
      grep -Fxq 'prior_all_runs=494' "${new_output}/matrix.txt"
      grep -Fxq 'current_all_runs=517' "${new_output}/matrix.txt"
      grep -Fxq 'minimum_new_runs=12' "${new_output}/matrix.txt"
      grep -Fxq 'gpu_jobs=0' "${new_output}/matrix.txt"
      grep -Fxq 'api_calls=0' "${new_output}/matrix.txt"
      grep -Fxq 'base_llm_updates=0' "${new_output}/matrix.txt"
      grep -Fxq 'effect_metrics=0' "${new_output}/matrix.txt"
    else
      new_output=''
    fi
  fi
  receipt_segment=$(tail -n "+$((receipt_before + 1))" "${receipt_root}/monitor.log")
  if grep -Fq "monitor_start prior=${prior} stable_polls=3 poll_seconds=300 max_polls=72" <<<"${receipt_segment}"; then
    receipt_started=true
  fi
  if [[ -n "${new_output}" && "${receipt_started}" = true ]]; then break; fi
  kill -0 "${wl_pid}"
  kill -0 "${receipt_pid}"
  sleep 1
done
test -n "${new_output}"
test "${receipt_started}" = true
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
kill -0 "${wl_pid}"
kill -0 "${receipt_pid}"
if lock_is_free "${wl_root}/monitor.lock"; then exit 1; fi
if lock_is_free "${receipt_root}/monitor.lock"; then exit 1; fi
test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
test "$(sha256sum "${transition_root}/monitor.log" | awk '{print $1}')" = "${transition_log_sha}"

cat >"${action_root}/safe_receipt.txt" <<EOF
status=OUTCOME_BLIND_NO_FIT_SUPPORT_RENEWED_V2
renewed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
public_commit=${public_commit}
latest=${latest}
prior=${prior}
eligible_runs=517
eligible_run_delta=23
wl_minimum_new_runs=12
wl_pid=${wl_pid}
receipt_pid=${receipt_pid}
wl_process_group_isolated=true
receipt_process_group_isolated=true
wl_start_receipt=matrix_exact
wl_output_basename=$(basename "${new_output}")
receipt_started_exact=true
v1_partial_output_reused=false
transition_restarted=false
config_v2_sidecar_filename_count=0
prediction_values_read=false
prospective_outcomes_read=false
candidate_identity_or_profile_read=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
test ! -s "${action_root}/wl.stderr"
test ! -s "${action_root}/receipt.stderr"
sha256sum "${action_root}/safe_receipt.txt" >"${action_root}/SHA256SUMS"
chmod 0400 "${action_root}/safe_receipt.txt" "${action_root}/SHA256SUMS"
success=true
printf 'NOFIT_SUPPORT_RENEWAL_V2=PASS\nWL_PID=%s RECEIPT_PID=%s LATEST=%s\n' \
  "${wl_pid}" "${receipt_pid}" "${latest}"
printf 'WL_START_RECEIPT=matrix_exact TRANSITION_RESTARTED=false GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'
printf 'PREDICTION_VALUES_READ=false OUTCOMES_READ=false IDENTITIES_READ=false PROFILE_READ=false\n'
