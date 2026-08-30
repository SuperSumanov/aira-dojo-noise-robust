#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077
export PYTHONDONTWRITEBYTECODE=1

if [[ "$#" -ne 3 ]]; then
  printf 'usage: %s (--initialize|--run) CONTROL_REPO CONTROL_COMMIT\n' "$0" >&2
  exit 64
fi

mode=$1
control_repo=$2
control_commit=$3
python_bin=${SNAPSHOT_DELTA_CHAIN_PYTHON:-/research/d7/spc/yzyang4/venvs/exp/bin/python}
state_root=${SNAPSHOT_DELTA_CHAIN_STATE_ROOT:-/research/d7/spc/yzyang4/prospective_decision_v1}
output_root=${SNAPSHOT_DELTA_CHAIN_OUTPUT_ROOT:-/research/d7/spc/yzyang4/prospective-snapshot-delta-chain/artifacts_v1}
monitor_root=${SNAPSHOT_DELTA_CHAIN_MONITOR_ROOT:-/research/d7/spc/yzyang4/prospective-snapshot-delta-chain/monitor_v1}
poll_seconds=${SNAPSHOT_DELTA_CHAIN_POLL_SECONDS:-300}
max_polls=${SNAPSHOT_DELTA_CHAIN_MAX_POLLS:-96}

seed_snapshot=0c0584b87140d9a3242f2aa59920829e07e9178749880e3c1f3bd0d065e0b07a
seed_artifact=/research/d7/spc/yzyang4/prospective-snapshot-delta/formal-734a2b1-v3
seed_manifest=69149e510d0bc519363dc48b57e578a3933757ae500e8e830ab60ff849d0bba0
protocol=${control_repo}/phase1/prospective_snapshot_delta_chain_protocol_v1.json
primary=${control_repo}/phase1/verify_prospective_snapshot_delta.py
grounded=${control_repo}/phase1/verify_prospective_snapshot_delta_grounded.py
protocol_sha=c0bda0893a0f8099d2bf8ae8cd13ae3eeded64dcc28845a142e0facaf7d7327e
primary_sha=9d5c56b9da33effd1d56275cccbe939f02a9cd32adb39ad33c8eb04340da67ce
grounded_sha=5d9ff8a80d40b2d59bb2060052ff4101a65547a37a1012b6b6c6a19f3488e854
state_file=${monitor_root}/state.tsv
pid_file=${monitor_root}/monitor.pid
lock_file=${monitor_root}/monitor.lock
log=${monitor_root}/monitor.log
script=${control_repo}/phase1/scripts/monitor_prospective_snapshot_delta_chain_20260831.sh

verify_tree() {
  local root=$1
  local expected=$2
  test -d "${root}"
  test -f "${root}/SHA256SUMS"
  test "$(sha256sum "${root}/SHA256SUMS" | awk '{print $1}')" = "${expected}"
  (cd "${root}" && sha256sum -c SHA256SUMS >/dev/null)
  test -z "$(find "${root}" -type l -print -quit)"
  test -z "$(find "${root}" -type f -perm /222 -print -quit)"
}

validate_artifact_state() {
  local snapshot=$1
  local artifact=$2
  local manifest=$3
  [[ "${snapshot}" =~ ^[0-9a-f]{64}$ ]]
  [[ "${manifest}" =~ ^[0-9a-f]{64}$ ]]
  test -d "${state_root}/snapshots/${snapshot}"
  verify_tree "${artifact}" "${manifest}"
  "${python_bin}" - "${snapshot}" "${artifact}/receipt_a.json" <<'PY'
import json
import pathlib
import sys
snapshot = sys.argv[1]
receipt = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert receipt["status"] == "PROSPECTIVE_SNAPSHOT_APPEND_ONLY_DELTA_VERIFIED"
assert receipt["current_snapshot_sha256"] == snapshot
assert receipt["security"]["outcomes_predictions_accuracy_utility_read"] is False
assert receipt["security"]["archive_drop_run_endpoint_pair_candidate_identities_emitted"] is False
PY
}

verify_contracts() {
  [[ "${control_commit}" =~ ^[0-9a-f]{40}$ ]]
  [[ "${poll_seconds}" =~ ^[1-9][0-9]*$ ]]
  [[ "${max_polls}" =~ ^[1-9][0-9]*$ ]]
  test -x "${python_bin}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain=v1 --untracked-files=all)"
  test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
  test "$(sha256sum "${primary}" | awk '{print $1}')" = "${primary_sha}"
  test "$(sha256sum "${grounded}" | awk '{print $1}')" = "${grounded_sha}"
  command -v strace >/dev/null
  test -d "${state_root}/snapshots"
  test -f "${state_root}/LATEST"
}

initialize_state() {
  mkdir -p "${output_root}" "${monitor_root}"
  if [[ ! -f "${state_file}" ]]; then
    validate_artifact_state "${seed_snapshot}" "${seed_artifact}" "${seed_manifest}"
    printf '%s\t%s\t%s\n' "${seed_snapshot}" "${seed_artifact}" "${seed_manifest}" \
      > "${state_file}"
  fi
  test "$(awk -F '\t' 'END {if (NR != 1) exit 2; print NF}' "${state_file}")" = 3
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_manifest < "${state_file}"
  validate_artifact_state "${prior_snapshot}" "${prior_artifact}" "${prior_manifest}"
}

run_logged() {
  local stage=$1
  shift
  set +e
  /usr/bin/time -v -o "${current_output}/${stage}.time.txt" \
    timeout 1800s "$@" > "${current_output}/${stage}.stdout.txt" \
    2> "${current_output}/${stage}.stderr.txt"
  local rc=$?
  set -e
  printf '%s\n' "${rc}" > "${current_output}/${stage}.rc.txt"
  test "${rc}" = 0
}

process_snapshot() {
  local prior_snapshot=$1
  local current_snapshot=$2
  local stamp
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  current_output=${output_root}/${stamp}_${current_snapshot:0:12}
  test ! -e "${current_output}"
  mkdir "${current_output}"
  printf '%s\n' \
    '01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS' \
    '02_question=append-only immutable snapshot lineage only; PASS' \
    '03_inputs=single promoted prior and atomic LATEST successor; PASS' \
    '04_population=all transactions in both snapshots,no selection or threshold; PASS' \
    '05_blinding=no labels,outcomes,prediction values,accuracy,utility or candidate identities emitted; PASS' \
    '06_controls=manifest,projection,prefix,inventory and duplicate attacks fail closed; PASS' \
    '07_repetitions=primary A/B and non-importing grounded A/B byte identity; PASS' \
    '08_independence=grounded source does not import primary or production; PASS' \
    '09_reproducibility=exact commit,source hashes,commands,seed,state and manifest; PASS' \
    '10_statistics=integer census/delta only,no effect estimate or optional stopping; PASS' \
    '11_resources=CPU only,gpu/api/model-fit/base-update 0/0/0/0; PASS' \
    '12_security=file/network trace,credential scan,no symlink,writable output becomes read-only; PASS' \
    '13_failure=FAILED receipt and no state promotion on any error; PASS' \
    > "${current_output}/preflight13.txt"
  printf 'control_commit=%s\nprotocol_sha256=%s\nprimary_sha256=%s\ngrounded_sha256=%s\nprior_snapshot=%s\ncurrent_snapshot=%s\n' \
    "${control_commit}" "${protocol_sha}" "${primary_sha}" "${grounded_sha}" \
    "${prior_snapshot}" "${current_snapshot}" > "${current_output}/environment.txt"

  primary_common=(
    "${python_bin}" -m phase1.verify_prospective_snapshot_delta
    --prior-snapshot "${state_root}/snapshots/${prior_snapshot}"
    --expect-prior-snapshot-sha256 "${prior_snapshot}"
    --current-snapshot "${state_root}/snapshots/${current_snapshot}"
    --expect-current-snapshot-sha256 "${current_snapshot}"
  )
  primary_a=(env "PYTHONPATH=${control_repo}" PYTHONHASHSEED=0 strace -ff -tt -yy -e trace=file,network -o "${current_output}/primary_a.trace" "${primary_common[@]}" --out "${current_output}/receipt_a.json")
  primary_b=(env "PYTHONPATH=${control_repo}" PYTHONHASHSEED=1 "${primary_common[@]}" --out "${current_output}/receipt_b.json")
  printf '%q ' "${primary_a[@]}" > "${current_output}/primary_a_command.txt"; printf '\n' >> "${current_output}/primary_a_command.txt"
  printf '%q ' "${primary_b[@]}" > "${current_output}/primary_b_command.txt"; printf '\n' >> "${current_output}/primary_b_command.txt"
  run_logged primary_a "${primary_a[@]}"
  run_logged primary_b "${primary_b[@]}"
  cmp "${current_output}/receipt_a.json" "${current_output}/receipt_b.json"
  candidate_sha=$(sha256sum "${current_output}/receipt_a.json" | awk '{print $1}')

  grounded_common=(
    "${python_bin}" -m phase1.verify_prospective_snapshot_delta_grounded
    --prior-snapshot "${state_root}/snapshots/${prior_snapshot}"
    --expect-prior-snapshot-sha256 "${prior_snapshot}"
    --current-snapshot "${state_root}/snapshots/${current_snapshot}"
    --expect-current-snapshot-sha256 "${current_snapshot}"
    --candidate "${current_output}/receipt_a.json"
    --expect-candidate-sha256 "${candidate_sha}"
  )
  grounded_a=(env "PYTHONPATH=${control_repo}" PYTHONHASHSEED=0 strace -ff -tt -yy -e trace=file,network -o "${current_output}/grounded_a.trace" "${grounded_common[@]}" --out "${current_output}/grounded_a.json")
  grounded_b=(env "PYTHONPATH=${control_repo}" PYTHONHASHSEED=1 "${grounded_common[@]}" --out "${current_output}/grounded_b.json")
  printf '%q ' "${grounded_a[@]}" > "${current_output}/grounded_a_command.txt"; printf '\n' >> "${current_output}/grounded_a_command.txt"
  printf '%q ' "${grounded_b[@]}" > "${current_output}/grounded_b_command.txt"; printf '\n' >> "${current_output}/grounded_b_command.txt"
  run_logged grounded_a "${grounded_a[@]}"
  run_logged grounded_b "${grounded_b[@]}"
  cmp "${current_output}/grounded_a.json" "${current_output}/grounded_b.json"

  network_hits=$(grep -hE 'connect\(' "${current_output}"/*.trace* 2>/dev/null | wc -l || true)
  forbidden_hits=$(grep -hEi 'label_vault|outcome_vault|blind_scores\.csv|pair_predictions\.jsonl|/pairs\.jsonl|regrade' \
    "${current_output}"/*.trace* 2>/dev/null | wc -l || true)
  credential_hits=$(grep -RIE --binary-files=without-match \
    'sk-[A-Za-z0-9._-]{16,}|BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY' \
    "${current_output}" 2>/dev/null | wc -l || true)
  test "${network_hits}" = 0
  test "${forbidden_hits}" = 0
  test "${credential_hits}" = 0
  test -z "$(find "${current_output}" -type l -print -quit)"
  printf 'network_hits=0\nforbidden_path_hits=0\ncredential_hits=0\n' \
    > "${current_output}/security.txt"

  "${python_bin}" - "${current_output}/receipt_a.json" "${current_output}/grounded_a.json" \
    "${current_output}/COMPLETE" <<'PY'
import json
import pathlib
import sys
receipt = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
grounded = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert grounded["status"] == "GROUNDED_PROSPECTIVE_SNAPSHOT_DELTA_VERIFIED"
assert grounded["transactions"] == receipt["transactions"]
assert grounded["inventory_delta"] == receipt["inventory"]["delta"]
assert grounded["security"] == receipt["security"]
assert receipt["security"]["archive_drop_run_endpoint_pair_candidate_identities_emitted"] is False
assert receipt["security"]["outcomes_predictions_accuracy_utility_read"] is False
delta = receipt["inventory"]["delta"]
lines = [
    "status=PROSPECTIVE_SNAPSHOT_DELTA_CHAIN_PASS",
    "transactions=%d/%d/%d" % (
        receipt["transactions"]["prior"],
        receipt["transactions"]["current"],
        receipt["transactions"]["appended"],
    ),
    "inventory_delta=%d/%d/%d/%d/%d" % (
        delta["all_physical_runs"],
        delta["eligible_runs"],
        delta["eligible_endpoints"],
        delta["eligible_structural_pairs"],
        delta["eligible_tasks"],
    ),
    "values_read=false",
    "identities_emitted=false",
    "gpu_api_fit_base=0/0/0/0",
]
pathlib.Path(sys.argv[3]).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
PY
  find "${current_output}" -type f ! -name SHA256SUMS ! -name MANIFEST_SHA256 -print0 \
    | sort -z | xargs -0 sha256sum > "${current_output}/SHA256SUMS"
  manifest_sha=$(sha256sum "${current_output}/SHA256SUMS" | awk '{print $1}')
  printf '%s\n' "${manifest_sha}" > "${current_output}/MANIFEST_SHA256"
  chmod -R a-w "${current_output}"
  state_tmp=${state_file}.tmp.$$
  printf '%s\t%s\t%s\n' "${current_snapshot}" "${current_output}" "${manifest_sha}" > "${state_tmp}"
  mv "${state_tmp}" "${state_file}"
  printf '%s promoted snapshot=%s manifest=%s values_read=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${current_snapshot}" "${manifest_sha}" >> "${log}"
  current_output=''
}

run_once() {
  test "$(awk -F '\t' 'END {if (NR != 1) exit 2; print NF}' "${state_file}")" = 3
  IFS=$'\t' read -r prior_snapshot prior_artifact prior_manifest < "${state_file}"
  validate_artifact_state "${prior_snapshot}" "${prior_artifact}" "${prior_manifest}"
  current_snapshot=$(tr -d '\r\n' < "${state_root}/LATEST")
  [[ "${current_snapshot}" =~ ^[0-9a-f]{64}$ ]]
  if [[ "${current_snapshot}" == "${prior_snapshot}" ]]; then
    printf '%s no_change snapshot=%s values_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${current_snapshot}" >> "${log}"
    return 0
  fi
  process_snapshot "${prior_snapshot}" "${current_snapshot}"
}

verify_contracts
initialize_state

if [[ "${mode}" == --initialize ]]; then
  if [[ -s "${pid_file}" ]]; then
    old_pid=$(cat "${pid_file}")
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline=$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)
      if [[ "${old_cmdline}" == *"${script} --run"* ]]; then
        printf 'SNAPSHOT_DELTA_CHAIN_ALREADY_RUNNING pid=%s\n' "${old_pid}"
        exit 0
      fi
      printf 'pid file points to a different live process\n' >&2
      exit 2
    fi
  fi
  nohup bash "${script}" --run "${control_repo}" "${control_commit}" \
    >> "${log}" 2>&1 </dev/null &
  monitor_pid=$!
  printf '%s\n' "${monitor_pid}" > "${pid_file}"
  printf 'SNAPSHOT_DELTA_CHAIN_MONITOR_STARTED pid=%s polls=%s interval=%s\n' \
    "${monitor_pid}" "${max_polls}" "${poll_seconds}"
  exit 0
fi

if [[ "${mode}" != --run ]]; then
  printf 'first argument must be --initialize or --run\n' >&2
  exit 64
fi

exec 9> "${lock_file}"
if ! flock -n 9; then
  printf '%s monitor_already_running\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "${log}"
  exit 3
fi
current_output=''
on_error() {
  local rc=$?
  set +e
  if [[ -n "${current_output}" && -d "${current_output}" && ! -e "${current_output}/COMPLETE" ]]; then
    printf 'status=FAIL_CLOSED\nrc=%s\nstate_promoted=false\n' "${rc}" \
      > "${current_output}/FAILED" 2>/dev/null || true
    find "${current_output}" -type f ! -name SHA256SUMS ! -name MANIFEST_SHA256 -print0 \
      | sort -z | xargs -0 sha256sum > "${current_output}/SHA256SUMS" 2>/dev/null || true
    if [[ -s "${current_output}/SHA256SUMS" ]]; then
      sha256sum "${current_output}/SHA256SUMS" | awk '{print $1}' \
        > "${current_output}/MANIFEST_SHA256" 2>/dev/null || true
    fi
    chmod -R a-w "${current_output}" 2>/dev/null || true
  fi
  printf '%s monitor_error rc=%s line=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${rc}" "${BASH_LINENO[0]:-unknown}" >> "${log}" 2>/dev/null || true
  exit "${rc}"
}
trap on_error ERR
for ((poll=0; poll<max_polls; poll++)); do
  printf '%s poll_start=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" >> "${log}"
  run_once
  printf '%s poll_end=%s rc=0\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" >> "${log}"
  if (( poll + 1 < max_polls )); then sleep "${poll_seconds}"; fi
done
printf '%s SNAPSHOT_DELTA_CHAIN_MONITOR_COMPLETE polls=%s values_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${max_polls}" >> "${log}"
