#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
PRIOR_LOG=${STATE_ROOT}/logs/monitor_rejection_20260819.log
ARCHIVE_REL=0819/multi-modal-gesture-recognition-8seeds.tar.gz
ARCHIVE=${SOURCE_ROOT}/${ARCHIVE_REL}
ARCHIVE_SHA=c0eee1bcae61ca314618802715e88c22e097e07f4f99ccf7ed3ce0c258d05a1d
ARCHIVE_SIZE=86260883
ARCHIVE_MTIME_NS=1787238788000000000
OUT_ROOT=${STATE_ROOT}/diagnostics/multi_modal_0819_task_identity_20260821
SUPERVISOR_LOG=${STATE_ROOT}/logs/structural_recovery_supervisor_20260821.log
SUPERVISOR_PID_FILE=${STATE_ROOT}/structural_recovery_supervisor_20260821.pid
CONTINUATION_PID_FILE=${STATE_ROOT}/rejection_monitor_20260821.pid
CONTINUATION_LOG=${STATE_ROOT}/logs/monitor_rejection_20260821.log
MAX_WAIT_POLLS=361
POLL_SECONDS=60

mode="${1:-}"
prior_pid="${2:-}"
control_repo="${3:-}"
control_commit="${4:-}"
if [[ ! "${prior_pid}" =~ ^[0-9]+$ || -z "${control_repo}" \
  || ! "${control_commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: supervisor (--initialize|--run) PRIOR_PID CONTROL_REPO FULL_CONTROL_COMMIT' >&2
  exit 64
fi

verify_control() {
  test -x "${PYTHON}"
  test -d "${SOURCE_ROOT}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${ARCHIVE}" | awk '{print $1}')" = "${ARCHIVE_SHA}"
  test "$(stat -c '%s' "${ARCHIVE}")" = "${ARCHIVE_SIZE}"
  test ! -e "${STATE_ROOT}/BASELINE_INVALID"
}

if [[ "${mode}" == --initialize ]]; then
  verify_control
  test ! -e "${OUT_ROOT}"
  if ! kill -0 "${prior_pid}" 2>/dev/null; then
    echo 'prior monitor is not live at supervisor initialization' >&2
    exit 2
  fi
  prior_cmdline="$(tr '\0' ' ' < "/proc/${prior_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${prior_cmdline}" != *run_prospective_rejection_monitor_20260819.sh* ]]; then
    echo 'prior PID identity mismatch' >&2
    exit 2
  fi
  mkdir -p "${STATE_ROOT}/logs"

  echo 'PREFLIGHT_01_DIRECTION=first-960 outcome-blind archive recovery only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_PRIOR_MONITOR_PID=${prior_pid}"
  echo "PREFLIGHT_04_ARCHIVE_SHA256=${ARCHIVE_SHA}"
  echo "PREFLIGHT_05_ARCHIVE_SIZE=${ARCHIVE_SIZE}"
  echo "PREFLIGHT_06_ARCHIVE_MTIME_NS=${ARCHIVE_MTIME_NS}"
  echo 'PREFLIGHT_07_TRIGGER=new fail-closed log segment plus exact archive first-ready proof'
  echo 'PREFLIGHT_08_AUDIT=credential-first two byte-identical task-cardinality receipts'
  echo 'PREFLIGHT_09_REJECTION=only if invalid_journals>0 and all security/outcome gates pass'
  echo 'PREFLIGHT_10_LEAKAGE=labels outcomes scores code stdout metric values remain unread/unemitted'
  echo 'PREFLIGHT_11_REPRO=clean exact commit immutable archive manifest receipt and registry SHAs'
  echo 'PREFLIGHT_12_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_13_FAILURE=any mismatch stops; unrelated failures cannot be masked'
  echo "PREFLIGHT_14_RUNTIME=up to ${MAX_WAIT_POLLS}x${POLL_SECONDS}s; downstream batch early-stops"

  if [[ -s "${SUPERVISOR_PID_FILE}" ]]; then
    old_pid="$(cat "${SUPERVISOR_PID_FILE}")"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline="$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${old_cmdline}" == *run_0819_structural_recovery_supervisor_20260821.sh* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${old_pid}" "${SUPERVISOR_LOG}"
        exit 0
      fi
      echo 'supervisor PID file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${control_repo}/phase1/scripts/run_0819_structural_recovery_supervisor_20260821.sh" \
    --run "${prior_pid}" "${control_repo}" "${control_commit}" \
    >> "${SUPERVISOR_LOG}" 2>&1 </dev/null &
  supervisor_pid=$!
  printf '%s\n' "${supervisor_pid}" > "${SUPERVISOR_PID_FILE}"
  printf 'STRUCTURAL_RECOVERY_SUPERVISOR_STARTED pid=%s log=%s\n' \
    "${supervisor_pid}" "${SUPERVISOR_LOG}"
  exit 0
fi

if [[ "${mode}" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_control
prior_start_line="$(wc -l < "${PRIOR_LOG}")"
printf '%s waiting_for_prior_pid=%s start_line=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${prior_pid}" "${prior_start_line}"
prior_exited=false
for ((poll=0; poll<MAX_WAIT_POLLS; poll++)); do
  if ! kill -0 "${prior_pid}" 2>/dev/null; then
    prior_exited=true
    break
  fi
  prior_cmdline="$(tr '\0' ' ' < "/proc/${prior_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${prior_cmdline}" != *run_prospective_rejection_monitor_20260819.sh* ]]; then
    echo 'prior PID identity changed while waiting' >&2
    exit 2
  fi
  sleep "${POLL_SECONDS}"
done
if [[ "${prior_exited}" != true ]]; then
  echo 'prior monitor did not exit within supervisor window' >&2
  exit 4
fi

mkdir -p "${OUT_ROOT}"
tail -n "+$((prior_start_line + 1))" "${PRIOR_LOG}" > "${OUT_ROOT}/prior_monitor_segment.log"
if grep -q 'PROSPECTIVE_REJECTION_MONITOR_COMPLETE' "${OUT_ROOT}/prior_monitor_segment.log" \
  && ! grep -q 'PROSPECTIVE_REJECTION_MONITOR_FAIL_CLOSED' "${OUT_ROOT}/prior_monitor_segment.log"; then
  printf '%s PRIOR_MONITOR_COMPLETED_WITHOUT_RECOVERY outcomes_read=false\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 0
fi
if ! grep -q 'PROSPECTIVE_REJECTION_MONITOR_FAIL_CLOSED' "${OUT_ROOT}/prior_monitor_segment.log"; then
  echo 'prior monitor exited without a fresh recognized terminal marker' >&2
  exit 2
fi

now_epoch="$(date -u +%s)"
precondition_args=(
  --source-root "${SOURCE_ROOT}"
  --state-root "${STATE_ROOT}"
  --archive-relative-path "${ARCHIVE_REL}"
  --expect-archive-sha256 "${ARCHIVE_SHA}"
  --expect-archive-size "${ARCHIVE_SIZE}"
  --expect-archive-mtime-ns "${ARCHIVE_MTIME_NS}"
  --now-epoch "${now_epoch}"
)
(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.verify_structural_recovery_precondition \
    "${precondition_args[@]}" --output "${OUT_ROOT}/precondition_a.json"
  "${PYTHON}" -m phase1.verify_structural_recovery_precondition \
    "${precondition_args[@]}" --output "${OUT_ROOT}/precondition_b.json"
)
cmp "${OUT_ROOT}/precondition_a.json" "${OUT_ROOT}/precondition_b.json"

(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.audit_archive_task_identity \
    --archive "${ARCHIVE}" --expect-archive-sha256 "${ARCHIVE_SHA}" \
    --source-commit "${control_commit}" --output "${OUT_ROOT}/diagnostic_a.json" \
    > "${OUT_ROOT}/audit_a.stdout"
  "${PYTHON}" -m phase1.audit_archive_task_identity \
    --archive "${ARCHIVE}" --expect-archive-sha256 "${ARCHIVE_SHA}" \
    --source-commit "${control_commit}" --output "${OUT_ROOT}/diagnostic_b.json" \
    > "${OUT_ROOT}/audit_b.stdout"
)
cmp "${OUT_ROOT}/diagnostic_a.json" "${OUT_ROOT}/diagnostic_b.json"
install -m 0600 "${OUT_ROOT}/diagnostic_a.json" \
  "${OUT_ROOT}/diagnostic_receipt_multi_modal_0819.json"

builder_args=(
  --archive "${ARCHIVE}"
  --archive-relative-path "${ARCHIVE_REL}"
  --expect-archive-sha256 "${ARCHIVE_SHA}"
  --diagnostic-receipt "${OUT_ROOT}/diagnostic_receipt_multi_modal_0819.json"
  --expect-source-commit "${control_commit}"
)
(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.build_structural_rejection_registry \
    "${builder_args[@]}" --output "${OUT_ROOT}/registry_a.json"
  "${PYTHON}" -m phase1.build_structural_rejection_registry \
    "${builder_args[@]}" --output "${OUT_ROOT}/registry_b.json"
)
cmp "${OUT_ROOT}/registry_a.json" "${OUT_ROOT}/registry_b.json"
install -m 0600 "${OUT_ROOT}/registry_a.json" "${OUT_ROOT}/structural_rejections_0819.json"
registry_sha="$(sha256sum "${OUT_ROOT}/structural_rejections_0819.json" | awk '{print $1}')"

PYTHONPATH="${control_repo}" "${PYTHON}" - "${OUT_ROOT}/structural_rejections_0819.json" \
  "${registry_sha}" <<'PY'
import sys
from pathlib import Path
from phase1.prospective_production_runner import load_structural_rejections

rows, actual = load_structural_rejections(Path(sys.argv[1]), sys.argv[2])
if len(rows) != 1 or actual != sys.argv[2]:
    raise SystemExit("dynamic structural-rejection registry validation failed")
print("DYNAMIC_STRUCTURAL_REJECTION_REGISTRY_VALIDATED", actual)
PY

continuation_start_line=0
if [[ -f "${CONTINUATION_LOG}" ]]; then
  continuation_start_line="$(wc -l < "${CONTINUATION_LOG}")"
fi
bash "${control_repo}/phase1/scripts/run_prospective_rejection_monitor_20260821.sh" \
  --initialize "${control_repo}" "${control_commit}" "${registry_sha}"
continuation_pid="$(cat "${CONTINUATION_PID_FILE}")"
continuation_exited=false
for ((poll=0; poll<MAX_WAIT_POLLS; poll++)); do
  if ! kill -0 "${continuation_pid}" 2>/dev/null; then
    continuation_exited=true
    break
  fi
  continuation_cmdline="$(tr '\0' ' ' < "/proc/${continuation_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${continuation_cmdline}" != *run_prospective_rejection_monitor_20260821.sh* ]]; then
    echo 'continuation PID identity changed while waiting' >&2
    exit 2
  fi
  sleep "${POLL_SECONDS}"
done
if [[ "${continuation_exited}" != true ]]; then
  echo 'continuation monitor did not exit within supervisor window' >&2
  exit 4
fi
tail -n "+$((continuation_start_line + 1))" "${CONTINUATION_LOG}" \
  > "${OUT_ROOT}/continuation_monitor_segment.log"
if ! grep -q 'PROSPECTIVE_0819_BATCH_COMPLETE' "${OUT_ROOT}/continuation_monitor_segment.log"; then
  echo 'continuation monitor did not complete the fixed 0819 batch' >&2
  exit 2
fi

snapshot_sha="$(tr -d '\r\n' < "${STATE_ROOT}/LATEST")"
if [[ ! "${snapshot_sha}" =~ ^[0-9a-f]{64}$ ]]; then
  echo 'invalid latest snapshot SHA' >&2
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
    "${gate_args[@]}" --output "${OUT_ROOT}/structural_gate_a.json" \
    > "${OUT_ROOT}/structural_gate_a.stdout"
  "${PYTHON}" -m phase1.verify_prospective_structural_gate \
    "${gate_args[@]}" --output "${OUT_ROOT}/structural_gate_b.json" \
    > "${OUT_ROOT}/structural_gate_b.stdout"
)
cmp "${OUT_ROOT}/structural_gate_a.json" "${OUT_ROOT}/structural_gate_b.json"
sha256sum "${OUT_ROOT}/precondition_a.json" "${OUT_ROOT}/diagnostic_a.json" \
  "${OUT_ROOT}/structural_rejections_0819.json" "${OUT_ROOT}/structural_gate_a.json" \
  > "${OUT_ROOT}/sha256_manifest.txt"
printf '%s STRUCTURAL_RECOVERY_AND_0819_BATCH_VERIFIED snapshot=%s outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot_sha}"
