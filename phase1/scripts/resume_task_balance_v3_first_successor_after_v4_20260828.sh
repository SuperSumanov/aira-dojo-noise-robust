#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

readonly control_commit=${TASK_BALANCE_HANDOFF_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/resume_task_balance_v3_first_successor_after_v4_20260828.sh
readonly previous_public_path=phase1/scripts/resume_task_balance_v3_first_successor_after_887_20260828.sh
readonly protocol_path=phase1/task_balance_forward_v3_future_protocol_v1.json
readonly protocol_sha=6db91cddecc3b1937fd694e2b4903f02f8f81bd4c6a6cdd6b01f46944c552ee1
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly transition_root=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly wl_root=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1
readonly receipt_root=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly transition_state=${transition_root}/state.tsv
readonly wl_state=${wl_root}/state.tsv
readonly receipt_state=${receipt_root}/state.tsv
readonly previous=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v4
readonly failed_attempt=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5
readonly root=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5-r2
readonly failed_attempt_control_commit=69dd6b22acdf767f237571e0a530da3c659a7bad
readonly failed_attempt_source_sha=934078533da2d34aac1325a36c5a25fd527d222651df4c4452fe6fe28d540e7f
readonly failed_attempt_previous_source_sha=8900896df4a13861dd53dd3d9b6de8c20d9b9d499fe1063c07b33ccd9ce814b8
readonly failed_attempt_fileset_sha=d3ee4736512f81ad6f40a6ec7bdeb5547d48b217f9452c72461187dc14e3ba50
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

field() {
  local key=$1 file=$2 value
  value=$(sed -n "s/^${key}=//p" "${file}")
  test -n "${value}"
  test "$(grep -c "^${key}=" "${file}")" = 1
  printf '%s' "${value}"
}

write_candidate() {
  local selected=$1 origin=$2 inherited_receipt_sha=$3
  test "${selected}" != "${baseline}"
  [[ ${selected} =~ ^[0-9a-f]{64}$ ]]
  test -d "${state_root}/snapshots/${selected}"
  test -f "${state_root}/snapshots/${selected}/accumulator/summary.json"
  test -f "${state_root}/snapshots/${selected}/accumulator/provisional_first960_runs.jsonl"
  {
    printf 'status=FIRST_SUCCESSOR_BOUND_ACROSS_SECOND_TIMEOUT_HANDOFF\n'
    printf 'observed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'control_commit=%s\n' "${control_commit}"
    printf 'continuation_script_sha256=%s\n' "${source_script_sha}"
    printf 'protocol_sha256=%s\n' "${protocol_sha}"
    printf 'baseline_snapshot_sha256=%s\n' "${baseline}"
    printf 'candidate_snapshot_sha256=%s\n' "${selected}"
    printf 'summary_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${selected}/accumulator/summary.json" | awk '{print $1}')"
    printf 'ledger_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${selected}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')"
    printf 'candidate_origin=%s\n' "${origin}"
    printf 'inherited_candidate_receipt_sha256=%s\n' "${inherited_receipt_sha}"
    printf 'previous_latch_timeout_continuity=true\n'
    printf 'timeout_handoff_generation=2\n'
    printf 'heartbeat_race_repair=true\n'
    printf 'failed_attempt_fileset_sha256=%s\n' "${failed_attempt_fileset_sha}"
    printf 'manual_snapshot_choice=false\n'
    printf 'earlier_successor_skipped=false\n'
    printf 'balance_values_or_classification_read=false\n'
  } > "${root}/candidate.tsv.tmp"
  mv "${root}/candidate.tsv.tmp" "${root}/candidate.tsv"
}

assert_only_successor_since() {
  local lower_stamp=$1 expected=$2 output=$3 row count
  find "${state_root}/snapshots" -mindepth 1 -maxdepth 1 -type d \
    -newermt "${lower_stamp}" -printf '%f\n' | LC_ALL=C sort -u > "${output}"
  while IFS= read -r row; do
    [[ ${row} =~ ^[0-9a-f]{64}$ ]]
  done < "${output}"
  grep -Fxv "${baseline}" "${output}" > "${output}.nonbaseline" || true
  count=$(wc -l < "${output}.nonbaseline")
  test "${count}" = 1
  test "$(tr -d '\r\n' < "${output}.nonbaseline")" = "${expected}"
}

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'TASK_BALANCE_HANDOFF_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
mkdir -p "${root}"
exec 9>"${root}/monitor.lock"
flock -n 9
printf '%s\n' "$$" > "${root}/monitor.pid"
failure_receipt() {
  rc=$?
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
source_script_sha=$(sha256sum "${root}/source_script.sh" | awk '{print $1}')
git -C "${repo}" show "${control_commit}:${protocol_path}" > "${root}/protocol.json"
test "$(sha256sum "${root}/protocol.json" | awk '{print $1}')" = "${protocol_sha}"

# The first v5 attempt is immutable evidence of an immediate post-timeout
# heartbeat race.  It failed before a candidate, preflight, monitor loop, or
# scientific readout.  Bind that exact failed file set before starting r2.
test -d "${failed_attempt}" && test ! -L "${failed_attempt}"
test -f "${failed_attempt}/FAILED_RC"
test "$(tr -d '\r\n' < "${failed_attempt}/FAILED_RC")" = 1
for forbidden in candidate.tsv READY COMPLETE TIMEOUT_RC INTERRUPTED_RC monitor.log preflight_13.txt handoff_receipt.txt; do
  test ! -e "${failed_attempt}/${forbidden}"
done
for required in \
  FAILED_RC fetch.stderr fetch.stdout handoff_new_snapshot_ids.txt \
  handoff_observed_snapshot_ids.txt monitor.lock monitor.pid \
  previous_source_from_git.sh protocol.json source_script.sh \
  transition_handoff_snapshot_ids.txt; do
  test -f "${failed_attempt}/${required}"
  test ! -L "${failed_attempt}/${required}"
done
test "$(find "${failed_attempt}" -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort | sha256sum | awk '{print $1}')" = \
  "${failed_attempt_fileset_sha}"
test "$(sha256sum "${failed_attempt}/source_script.sh" | awk '{print $1}')" = "${failed_attempt_source_sha}"
test "$(sha256sum "${failed_attempt}/previous_source_from_git.sh" | awk '{print $1}')" = \
  "${failed_attempt_previous_source_sha}"
test "$(sha256sum "${failed_attempt}/protocol.json" | awk '{print $1}')" = "${protocol_sha}"
test ! -s "${failed_attempt}/handoff_new_snapshot_ids.txt"
test ! -s "${failed_attempt}/transition_handoff_snapshot_ids.txt"
test "$(LC_ALL=C sort -u "${failed_attempt}/handoff_observed_snapshot_ids.txt" | tr -d '\r\n')" = "${baseline}"
failed_pid=$(tr -d '\r\n' < "${failed_attempt}/monitor.pid")
[[ ${failed_pid} =~ ^[0-9]+$ ]]
! kill -0 "${failed_pid}" 2>/dev/null
flock -n "${failed_attempt}/monitor.lock" true
git -C "${repo}" cat-file -e "${failed_attempt_control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${failed_attempt_control_commit}" "${control_commit}"
git -C "${repo}" show "${failed_attempt_control_commit}:${public_path}" \
  > "${root}/failed_attempt_source_from_git.sh"
test "$(sha256sum "${root}/failed_attempt_source_from_git.sh" | awk '{print $1}')" = \
  "${failed_attempt_source_sha}"
cmp "${failed_attempt}/source_script.sh" "${root}/failed_attempt_source_from_git.sh"
(
  cd "${failed_attempt}"
  sha256sum \
    FAILED_RC fetch.stderr fetch.stdout handoff_new_snapshot_ids.txt \
    handoff_observed_snapshot_ids.txt monitor.lock monitor.pid \
    previous_source_from_git.sh protocol.json source_script.sh \
    transition_handoff_snapshot_ids.txt
) > "${root}/failed_attempt_sha256.txt"
cat > "${root}/failed_attempt_receipt.txt" <<EOF
status=PRE_CANDIDATE_POST_TIMEOUT_HEARTBEAT_RACE_BOUND
failed_attempt=${failed_attempt}
failed_attempt_control_commit=${failed_attempt_control_commit}
failed_attempt_source_sha256=${failed_attempt_source_sha}
failed_attempt_fileset_sha256=${failed_attempt_fileset_sha}
candidate_present=false
ready_present=false
complete_present=false
monitor_loop_started=false
prospective_values_or_classification_read=false
EOF

test -f "${previous}/TIMEOUT_RC"
test "$(tr -d '\r\n' < "${previous}/TIMEOUT_RC")" = 124
test ! -e "${previous}/FAILED_RC"
test ! -e "${previous}/READY"
test ! -e "${previous}/COMPLETE"
test -f "${previous}/source_script.sh"
test -f "${previous}/protocol.json"
test -f "${previous}/continuity_receipt.txt"
test "$(sha256sum "${previous}/protocol.json" | awk '{print $1}')" = "${protocol_sha}"

previous_control_commit=$(field control_commit "${previous}/continuity_receipt.txt")
previous_script_sha=$(field continuation_script_sha256 "${previous}/continuity_receipt.txt")
[[ ${previous_control_commit} =~ ^[0-9a-f]{40}$ ]]
[[ ${previous_script_sha} =~ ^[0-9a-f]{64}$ ]]
git -C "${repo}" cat-file -e "${previous_control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${previous_control_commit}" "${control_commit}"
git -C "${repo}" show "${previous_control_commit}:${previous_public_path}" \
  > "${root}/previous_source_from_git.sh"
test "$(sha256sum "${root}/previous_source_from_git.sh" | awk '{print $1}')" = "${previous_script_sha}"
cmp "${previous}/source_script.sh" "${root}/previous_source_from_git.sh"
test "$(field status "${previous}/continuity_receipt.txt")" = PREVIOUS_TIMEOUT_CONTIGUOUS_WITH_CURRENT_BASELINE
test "$(field previous_last_observed_snapshot_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field current_latest_snapshot_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field newest_snapshot_directory_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field transition_state_snapshot_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field wl_state_snapshot_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field receipt_state_snapshot_sha256 "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field continuity_monitor_unique_snapshot_ids "${previous}/continuity_receipt.txt")" = "${baseline}"
test "$(field earlier_successor_observed_or_skipped "${previous}/continuity_receipt.txt")" = false
test "$(field balance_values_or_classification_read "${previous}/continuity_receipt.txt")" = false

previous_last_line=$(tail -n 1 "${previous}/monitor.log")
previous_final_stamp=${previous_last_line%% *}
previous_candidate_present=false
candidate=
handoff_mode=
candidate_origin=
inherited_candidate_receipt_sha=NONE

if test -f "${previous}/candidate.tsv"; then
  previous_candidate_present=true
  handoff_mode=CANDIDATE_PRESERVED_FROM_PREVIOUS_TIMEOUT
  candidate_origin=PREVIOUS_AUTHORITATIVE_LATCH
  inherited_candidate_receipt_sha=$(sha256sum "${previous}/candidate.tsv" | awk '{print $1}')
  test "$(field status "${previous}/candidate.tsv")" = FIRST_SUCCESSOR_LATCHED_AFTER_VERIFIED_CONTINUITY
  test "$(field control_commit "${previous}/candidate.tsv")" = "${previous_control_commit}"
  test "$(field continuation_script_sha256 "${previous}/candidate.tsv")" = "${previous_script_sha}"
  test "$(field protocol_sha256 "${previous}/candidate.tsv")" = "${protocol_sha}"
  test "$(field baseline_snapshot_sha256 "${previous}/candidate.tsv")" = "${baseline}"
  test "$(field previous_latch_timeout_continuity "${previous}/candidate.tsv")" = true
  test "$(field manual_snapshot_choice "${previous}/candidate.tsv")" = false
  test "$(field earlier_successor_skipped "${previous}/candidate.tsv")" = false
  test "$(field balance_values_or_classification_read "${previous}/candidate.tsv")" = false
  candidate=$(field candidate_snapshot_sha256 "${previous}/candidate.tsv")
  [[ ${candidate} =~ ^[0-9a-f]{64}$ ]]
  test "${candidate}" != "${baseline}"
  current_latest_after_previous_candidate=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ ${current_latest_after_previous_candidate} =~ ^[0-9a-f]{64}$ ]]
  test "${current_latest_after_previous_candidate}" != "${baseline}"
  test ! -L "${state_root}/snapshots/${candidate}/accumulator/summary.json"
  test ! -L "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl"
  test "$(field summary_sha256 "${previous}/candidate.tsv")" = \
    "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/summary.json" | awk '{print $1}')"
  test "$(field ledger_sha256 "${previous}/candidate.tsv")" = \
    "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')"
  write_candidate "${candidate}" "${candidate_origin}" "${inherited_candidate_receipt_sha}"
  for item in transition wl receipt; do
    if test -f "${previous}/${item}_state.tsv"; then
      test ! -L "${previous}/${item}_state.tsv"
      IFS=$'\t' read -r observed artifact binding extra < "${previous}/${item}_state.tsv"
      test "${observed}" = "${candidate}"
      test -n "${artifact}"
      test -n "${binding}"
      cp "${previous}/${item}_state.tsv" "${root}/${item}_state.tsv"
    fi
  done
else
  handoff_mode=PRE_CANDIDATE_CONTIGUOUS_HANDOFF_AFTER_HEARTBEAT_RACE_REPAIR
  candidate_origin=LATCHED_BY_SECOND_CONTINUATION
  for item in transition wl receipt; do
    test ! -e "${previous}/${item}_state.tsv"
  done
  test "$(printf '%s\n' "${previous_last_line}" | awk '{print $NF}' | cut -d= -f2)" = "${baseline}"
  current_latest=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ ${current_latest} =~ ^[0-9a-f]{64}$ ]]
  newest_snapshot_dir=$(
    find "${state_root}/snapshots" -mindepth 1 -maxdepth 1 -type d -printf '%T@\t%f\n' \
      | LC_ALL=C sort -n | tail -n 1 | cut -f2
  )
  test "${newest_snapshot_dir}" = "${current_latest}"
  printf '%s\n' "${current_latest}" "${newest_snapshot_dir}" > "${root}/handoff_observed_snapshot_ids.txt"
  find "${state_root}/snapshots" -mindepth 1 -maxdepth 1 -type d \
    -newermt "${previous_final_stamp}" -printf '%f\n' \
    | LC_ALL=C sort -u > "${root}/handoff_new_snapshot_ids.txt"
  while IFS= read -r observed; do
    [[ ${observed} =~ ^[0-9a-f]{64}$ ]]
    printf '%s\n' "${observed}" >> "${root}/handoff_observed_snapshot_ids.txt"
  done < "${root}/handoff_new_snapshot_ids.txt"
  for spec in \
    "transition|${transition_root}/monitor.log|${transition_state}" \
    "wl|${wl_root}/monitor.log|${wl_state}" \
    "receipt|${receipt_root}/monitor.log|${receipt_state}"; do
    name=${spec%%|*}
    remainder=${spec#*|}
    log=${remainder%%|*}
    state=${remainder#*|}
    test -f "${log}"
    test -f "${state}"
    IFS=$'\t' read -r observed _ < "${state}"
    [[ ${observed} =~ ^[0-9a-f]{64}$ ]]
    test "${observed}" = "${baseline}" || test "${observed}" = "${current_latest}"
    awk -v lower="${previous_final_stamp}" '$1 >= lower {print}' "${log}" \
      | grep -oE '[0-9a-f]{64}' \
      > "${root}/${name}_handoff_snapshot_ids.unsorted" || true
    LC_ALL=C sort -u "${root}/${name}_handoff_snapshot_ids.unsorted" \
      > "${root}/${name}_handoff_snapshot_ids.txt"
    rm "${root}/${name}_handoff_snapshot_ids.unsorted"
    if test ! -s "${root}/${name}_handoff_snapshot_ids.txt"; then
      printf '%s\n' "${observed}" > "${root}/${name}_handoff_snapshot_ids.txt"
      printf '%s\t%s\n' "${name}" "${observed}" >> "${root}/heartbeat_race_state_fallbacks.tsv"
    fi
    cat "${root}/${name}_handoff_snapshot_ids.txt" >> "${root}/handoff_observed_snapshot_ids.txt"
    printf '%s\n' "${observed}" >> "${root}/handoff_observed_snapshot_ids.txt"
  done
  LC_ALL=C sort -u "${root}/handoff_observed_snapshot_ids.txt" \
    > "${root}/handoff_unique_snapshot_ids.txt"
  test "$(tr -d '\r\n' < "${state_root}/LATEST")" = "${current_latest}"
  grep -Fxv "${baseline}" "${root}/handoff_unique_snapshot_ids.txt" \
    > "${root}/handoff_nonbaseline_snapshot_ids.txt" || true
  nonbaseline_count=$(wc -l < "${root}/handoff_nonbaseline_snapshot_ids.txt")
  test "${nonbaseline_count}" -le 1
  if test "${current_latest}" = "${baseline}"; then
    test "${nonbaseline_count}" = 0
  else
    test "${nonbaseline_count}" = 1
    test "$(tr -d '\r\n' < "${root}/handoff_nonbaseline_snapshot_ids.txt")" = "${current_latest}"
    candidate=${current_latest}
    candidate_origin=RECOVERED_SINGLE_SUCCESSOR_ACROSS_TIMEOUT_GAP
    write_candidate "${candidate}" "${candidate_origin}" NONE
  fi
fi

handoff_checked_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat > "${root}/handoff_receipt.txt" <<EOF
status=SECOND_TIMEOUT_HANDOFF_VERIFIED
checked_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${control_commit}
remote_head_at_check=${remote_head}
continuation_script_sha256=${source_script_sha}
protocol_sha256=${protocol_sha}
previous_root=${previous}
previous_timeout_rc=124
previous_control_commit=${previous_control_commit}
previous_continuation_script_sha256=${previous_script_sha}
previous_monitor_log_sha256=$(sha256sum "${previous}/monitor.log" | awk '{print $1}')
previous_final_observation_utc=${previous_final_stamp}
previous_candidate_present=${previous_candidate_present}
handoff_mode=${handoff_mode}
candidate_origin=${candidate_origin}
inherited_candidate_receipt_sha256=${inherited_candidate_receipt_sha}
heartbeat_race_repair=true
failed_attempt=${failed_attempt}
failed_attempt_control_commit=${failed_attempt_control_commit}
failed_attempt_source_sha256=${failed_attempt_source_sha}
failed_attempt_fileset_sha256=${failed_attempt_fileset_sha}
manual_snapshot_choice=false
earlier_successor_skipped=false
balance_values_or_classification_read=false
EOF

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_goal=preserve the exact first-successor selection across a second bounded timeout; PASS
03_control_commit=${control_commit}; PASS
04_protocol_sha256=${protocol_sha}; PASS
05_previous=exact Git-bound authoritative v4 timeout plus exact pre-candidate v5 heartbeat-race failure; PASS
06_handoff=${handoff_mode},candidate origin ${candidate_origin},race repair true; PASS
07_selection=no caller-supplied snapshot,no manual skip,existing candidate preserved if present; PASS
08_support=transition,WL,and receipt-only common support must each reach the fixed candidate; PASS
09_inputs=LATEST,state TSV,snapshot structural hashes,and safe common-support verification only; PASS
10_forbidden=no label,outcome,prediction value,accuracy,effect,utility,raw archive read; PASS
11_resources=CPU monitor only,GPU/API/model-fit/base-update 0/0/0/0; PASS
12_failure=multiple gap successors,support skip,hash drift,duplicate,credential or monitor failure closes latch; PASS
13_output=handoff,selection,and support receipts only,no balance values or classification; PASS
EOF

for poll in $(seq 0 2160); do
  latest=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ ${latest} =~ ^[0-9a-f]{64}$ ]]
  if test -z "${candidate}" && test "${latest}" != "${baseline}"; then
    candidate=${latest}
    assert_only_successor_since \
      "${handoff_checked_at}" "${candidate}" "${root}/post_handoff_new_snapshot_ids.txt"
    for state in "${transition_state}" "${wl_state}" "${receipt_state}"; do
      IFS=$'\t' read -r observed _ < "${state}"
      test "${observed}" = "${baseline}" || test "${observed}" = "${candidate}"
    done
    write_candidate "${candidate}" "${candidate_origin}" NONE
    printf '%s latched poll=%s snapshot=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${candidate}" >> "${root}/monitor.log"
  fi

  if test -n "${candidate}"; then
    for item in transition wl receipt; do
      case "${item}" in
        transition) state=${transition_state} ;;
        wl) state=${wl_state} ;;
        receipt) state=${receipt_state} ;;
        *) exit 70 ;;
      esac
      if test ! -f "${root}/${item}_state.tsv"; then
        IFS=$'\t' read -r observed artifact binding extra < "${state}"
        if test "${observed}" = "${candidate}"; then
          printf '%s\t%s\t%s\t%s\n' "${observed}" "${artifact}" "${binding}" "${extra:-}" \
            > "${root}/${item}_state.tsv.tmp"
          mv "${root}/${item}_state.tsv.tmp" "${root}/${item}_state.tsv"
        elif test "${observed}" != "${baseline}"; then
          printf '%s support_skipped_candidate item=%s observed=%s candidate=%s\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${item}" "${observed}" "${candidate}" >> "${root}/monitor.log"
          exit 3
        fi
      fi
    done
    if test -f "${root}/transition_state.tsv" \
      && test -f "${root}/wl_state.tsv" \
      && test -f "${root}/receipt_state.tsv"; then
      IFS=$'\t' read -r receipt_snapshot receipt_artifact receipt_binding _ < "${root}/receipt_state.tsv"
      test "${receipt_snapshot}" = "${candidate}"
      test -f "${receipt_artifact}/COMPLETE"
      test ! -e "${receipt_artifact}/FAILED_RC"
      test "$(sha256sum "${receipt_artifact}/receipt_a.json" | awk '{print $1}')" = "${receipt_binding}"
      (cd "${receipt_artifact}" && sha256sum -c SHA256SUMS > "${root}/receipt_manifest_check.txt")
      cmp "${receipt_artifact}/receipt_a.json" "${receipt_artifact}/receipt_b.json"
      cmp "${receipt_artifact}/verification_a.json" "${receipt_artifact}/verification_b.json"
      jq -e --arg snapshot "${candidate}" '
        .protocol == "prediction-receipt-common-support-v1"
        and .status == "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED"
        and .snapshot_sha256 == $snapshot
        and .same_canonical_pair_population_certified == true
        and .candidate_exact == true
        and .prediction_pair_files_opened == false
        and .prediction_values_accessed == false
        and .producer_imported == false
        and .prospective_outcomes_read == false
        and .effect_metrics_computed == []
      ' "${receipt_artifact}/verification_a.json" > /dev/null
      filename_hits=$(find "${root}" -type f -printf '%f\n' \
        | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
      test "${filename_hits}" = 0
      credential_files=$(grep -R -E -i -l "${credential_pattern}" "${root}" \
        --exclude=security_scan_receipt.txt --exclude=SHA256SUMS || true)
      test -z "${credential_files}"
      printf '%s\n' \
        'boundary_aware_credential_file_hits=0' \
        'credential_filename_hits=0' \
        > "${root}/security_scan_receipt.txt"
      cat > "${root}/READY" <<EOF
status=FIRST_SUCCESSOR_AND_SUPPORT_READY_AFTER_SECOND_TIMEOUT_HANDOFF
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${control_commit}
continuation_script_sha256=${source_script_sha}
protocol_sha256=${protocol_sha}
baseline_snapshot_sha256=${baseline}
candidate_snapshot_sha256=${candidate}
common_support_verification_path=${receipt_artifact}/verification_a.json
common_support_verification_sha256=$(sha256sum "${receipt_artifact}/verification_a.json" | awk '{print $1}')
previous_latch_timeout_continuity=true
timeout_handoff_generation=2
heartbeat_race_repair=true
failed_attempt_fileset_sha256=${failed_attempt_fileset_sha}
handoff_mode=${handoff_mode}
candidate_origin=${candidate_origin}
manual_snapshot_choice=false
earlier_successor_skipped=false
balance_values_or_classification_read=false
prospective_outcomes_or_prediction_values_read=false
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
      exit 0
    fi
  fi
  printf '%s waiting poll=%s latest=%s candidate=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${latest}" "${candidate:-none}" >> "${root}/monitor.log"
  sleep 10
done

printf '%s\n' 124 > "${root}/TIMEOUT_RC"
trap - EXIT
exit 0
