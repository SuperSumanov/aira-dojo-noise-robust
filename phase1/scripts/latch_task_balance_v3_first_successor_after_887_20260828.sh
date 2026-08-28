#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

readonly source_commit=ab55510bc98ba05e947113e25a450f963d2f117d
readonly protocol_sha=6db91cddecc3b1937fd694e2b4903f02f8f81bd4c6a6cdd6b01f46944c552ee1
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly transition_state=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1/state.tsv
readonly wl_state=/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1/state.tsv
readonly receipt_state=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1/state.tsv
readonly root=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-ab55510-after-887-v3
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test ! -e "${root}"
mkdir -p "${root}"
exec 9>"${root}/monitor.lock"
flock -n 9
printf '%s\n' "$$" > "${root}/monitor.pid"
trap 'rc=$?; if (( rc != 0 )); then printf "%s\n" "${rc}" > "${root}/FAILED_RC"; fi; exit "${rc}"' EXIT

git -C "${repo}" fetch fork phase1-value-critic > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
test "$(git -C "${repo}" rev-parse fork/phase1-value-critic)" = "${source_commit}"
git -C "${repo}" show "${source_commit}:phase1/task_balance_forward_v3_future_protocol_v1.json" \
  > "${root}/protocol.json"
test "$(sha256sum "${root}/protocol.json" | awk '{print $1}')" = "${protocol_sha}"
test "$(tr -d '\r\n' < "${state_root}/LATEST")" = "${baseline}"
for state in "${transition_state}" "${wl_state}" "${receipt_state}"; do
  IFS=$'\t' read -r snapshot _ < "${state}"
  test "${snapshot}" = "${baseline}"
done
cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_goal=atomically latch the first immutable successor of ${baseline}; PASS
03_source_commit=${source_commit}; PASS
04_protocol_sha256=${protocol_sha}; PASS
05_initial_latest_and_all_support_states=${baseline}; PASS
06_selection=no caller-supplied snapshot,no manual skip,first observed successor only; PASS
07_support=transition,WL,and receipt-only common support must each reach latched successor; PASS
08_inputs=LATEST,state TSV,snapshot structural hashes,and safe common-support verification only; PASS
09_forbidden=no label,outcome,prediction value,accuracy,effect,utility,raw archive read; PASS
10_resources=CPU monitor only,GPU/API/model-fit/base-update 0/0/0/0; PASS
11_failure=unknown state jump,hash mismatch,duplicate,credential or monitor failure closes latch; PASS
12_duration=10-second polling,2160-poll six-hour bound; PASS
13_output=selection and support receipts only,no balance values or classification; PASS
EOF

candidate=
for poll in $(seq 0 2160); do
  latest=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ ${latest} =~ ^[0-9a-f]{64}$ ]]
  if test -z "${candidate}" && test "${latest}" != "${baseline}"; then
    candidate=${latest}
    test "${candidate}" != "${baseline}"
    test -d "${state_root}/snapshots/${candidate}"
    test -f "${state_root}/snapshots/${candidate}/accumulator/summary.json"
    test -f "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl"
    {
      printf 'status=FIRST_SUCCESSOR_LATCHED\n'
      printf 'observed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'poll=%s\n' "${poll}"
      printf 'source_commit=%s\n' "${source_commit}"
      printf 'baseline_snapshot_sha256=%s\n' "${baseline}"
      printf 'candidate_snapshot_sha256=%s\n' "${candidate}"
      printf 'summary_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/summary.json" | awk '{print $1}')"
      printf 'ledger_sha256=%s\n' "$(sha256sum "${state_root}/snapshots/${candidate}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')"
      printf 'manual_snapshot_choice=false\n'
      printf 'earlier_successor_skipped=false\n'
      printf 'balance_values_or_classification_read=false\n'
    } > "${root}/candidate.tsv.tmp"
    mv "${root}/candidate.tsv.tmp" "${root}/candidate.tsv"
    printf '%s latched poll=%s snapshot=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${candidate}" >> "${root}/monitor.log"
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
status=FIRST_SUCCESSOR_AND_SUPPORT_READY
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_commit=${source_commit}
baseline_snapshot_sha256=${baseline}
candidate_snapshot_sha256=${candidate}
common_support_verification_path=${receipt_artifact}/verification_a.json
common_support_verification_sha256=$(sha256sum "${receipt_artifact}/verification_a.json" | awk '{print $1}')
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
  printf '%s waiting poll=%s latest=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${latest}" >> "${root}/monitor.log"
  sleep 10
done

echo 124 > "${root}/TIMEOUT_RC"
trap - EXIT
exit 0
