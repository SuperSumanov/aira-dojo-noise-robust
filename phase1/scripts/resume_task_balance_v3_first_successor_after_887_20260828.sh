#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

readonly control_commit=${TASK_BALANCE_CONTINUATION_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/resume_task_balance_v3_first_successor_after_887_20260828.sh
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
readonly previous=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-ab55510-after-887-v3
readonly root=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v4
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'TASK_BALANCE_CONTINUATION_CONTROL_COMMIT must be a 40-hex public commit' >&2
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

test -f "${previous}/TIMEOUT_RC"
test "$(tr -d '\r\n' < "${previous}/TIMEOUT_RC")" = 124
test ! -e "${previous}/FAILED_RC"
test ! -e "${previous}/candidate.tsv"
test ! -e "${previous}/READY"
test ! -e "${previous}/COMPLETE"
previous_last_line=$(tail -n 1 "${previous}/monitor.log")
previous_final_stamp=${previous_last_line%% *}
test "$(printf '%s\n' "${previous_last_line}" | awk '{print $NF}' | cut -d= -f2)" = "${baseline}"
test "$(tr -d '\r\n' < "${state_root}/LATEST")" = "${baseline}"
newest_snapshot_dir=$(
  find "${state_root}/snapshots" -mindepth 1 -maxdepth 1 -type d -printf '%T@\t%f\n' \
    | LC_ALL=C sort -n | tail -n 1 | cut -f2
)
test "${newest_snapshot_dir}" = "${baseline}"
for state in "${transition_state}" "${wl_state}" "${receipt_state}"; do
  IFS=$'\t' read -r snapshot _ < "${state}"
  test "${snapshot}" = "${baseline}"
done

for spec in \
  "transition|${transition_root}/monitor.log" \
  "wl|${wl_root}/monitor.log" \
  "receipt|${receipt_root}/monitor.log"; do
  name=${spec%%|*}
  log=${spec#*|}
  test -f "${log}"
  awk -v lower="${previous_final_stamp}" '$1 >= lower {print}' "${log}" \
    | grep -oE '[0-9a-f]{64}' \
    | LC_ALL=C sort -u > "${root}/${name}_continuity_snapshot_ids.txt"
  test "$(wc -l < "${root}/${name}_continuity_snapshot_ids.txt")" = 1
  test "$(tr -d '\r\n' < "${root}/${name}_continuity_snapshot_ids.txt")" = "${baseline}"
done

cat > "${root}/continuity_receipt.txt" <<EOF
status=PREVIOUS_TIMEOUT_CONTIGUOUS_WITH_CURRENT_BASELINE
checked_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${control_commit}
remote_head_at_check=${remote_head}
continuation_script_sha256=${source_script_sha}
protocol_sha256=${protocol_sha}
previous_root=${previous}
previous_timeout_rc=124
previous_monitor_log_sha256=$(sha256sum "${previous}/monitor.log" | awk '{print $1}')
previous_final_observation_utc=${previous_final_stamp}
previous_last_observed_snapshot_sha256=${baseline}
current_latest_snapshot_sha256=${baseline}
newest_snapshot_directory_sha256=${newest_snapshot_dir}
transition_state_snapshot_sha256=${baseline}
wl_state_snapshot_sha256=${baseline}
receipt_state_snapshot_sha256=${baseline}
continuity_monitor_unique_snapshot_ids=${baseline}
earlier_successor_observed_or_skipped=false
balance_values_or_classification_read=false
EOF

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_goal=continue the exact first-successor latch after a clean six-hour timeout; PASS
03_control_commit=${control_commit}; PASS
04_protocol_sha256=${protocol_sha}; PASS
05_continuity=previous final observation,current LATEST,newest snapshot directory,and three support logs/states all equal ${baseline}; PASS
06_selection=no caller-supplied snapshot,no manual skip,first observed successor only; PASS
07_support=transition,WL,and receipt-only common support must each reach latched successor; PASS
08_inputs=LATEST,state TSV,snapshot structural hashes,and safe common-support verification only; PASS
09_forbidden=no label,outcome,prediction value,accuracy,effect,utility,raw archive read; PASS
10_resources=CPU monitor only,GPU/API/model-fit/base-update 0/0/0/0; PASS
11_failure=unknown state jump,hash mismatch,duplicate,credential or monitor failure closes latch; PASS
12_duration=10-second polling,2160-poll six-hour bound; PASS
13_output=continuity,selection,and support receipts only,no balance values or classification; PASS
EOF

candidate=
for poll in $(seq 0 2160); do
  latest=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ ${latest} =~ ^[0-9a-f]{64}$ ]]
  if test -z "${candidate}" && test "${latest}" != "${baseline}"; then
    candidate=${latest}
    test -d "${state_root}/snapshots/${candidate}"
    test -f "${state_root}/snapshots/${candidate}/accumulator/summary.json"
    test -f "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl"
    {
      printf 'status=FIRST_SUCCESSOR_LATCHED_AFTER_VERIFIED_CONTINUITY\n'
      printf 'observed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'poll=%s\n' "${poll}"
      printf 'control_commit=%s\n' "${control_commit}"
      printf 'continuation_script_sha256=%s\n' "${source_script_sha}"
      printf 'protocol_sha256=%s\n' "${protocol_sha}"
      printf 'baseline_snapshot_sha256=%s\n' "${baseline}"
      printf 'candidate_snapshot_sha256=%s\n' "${candidate}"
      printf 'summary_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/summary.json" | awk '{print $1}')"
      printf 'ledger_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')"
      printf 'previous_latch_timeout_continuity=true\n'
      printf 'manual_snapshot_choice=false\n'
      printf 'earlier_successor_skipped=false\n'
      printf 'balance_values_or_classification_read=false\n'
    } > "${root}/candidate.tsv.tmp"
    mv "${root}/candidate.tsv.tmp" "${root}/candidate.tsv"
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
status=FIRST_SUCCESSOR_AND_SUPPORT_READY_AFTER_VERIFIED_CONTINUITY
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${control_commit}
continuation_script_sha256=${source_script_sha}
protocol_sha256=${protocol_sha}
baseline_snapshot_sha256=${baseline}
candidate_snapshot_sha256=${candidate}
common_support_verification_path=${receipt_artifact}/verification_a.json
common_support_verification_sha256=$(sha256sum "${receipt_artifact}/verification_a.json" | awk '{print $1}')
previous_latch_timeout_continuity=true
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
  printf '%s waiting poll=%s latest=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${latest}" >> "${root}/monitor.log"
  sleep 10
done

printf '%s\n' 124 > "${root}/TIMEOUT_RC"
trap - EXIT
exit 0
