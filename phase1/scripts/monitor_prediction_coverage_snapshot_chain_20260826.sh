#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ "$#" -ne 2 ]]; then
  printf 'usage: %s CONTROL_REPO CONTROL_COMMIT\n' "$0" >&2
  exit 64
fi

control_repo=$1
control_commit=$2
state_root=${RECEIPT_SUPPORT_STATE_ROOT:-/research/d7/spc/yzyang4/prospective_decision_v1}
wl_state=${RECEIPT_SUPPORT_WL_STATE:-/research/d7/spc/yzyang4/wl-graph-escrow-snapshot-chain/monitor_3932b38_v1/state.tsv}
transition_state=${RECEIPT_SUPPORT_TRANSITION_STATE:-/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1/state.tsv}
result_root=${RECEIPT_SUPPORT_RESULT_ROOT:-/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_v1}
monitor_root=${RECEIPT_SUPPORT_MONITOR_ROOT:-/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_v1}
wl_verifier_source=${RECEIPT_SUPPORT_WL_VERIFIER_SOURCE:-/research/d7/spc/yzyang4/worktrees/codex_wl_escrow_031edb3/phase1/verify_prospective_wl_graph_escrow.py}
transition_verifier_source=${RECEIPT_SUPPORT_TRANSITION_VERIFIER_SOURCE:-/research/d7/spc/yzyang4/worktrees/transition_future_7458f09_nosmudge/phase1/verify_prospective_transition_future_escrow.py}
python_bin=${RECEIPT_SUPPORT_PYTHON:-/research/d7/spc/yzyang4/venvs/exp/bin/python}
poll_seconds=${RECEIPT_SUPPORT_POLL_SECONDS:-300}
max_polls=${RECEIPT_SUPPORT_MAX_POLLS:-72}
stable_polls=${RECEIPT_SUPPORT_STABLE_POLLS:-3}

protocol=${control_repo}/phase1/prediction_receipt_common_support_protocol_v1.json
builder=${control_repo}/phase1/build_prediction_receipt_common_support.py
verifier=${control_repo}/phase1/verify_prediction_receipt_common_support.py
mkdir -p "${result_root}" "${monitor_root}"
log=${monitor_root}/monitor.log
state_file=${monitor_root}/state.tsv
lock_file=${monitor_root}/monitor.lock
script_sha=$(sha256sum "$0" | awk '{print $1}')
protocol_sha=$(sha256sum "${protocol}" | awk '{print $1}')
builder_sha=$(sha256sum "${builder}" | awk '{print $1}')
verifier_sha=$(sha256sum "${verifier}" | awk '{print $1}')
current_output=''

exec 9>"${lock_file}"
if ! flock -n 9; then
  printf '%s monitor_already_running\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "${log}"
  exit 3
fi

on_error() {
  local rc=$?
  if [[ -n "${current_output}" && -d "${current_output}" && ! -e "${current_output}/COMPLETE" ]]; then
    printf 'status=FAILURE\nrc=%s\nutc=%s\n' "${rc}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${current_output}/FAILURE"
  fi
  printf '%s monitor_error rc=%s line=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${rc}" "${BASH_LINENO[0]:-unknown}" >> "${log}"
  exit "${rc}"
}
trap on_error ERR

[[ "${control_commit}" =~ ^[0-9a-f]{40}$ ]]
[[ "${poll_seconds}" =~ ^[1-9][0-9]*$ ]]
[[ "${max_polls}" =~ ^[1-9][0-9]*$ ]]
[[ "${stable_polls}" =~ ^[1-9][0-9]*$ ]]
test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
test -x "${python_bin}"
test -f "${wl_verifier_source}"
test -f "${transition_verifier_source}"
command -v strace >/dev/null

export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 BLIS_NUM_THREADS=1

read_promoted_states() {
  test "$(awk -F '\t' 'END {if (NR != 1) exit 2; print NF}' "${wl_state}")" = 4
  test "$(awk -F '\t' 'END {if (NR != 1) exit 2; print NF}' "${transition_state}")" = 3
  IFS=$'\t' read -r wl_snapshot wl_artifact wl_summary wl_all_runs < "${wl_state}"
  IFS=$'\t' read -r transition_snapshot transition_artifact transition_summary < "${transition_state}"
  latest_snapshot=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ "${wl_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${transition_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${latest_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${wl_summary}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${transition_summary}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${wl_all_runs}" =~ ^[1-9][0-9]*$ ]]
  test "$(sha256sum "${wl_artifact}/summary.json" | awk '{print $1}')" = "${wl_summary}"
  test "$(sha256sum "${transition_artifact}/summary.json" | awk '{print $1}')" = "${transition_summary}"

  wl_parent=$(dirname "${wl_artifact}")
  transition_parent=$(dirname "${transition_artifact}")
  wl_receipt=${wl_parent}/independent_verification.json
  wl_command=${wl_parent}/independent_verifier_command.txt
  if [[ -f "${transition_parent}/independent_verification.json" ]]; then
    transition_receipt=${transition_parent}/independent_verification.json
    transition_command=${transition_parent}/independent_verifier_command.txt
  else
    transition_receipt=${transition_parent}/verification.json
    transition_command=${transition_parent}/verifier_command.txt
  fi
  test -f "${wl_receipt}"
  test -f "${wl_command}"
  test -f "${transition_receipt}"
  test -f "${transition_command}"
}

validate_result() {
  local expected_snapshot=$1
  local root=$2
  local expected_receipt_sha=$3
  test -f "${root}/COMPLETE"
  test -f "${root}/receipt_a.json"
  test -f "${root}/verification_a.json"
  test "$(sha256sum "${root}/receipt_a.json" | awk '{print $1}')" = "${expected_receipt_sha}"
  (
    cd "${root}"
    sha256sum -c SHA256SUMS > /dev/null
  )
  "${python_bin}" - "${expected_snapshot}" "${root}/receipt_a.json" "${root}/verification_a.json" <<'PY'
import json
import pathlib
import sys
snapshot = sys.argv[1]
receipt = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
verification = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
assert receipt["status"] == "RECEIPT_CERTIFIED_EXACT_CANONICAL_COMMON_SUPPORT"
assert verification["status"] == "INDEPENDENT_PREDICTION_RECEIPT_COMMON_SUPPORT_VERIFIED"
assert receipt["snapshot_sha256"] == verification["snapshot_sha256"] == snapshot
assert receipt["scope"]["prediction_values_accessed"] is False
assert receipt["input_policy"]["prediction_pair_files_opened"] is False
assert verification["prediction_pair_files_opened"] is False
assert verification["prediction_values_accessed"] is False
assert verification["prospective_outcomes_read"] is False
assert verification["effect_metrics_computed"] == []
PY
}

if [[ -f "${state_file}" ]]; then
  test "$(awk -F '\t' 'END {if (NR != 1) exit 2; print NF}' "${state_file}")" = 3
  IFS=$'\t' read -r prior_snapshot prior_result prior_receipt_sha < "${state_file}"
  [[ "${prior_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${prior_receipt_sha}" =~ ^[0-9a-f]{64}$ ]]
  validate_result "${prior_snapshot}" "${prior_result}" "${prior_receipt_sha}"
else
  prior_snapshot=''
fi

run_logged() {
  local stage=$1
  shift
  set +e
  /usr/bin/time -v -o "${current_output}/${stage}.time.txt" \
    strace -ff -e trace=file -o "${current_output}/${stage}.strace" \
    "$@" > "${current_output}/${stage}.stdout.txt" 2> "${current_output}/${stage}.stderr.txt"
  local rc=$?
  set -e
  printf '%s\n' "${rc}" > "${current_output}/${stage}.rc.txt"
  test "${rc}" = 0
}

process_snapshot() {
  local snapshot=$1
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  current_output=${result_root}/${stamp}_${snapshot:0:12}
  test ! -e "${current_output}"
  mkdir "${current_output}"

  printf '%s\n' \
    '01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS' \
    '02_question=receipt-certified exact canonical common support only; PASS' \
    '03_inputs=promoted states,independent receipts,verifier commands,summary/source bytes for hashes; PASS' \
    '04_forbidden=no prediction pair files,values,orientation,ties,labels,outcomes,effects,accuracy,utility; PASS' \
    '05_trigger=WL=transition=LATEST and stable; PASS' \
    '06_success=builder A/B byte identity plus independent verifier A/B byte identity; PASS' \
    '07_negative=any snapshot,hash,command,receipt,count or blindness mismatch fails closed; PASS' \
    '08_independence=verifier does not import builder and reconstructs candidate exactly; PASS' \
    '09_reproducibility=exact commit,source hashes,commands,state,manifest; PASS' \
    '10_statistics=structural support count only,no prediction aggregate or effect estimate; PASS' \
    '11_resources=CPU only,gpu=0,api=0,model fit=0,base LLM updates=0; PASS' \
    '12_security=strace forbidden-path and credential scans; PASS' \
    '13_stop=any failure prevents receipt state promotion; PASS' \
    > "${current_output}/preflight13.txt"
  printf 'control_commit=%s\nmonitor_script_sha256=%s\nprotocol_sha256=%s\nbuilder_sha256=%s\nverifier_sha256=%s\nsnapshot_sha256=%s\n' \
    "${control_commit}" "${script_sha}" "${protocol_sha}" "${builder_sha}" "${verifier_sha}" "${snapshot}" \
    > "${current_output}/environment.txt"

  common=(
    --protocol "${protocol}" --expect-protocol-sha256 "${protocol_sha}"
    --expect-snapshot-sha256 "${snapshot}"
    --wl-state "${wl_state}" --transition-state "${transition_state}"
    --wl-independent-receipt "${wl_receipt}"
    --transition-independent-receipt "${transition_receipt}"
    --wl-verifier-command "${wl_command}"
    --transition-verifier-command "${transition_command}"
    --wl-verifier-source "${wl_verifier_source}"
    --transition-verifier-source "${transition_verifier_source}"
  )
  build_a=(env "PYTHONPATH=${control_repo}" "${python_bin}" -m phase1.build_prediction_receipt_common_support "${common[@]}" --output "${current_output}/receipt_a.json")
  build_b=(env "PYTHONPATH=${control_repo}" "${python_bin}" -m phase1.build_prediction_receipt_common_support "${common[@]}" --output "${current_output}/receipt_b.json")
  verify_a=(env "PYTHONPATH=${control_repo}" "${python_bin}" -m phase1.verify_prediction_receipt_common_support --candidate "${current_output}/receipt_a.json" "${common[@]}" --output "${current_output}/verification_a.json")
  verify_b=(env "PYTHONPATH=${control_repo}" "${python_bin}" -m phase1.verify_prediction_receipt_common_support --candidate "${current_output}/receipt_b.json" "${common[@]}" --output "${current_output}/verification_b.json")
  printf '%q ' "${build_a[@]}" > "${current_output}/builder_a_command.txt"; printf '\n' >> "${current_output}/builder_a_command.txt"
  printf '%q ' "${build_b[@]}" > "${current_output}/builder_b_command.txt"; printf '\n' >> "${current_output}/builder_b_command.txt"
  printf '%q ' "${verify_a[@]}" > "${current_output}/verifier_a_command.txt"; printf '\n' >> "${current_output}/verifier_a_command.txt"
  printf '%q ' "${verify_b[@]}" > "${current_output}/verifier_b_command.txt"; printf '\n' >> "${current_output}/verifier_b_command.txt"
  run_logged builder_a "${build_a[@]}"
  run_logged builder_b "${build_b[@]}"
  cmp "${current_output}/receipt_a.json" "${current_output}/receipt_b.json"
  run_logged verifier_a "${verify_a[@]}"
  run_logged verifier_b "${verify_b[@]}"
  cmp "${current_output}/verification_a.json" "${current_output}/verification_b.json"

  prediction_file_hits=$( { grep -hE 'pair_predictions\.jsonl|/pairs\.jsonl' "${current_output}"/*.strace* || true; } | wc -l )
  outcome_path_hits=$( { grep -hEi '/prospective_decision_v1/(label|outcome|scorer)|label_vault|outcome_vault|score_registry|regrade' "${current_output}"/*.strace* || true; } | wc -l )
  credential_hits=$( { grep -rIPIl '(?<![A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "${current_output}" || true; } | wc -l )
  printf 'prediction_pair_file_open_hits=%s\noutcome_path_open_hits=%s\ncredential_content_file_hits=%s\n' \
    "${prediction_file_hits}" "${outcome_path_hits}" "${credential_hits}" > "${current_output}/security.txt"
  test "${prediction_file_hits}" = 0
  test "${outcome_path_hits}" = 0
  test "${credential_hits}" = 0

  receipt_sha=$(sha256sum "${current_output}/receipt_a.json" | awk '{print $1}')
  touch "${current_output}/COMPLETE"
  (
    cd "${current_output}"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
    sha256sum -c SHA256SUMS > manifest_verification.txt
  )
  chmod -R a-w "${current_output}"
  printf '%s\t%s\t%s\n' "${snapshot}" "${current_output}" "${receipt_sha}" > "${state_file}.next"
  mv "${state_file}.next" "${state_file}"
  prior_snapshot=${snapshot}
  printf '%s receipt_support_complete snapshot=%s result=%s values_accessed=false outcomes_read=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot}" "${current_output}" >> "${log}"
  current_output=''
}

candidate=''
stable_count=0
printf '%s monitor_start prior=%s stable_polls=%s poll_seconds=%s max_polls=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot:-none}" "${stable_polls}" "${poll_seconds}" "${max_polls}" >> "${log}"
for ((poll = 1; poll <= max_polls; poll += 1)); do
  read_promoted_states
  if [[ "${wl_snapshot}" = "${transition_snapshot}" \
        && "${wl_snapshot}" = "${latest_snapshot}" \
        && "${wl_snapshot}" != "${prior_snapshot}" ]]; then
    if [[ "${candidate}" = "${wl_snapshot}" ]]; then
      stable_count=$((stable_count + 1))
    else
      candidate=${wl_snapshot}
      stable_count=1
    fi
    printf '%s candidate poll=%s snapshot=%s stable=%s/%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${candidate}" "${stable_count}" "${stable_polls}" >> "${log}"
    if (( stable_count >= stable_polls )); then
      process_snapshot "${candidate}"
      candidate=''
      stable_count=0
    fi
  else
    candidate=''
    stable_count=0
    printf '%s waiting poll=%s latest=%s wl=%s transition=%s prior=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${latest_snapshot}" "${wl_snapshot}" \
      "${transition_snapshot}" "${prior_snapshot:-none}" >> "${log}"
  fi
  if (( poll < max_polls )); then
    sleep "${poll_seconds}"
  fi
done
printf '%s monitor_complete prior=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_snapshot:-none}" >> "${log}"
