#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly mode="${1:-check}"
readonly public_commit="${NOFIT_SUPPORT_RENEWAL_PUBLIC_COMMIT:-}"
readonly public_repo=/research/d7/spc/yzyang4/aira-dojo
readonly public_path=phase1/scripts/renew_outcome_blind_no_fit_support_20260901.sh
readonly protocol_path=phase1/outcome_blind_no_fit_support_renewal_v1.json
readonly action_root=/research/d7/spc/yzyang4/outcome-blind-no-fit-support-renewal-20260901-v1

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
readonly wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly wl_output=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain
readonly wl_state_sha=d6fdf8658e72ff8bb100feb01cfb952c3d510eb8addfb651ff5b80b57c6fd363
readonly wl_log_sha=a75ee5c43c6b8a11d0b92aed321d79e6e7e03d756eb6066c160843136ecafe7e

readonly receipt_control=/research/d7/spc/yzyang4/worktrees/receipt_support_9f2cbe9_nosmudge
readonly receipt_commit=9f2cbe9bff91c2f0ee6f86ff93d9737f9431547f
readonly receipt_script=${receipt_control}/phase1/scripts/monitor_prediction_coverage_snapshot_chain_20260826.sh
readonly receipt_script_sha=458b50a3ac4499abd80c951881f69ab15f82af15a8b2bc51c950cf425d906533
readonly receipt_root=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly receipt_output=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1
readonly receipt_state_sha=6a1ac64a49221f3879a165e608b3cb8298aab221f3ff1bcd20764c1fe47d38bc
readonly receipt_log_sha=6337bb856529f8bcaf59a0d5d8df37630a75b469d771f7e6170b97970e9f5643

readonly transition_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly transition_state_sha=ac66b2deb9054b05e9fab803587d1ee38478f88cbadc86aebfa9f4a9f7ebad4e
readonly transition_log_sha=a23e382f0a8ccb2684dbd29bed68ae0ea1d61c7a6a1727f03195033697f9ec43
readonly intake_pid_file=${state}/continuous_intake_monitor_20260821.pid

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

summary = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
inventory = summary["inventory"]
actual = (
    inventory["all_physical_runs"],
    inventory["eligible_runs"],
    inventory["eligible_endpoints"],
    inventory["eligible_structural_pairs"],
    inventory["eligible_tasks"],
)
expected = tuple(int(value) for value in sys.argv[2:])
assert actual == expected, (actual, expected)
PY
}

verify_public_binding() {
  [[ "${public_commit}" =~ ^[0-9a-f]{40}$ ]]
  local self_sha git_script_sha git_protocol_sha
  self_sha=$(sha256sum "$0" | awk '{print $1}')
  git_script_sha=$(git -C "${public_repo}" show "${public_commit}:${public_path}" | sha256sum | awk '{print $1}')
  git_protocol_sha=$(git -C "${public_repo}" show "${public_commit}:${protocol_path}" | sha256sum | awk '{print $1}')
  test "${self_sha}" = "${git_script_sha}"
  [[ "${git_protocol_sha}" =~ ^[0-9a-f]{64}$ ]]
}

preflight() {
  test "${mode}" = check || test "${mode}" = run
  verify_public_binding
  test "$(git -C "${control}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control}" status --porcelain --untracked-files=all)"
  test "$(git -C "${receipt_control}" rev-parse HEAD)" = "${receipt_commit}"
  test -z "$(git -C "${receipt_control}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${wl_script}" | awk '{print $1}')" = "${wl_script_sha}"
  test "$(sha256sum "${receipt_script}" | awk '{print $1}')" = "${receipt_script_sha}"

  test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
  test -d "${state}/snapshots/${latest}"
  assert_inventory
  test "$(find "${source_root}" -mindepth 2 -maxdepth 2 -type f -name '*.tar.gz' | wc -l)" = "${source_archives}"
  test "$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)" = 0

  test "$(sha256sum "${wl_root}/state.tsv" | awk '{print $1}')" = "${wl_state_sha}"
  test "$(sha256sum "${wl_root}/monitor.log" | awk '{print $1}')" = "${wl_log_sha}"
  test "$(cut -f1 "${wl_root}/state.tsv")" = "${prior}"
  test "$(cut -f4 "${wl_root}/state.tsv")" = 494
  tail -n 1 "${wl_root}/monitor.log" | grep -Fq "monitor_complete prior_snapshot=${prior} prior_all_runs=494"
  all_pid_owners_dead "${wl_root}"
  lock_is_free "${wl_root}/monitor.lock"

  test "$(sha256sum "${receipt_root}/state.tsv" | awk '{print $1}')" = "${receipt_state_sha}"
  test "$(sha256sum "${receipt_root}/monitor.log" | awk '{print $1}')" = "${receipt_log_sha}"
  test "$(cut -f1 "${receipt_root}/state.tsv")" = "${prior}"
  tail -n 1 "${receipt_root}/monitor.log" | grep -Fq "monitor_complete prior=${prior}"
  all_pid_owners_dead "${receipt_root}"
  lock_is_free "${receipt_root}/monitor.lock"

  test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
  test "$(sha256sum "${transition_root}/monitor.log" | awk '{print $1}')" = "${transition_log_sha}"
  test "$(cut -f1 "${transition_root}/state.tsv")" = "${prior}"
  all_pid_owners_dead "${transition_root}"
  lock_is_free "${transition_root}/monitor.lock"

  intake_pid=$(tr -cd '0-9' <"${intake_pid_file}")
  [[ "${intake_pid}" =~ ^[0-9]+$ ]]
  kill -0 "${intake_pid}"
  grep -Fq 'run_prospective_continuous_intake_monitor_20260821.sh --run' \
    < <(tr '\0' ' ' <"/proc/${intake_pid}/cmdline")

  test "$(find "${wl_output}" -mindepth 1 -maxdepth 1 -type d -name "*_${latest:0:12}" -printf '.' | wc -c)" = 0
  test ! -e "${action_root}"
  printf 'NOFIT_SUPPORT_RENEWAL_PREFLIGHT=PASS\n'
  printf 'LATEST=%s PRIOR=%s ELIGIBLE_RUNS=%s DELTA=%s WL_MINIMUM_NEW_RUNS=12\n' \
    "${latest}" "${prior}" "${expected_eligible_runs}" "$((expected_eligible_runs - 494))"
  printf 'TRANSITION_RESTARTED=false GPU_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'
  printf 'PREDICTION_VALUES_READ=false OUTCOMES_READ=false IDENTITIES_READ=false PROFILE_READ=false\n'
}

preflight
if [[ "${mode}" = check ]]; then
  exit 0
fi

mkdir -m 0700 "${action_root}"
wl_pid=''
receipt_pid=''
on_exit() {
  local rc=$?
  if (( rc != 0 )); then
    for pid in "${wl_pid}" "${receipt_pid}"; do
      if [[ "${pid}" =~ ^[0-9]+$ ]] && kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}" 2>/dev/null || true
      fi
    done
    printf '%s\n' "${rc}" >"${action_root}/FAILED_RC"
  fi
}
trap on_exit EXIT

wl_before=$(wc -l <"${wl_root}/monitor.log")
receipt_before=$(wc -l <"${receipt_root}/monitor.log")

nohup env WL_CHAIN_STATE_ROOT="${state}" WL_CHAIN_OUTPUT_ROOT="${wl_output}" \
  WL_CHAIN_MONITOR_ROOT="${wl_root}" WL_CHAIN_POLL_SECONDS=300 WL_CHAIN_MAX_POLLS=72 \
  WL_CHAIN_MINIMUM_NEW_RUNS=12 \
  bash "${wl_script}" "${control}" "${control_commit}" \
  >"${action_root}/wl.stdout" 2>"${action_root}/wl.stderr" </dev/null &
wl_pid=$!
printf '%s\n' "${wl_pid}" >"${wl_root}/renew_20260901_e9_no_fit_v1.pid"

nohup env RECEIPT_SUPPORT_STATE_ROOT="${state}" \
  RECEIPT_SUPPORT_WL_STATE="${wl_root}/state.tsv" \
  RECEIPT_SUPPORT_TRANSITION_STATE="${transition_root}/state.tsv" \
  RECEIPT_SUPPORT_RESULT_ROOT="${receipt_output}" \
  RECEIPT_SUPPORT_MONITOR_ROOT="${receipt_root}" \
  RECEIPT_SUPPORT_POLL_SECONDS=300 RECEIPT_SUPPORT_MAX_POLLS=72 RECEIPT_SUPPORT_STABLE_POLLS=3 \
  bash "${receipt_script}" "${receipt_control}" "${receipt_commit}" \
  >"${action_root}/receipt.stdout" 2>"${action_root}/receipt.stderr" </dev/null &
receipt_pid=$!
printf '%s\n' "${receipt_pid}" >"${receipt_root}/renew_20260901_e9_no_fit_v1.pid"

wl_observed=false
receipt_started=false
for _ in $(seq 1 60); do
  wl_segment=$(tail -n "+$((wl_before + 1))" "${wl_root}/monitor.log")
  receipt_segment=$(tail -n "+$((receipt_before + 1))" "${receipt_root}/monitor.log")
  if grep -Fq "new_snapshot poll=1 old=${prior} new=${latest}" <<<"${wl_segment}"; then
    wl_observed=true
  fi
  if grep -Fq "monitor_start prior=${prior} stable_polls=3 poll_seconds=300 max_polls=72" <<<"${receipt_segment}"; then
    receipt_started=true
  fi
  if [[ "${wl_observed}" = true && "${receipt_started}" = true ]]; then
    break
  fi
  kill -0 "${wl_pid}"
  kill -0 "${receipt_pid}"
  sleep 1
done
test "${wl_observed}" = true
test "${receipt_started}" = true
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${latest}"
kill -0 "${wl_pid}"
kill -0 "${receipt_pid}"
if lock_is_free "${wl_root}/monitor.lock"; then exit 1; fi
if lock_is_free "${receipt_root}/monitor.lock"; then exit 1; fi
test "$(sha256sum "${transition_root}/state.tsv" | awk '{print $1}')" = "${transition_state_sha}"
test "$(sha256sum "${transition_root}/monitor.log" | awk '{print $1}')" = "${transition_log_sha}"

cat >"${action_root}/safe_receipt.txt" <<EOF
status=OUTCOME_BLIND_NO_FIT_SUPPORT_RENEWED
renewed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
public_commit=${public_commit}
latest=${latest}
prior=${prior}
eligible_runs=${expected_eligible_runs}
eligible_run_delta=23
wl_minimum_new_runs=12
wl_pid=${wl_pid}
receipt_pid=${receipt_pid}
wl_first_observation_exact=true
receipt_started_exact=true
transition_restarted=false
transition_state_unchanged=true
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
printf 'NOFIT_SUPPORT_RENEWAL=PASS\nWL_PID=%s RECEIPT_PID=%s LATEST=%s\n' \
  "${wl_pid}" "${receipt_pid}" "${latest}"
printf 'TRANSITION_RESTARTED=false PREDICTION_VALUES_READ=false OUTCOMES_READ=false\n'
