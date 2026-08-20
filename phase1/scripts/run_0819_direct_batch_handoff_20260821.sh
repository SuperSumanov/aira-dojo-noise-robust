#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
BATCH_MANIFEST_REL=phase1/results/prospective_0819_intake_plan_20260821/archive_manifest.json
BATCH_MANIFEST_SHA=d0c0ac148d4277cb11df4a13e5a23f29f57a043772d83423aa606ee1f996f017
OLD_MONITOR_SCRIPT=run_prospective_rejection_monitor_20260819.sh
OLD_MONITOR_COMMIT=2f33982564986d869757283db283c8aaccb147e2
HANDOFF_ROOT=${STATE_ROOT}/diagnostics/direct_0819_batch_handoff_20260821
HANDOFF_LOG=${STATE_ROOT}/logs/direct_0819_batch_handoff_20260821.log
HANDOFF_PID_FILE=${STATE_ROOT}/direct_0819_batch_handoff_20260821.pid
POLL_SECONDS=15
MAX_WAIT_POLLS=481

mode="${1:-}"
old_monitor_pid="${2:-}"
control_repo="${3:-}"
control_commit="${4:-}"
if [[ ! "${old_monitor_pid}" =~ ^[0-9]+$ || -z "${control_repo}" \
  || ! "${control_commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: handoff (--initialize|--run) OLD_MONITOR_PID CONTROL_REPO FULL_CONTROL_COMMIT' >&2
  exit 64
fi

batch_manifest="${control_repo}/${BATCH_MANIFEST_REL}"

verify_fixed_inputs() {
  command -v flock >/dev/null
  test -x "${PYTHON}"
  test -d "${SOURCE_ROOT}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${batch_manifest}" | awk '{print $1}')" = "${BATCH_MANIFEST_SHA}"
  test ! -e "${STATE_ROOT}/BASELINE_INVALID"
}

verify_old_monitor_identity() {
  kill -0 "${old_monitor_pid}" 2>/dev/null || return 1
  old_cmdline="$(tr '\0' ' ' < "/proc/${old_monitor_pid}/cmdline" 2>/dev/null || true)"
  [[ "${old_cmdline}" == *"${OLD_MONITOR_SCRIPT}"* \
    && "${old_cmdline}" == *"${OLD_MONITOR_COMMIT}"* ]]
}

batch_status() {
  (
    cd "${control_repo}"
    "${PYTHON}" -m phase1.verify_prospective_archive_batch \
      --source-root "${SOURCE_ROOT}" \
      --state-root "${STATE_ROOT}" \
      --manifest "${batch_manifest}" \
      --expect-manifest-sha256 "${BATCH_MANIFEST_SHA}" \
      "$@"
  )
}

if [[ "${mode}" == --initialize ]]; then
  verify_fixed_inputs
  if ! verify_old_monitor_identity; then
    echo 'old intake monitor PID identity mismatch at initialization' >&2
    exit 2
  fi
  mkdir -p "${STATE_ROOT}/logs"
  batch_status --hash-source-archives > "${STATE_ROOT}/logs/direct_0819_batch_manifest_smoke_20260821.json"

  echo 'PREFLIGHT_01_DIRECTION=current decision-corpus mainline; exact 0819 batch handoff only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_OLD_MONITOR_COMMIT=${OLD_MONITOR_COMMIT}"
  echo "PREFLIGHT_04_BATCH_MANIFEST_SHA256=${BATCH_MANIFEST_SHA}"
  echo 'PREFLIGHT_05_INPUT=8 exact immutable 0819 archives bound by path size mtime and SHA256'
  echo 'PREFLIGHT_06_TRIGGER=all 8 dispositions resolved by the frozen observer ledger'
  echo 'PREFLIGHT_07_HANDOFF=nonblocking runner lock; reverify exact batch; SIGTERM only the identified sleeping old monitor'
  echo 'PREFLIGHT_08_ESTIMAND=unchanged first-960 structural prefix; no outcomes or effect metrics'
  echo 'PREFLIGHT_09_LEAKAGE=archive payloads labels outcomes scores and predictions remain closed'
  echo 'PREFLIGHT_10_REPRO=clean exact control commit; immutable manifest; gate emitted twice byte-identically'
  echo 'PREFLIGHT_11_GATE=pairs>=1500 runs>=150 tasks>=15 dominant<=0.25 cohort_runs>=960'
  echo 'PREFLIGHT_12_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_13_RUNTIME=poll 15s; expected under 30m; hard wait 2h; no long experiment'
  echo 'PREFLIGHT_14_FAILURE=any PID lock hash ledger LATEST or gate mismatch fails closed'

  if [[ -s "${HANDOFF_PID_FILE}" ]]; then
    prior_handoff_pid="$(cat "${HANDOFF_PID_FILE}")"
    if [[ "${prior_handoff_pid}" =~ ^[0-9]+$ ]] && kill -0 "${prior_handoff_pid}" 2>/dev/null; then
      prior_cmdline="$(tr '\0' ' ' < "/proc/${prior_handoff_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${prior_cmdline}" == *run_0819_direct_batch_handoff_20260821.sh* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${prior_handoff_pid}" "${HANDOFF_LOG}"
        exit 0
      fi
      echo 'handoff PID file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${control_repo}/phase1/scripts/run_0819_direct_batch_handoff_20260821.sh" \
    --run "${old_monitor_pid}" "${control_repo}" "${control_commit}" \
    >> "${HANDOFF_LOG}" 2>&1 </dev/null &
  handoff_pid=$!
  printf '%s\n' "${handoff_pid}" > "${HANDOFF_PID_FILE}"
  printf 'DIRECT_0819_BATCH_HANDOFF_STARTED pid=%s log=%s\n' \
    "${handoff_pid}" "${HANDOFF_LOG}"
  exit 0
fi

if [[ "${mode}" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_fixed_inputs
mkdir -p "${HANDOFF_ROOT}"
printf '%s waiting_for_exact_0819_batch old_monitor_pid=%s outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${old_monitor_pid}"
batch_resolved=false
for ((poll=0; poll<MAX_WAIT_POLLS; poll++)); do
  if ! verify_old_monitor_identity; then
    echo 'old intake monitor exited or changed identity before direct handoff' >&2
    exit 2
  fi
  set +e
  batch_status --require-resolved > "${HANDOFF_ROOT}/batch_wait.tmp"
  batch_rc=$?
  set -e
  if (( batch_rc == 0 )); then
    batch_resolved=true
    break
  fi
  if (( batch_rc != 3 )); then
    echo "batch verification failed while waiting rc=${batch_rc}" >&2
    exit "${batch_rc}"
  fi
  if (( poll % 4 == 0 )); then
    cat "${HANDOFF_ROOT}/batch_wait.tmp"
  fi
  sleep "${POLL_SECONDS}"
done
if [[ "${batch_resolved}" != true ]]; then
  echo 'exact 0819 batch did not resolve within wait window' >&2
  exit 4
fi

exec 9>"${STATE_ROOT}/runner.lock"
lock_acquired=false
for ((lock_poll=0; lock_poll<40; lock_poll++)); do
  if flock -n 9; then
    lock_acquired=true
    break
  fi
  sleep 1
done
if [[ "${lock_acquired}" != true ]]; then
  echo 'could not acquire runner lock for safe handoff' >&2
  exit 4
fi

verify_fixed_inputs
if ! verify_old_monitor_identity; then
  echo 'old intake monitor identity changed before locked handoff' >&2
  exit 2
fi
batch_status --hash-source-archives --require-resolved \
  > "${HANDOFF_ROOT}/batch_resolved_hashcheck.json"
snapshot_sha="$(tr -d '\r\n' < "${STATE_ROOT}/LATEST")"
if [[ ! "${snapshot_sha}" =~ ^[0-9a-f]{64}$ \
  || ! -d "${STATE_ROOT}/snapshots/${snapshot_sha}" ]]; then
  echo 'invalid LATEST snapshot at locked handoff' >&2
  exit 2
fi

kill -TERM "${old_monitor_pid}"
old_exited=false
for ((term_poll=0; term_poll<30; term_poll++)); do
  if ! kill -0 "${old_monitor_pid}" 2>/dev/null; then
    old_exited=true
    break
  fi
  sleep 1
done
if [[ "${old_exited}" != true ]]; then
  echo 'identified old intake monitor did not exit after SIGTERM' >&2
  exit 4
fi
flock -u 9

if [[ "$(tr -d '\r\n' < "${STATE_ROOT}/LATEST")" != "${snapshot_sha}" ]]; then
  echo 'LATEST changed during direct handoff' >&2
  exit 2
fi
snapshot_root="${STATE_ROOT}/snapshots/${snapshot_sha}"
gate_args=(
  --state-root "${STATE_ROOT}"
  --snapshot-root "${snapshot_root}"
  --minimum-pairs 1500
  --minimum-decision-runs 150
  --minimum-tasks 15
  --maximum-dominant-task-share 0.25
  --minimum-cohort-runs 960
  --source-commit "${control_commit}"
)
(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.verify_prospective_structural_gate \
    "${gate_args[@]}" --output "${HANDOFF_ROOT}/structural_gate_a.json" \
    > "${HANDOFF_ROOT}/structural_gate_a.stdout"
  "${PYTHON}" -m phase1.verify_prospective_structural_gate \
    "${gate_args[@]}" --output "${HANDOFF_ROOT}/structural_gate_b.json" \
    > "${HANDOFF_ROOT}/structural_gate_b.stdout"
)
cmp "${HANDOFF_ROOT}/structural_gate_a.json" "${HANDOFF_ROOT}/structural_gate_b.json"
sha256sum "${HANDOFF_ROOT}/batch_resolved_hashcheck.json" \
  "${HANDOFF_ROOT}/structural_gate_a.json" > "${HANDOFF_ROOT}/sha256_manifest.txt"
printf '%s DIRECT_0819_BATCH_HANDOFF_VERIFIED snapshot=%s outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot_sha}"
