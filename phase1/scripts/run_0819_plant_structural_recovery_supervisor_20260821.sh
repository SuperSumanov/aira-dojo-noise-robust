#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
ARCHIVE_REL=0819/plant-pathology-2021-fgvc8-8seeds.tar.gz
ARCHIVE=${SOURCE_ROOT}/${ARCHIVE_REL}
ARCHIVE_SHA=f583a74a3e828d45a22de11158d79ab5ed33c51dd58933b076b48dc191e7ed4d
ARCHIVE_SIZE=109828866
ARCHIVE_MTIME_NS=1787238813000000000
FAILED_MONITOR_LOG=${STATE_ROOT}/logs/monitor_rejection_20260819.log
FAILED_MONITOR_LOG_SHA=0327c63cf454ae800a03136b4d1a9c3a6ee7b50b8824daabfe03ed0126f3cf3f
FAILED_ATTEMPT_LOG=${STATE_ROOT}/attempts/0819-plant-pathology-2021-fgvc8-8seeds-f583a74a3e828d45.1070095/snapshot/logs/01_intake.log
FAILED_ATTEMPT_LOG_SHA=e8aa85bbd981efd3b789787520bde22022b6273b0bf77e9601f31c158ef1b6e6
DYNAMIC_TAG=plant_0819_task_identity_20260821
OUT_ROOT=${STATE_ROOT}/diagnostics/${DYNAMIC_TAG}
SUPERVISOR_LOG=${STATE_ROOT}/logs/plant_structural_recovery_supervisor_20260821.log
SUPERVISOR_PID_FILE=${STATE_ROOT}/plant_structural_recovery_supervisor_20260821.pid
CONTINUATION_PID_FILE=${STATE_ROOT}/rejection_monitor_20260821.pid
CONTINUATION_LOG=${STATE_ROOT}/logs/monitor_rejection_20260821.log
MAX_WAIT_POLLS=121
POLL_SECONDS=15

mode="${1:-}"
control_repo="${2:-}"
control_commit="${3:-}"
if [[ -z "${control_repo}" || ! "${control_commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: supervisor (--initialize|--run) CONTROL_REPO FULL_CONTROL_COMMIT' >&2
  exit 64
fi

verify_control() {
  test -x "${PYTHON}"
  test -d "${SOURCE_ROOT}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${ARCHIVE}" | awk '{print $1}')" = "${ARCHIVE_SHA}"
  test "$(stat -c '%s' "${ARCHIVE}")" = "${ARCHIVE_SIZE}"
  test "$(stat -c '%Y000000000' "${ARCHIVE}")" = "${ARCHIVE_MTIME_NS}"
  test "$(sha256sum "${FAILED_MONITOR_LOG}" | awk '{print $1}')" = "${FAILED_MONITOR_LOG_SHA}"
  test "$(sha256sum "${FAILED_ATTEMPT_LOG}" | awk '{print $1}')" = "${FAILED_ATTEMPT_LOG_SHA}"
  grep -q 'PROSPECTIVE_REJECTION_MONITOR_FAIL_CLOSED poll=135 rc=1' "${FAILED_MONITOR_LOG}"
  grep -q 'IntakeError: journal must identify exactly one competition' "${FAILED_ATTEMPT_LOG}"
  test ! -e "${STATE_ROOT}/BASELINE_INVALID"
}

if [[ "${mode}" == --initialize ]]; then
  verify_control
  test ! -e "${OUT_ROOT}"
  mkdir -p "${STATE_ROOT}/logs"

  echo 'PREFLIGHT_01_DIRECTION=current decision-corpus mainline; exact 0819 plant structural recovery only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_ARCHIVE_SHA256=${ARCHIVE_SHA}"
  echo "PREFLIGHT_04_ARCHIVE_SIZE=${ARCHIVE_SIZE}"
  echo "PREFLIGHT_05_ARCHIVE_MTIME_NS=${ARCHIVE_MTIME_NS}"
  echo "PREFLIGHT_06_FAILED_MONITOR_LOG_SHA256=${FAILED_MONITOR_LOG_SHA}"
  echo "PREFLIGHT_07_FAILED_ATTEMPT_LOG_SHA256=${FAILED_ATTEMPT_LOG_SHA}"
  echo 'PREFLIGHT_08_PRECONDITION=exact plant archive must remain first ready and unresolved'
  echo 'PREFLIGHT_09_AUDIT=credential-shape scan precedes journal JSON; env/live-event members never read'
  echo 'PREFLIGHT_10_REJECTION=only if at least one journal has competition-cardinality not equal to one'
  echo 'PREFLIGHT_11_LEAKAGE=task identity values code stdout grades metric values and outcomes are not emitted'
  echo 'PREFLIGHT_12_REPRO=two byte-identical audits registries and structural gates; immutable SHA bindings'
  echo 'PREFLIGHT_13_BATCH=exact 8-archive manifest must finish resolved with full source hashing'
  echo 'PREFLIGHT_14_GATE=pairs>=1500 runs>=150 tasks>=15 dominant<=0.25 cohort_runs>=960'
  echo 'PREFLIGHT_15_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_16_RUNTIME=expected 5-15m; hard supervisor wait 30m; continuation early-stops'
  echo 'PREFLIGHT_17_FAILURE=any log archive identity audit registry intake batch or gate mismatch fails closed'

  if [[ -s "${SUPERVISOR_PID_FILE}" ]]; then
    old_pid="$(cat "${SUPERVISOR_PID_FILE}")"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline="$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${old_cmdline}" == *run_0819_plant_structural_recovery_supervisor_20260821.sh* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${old_pid}" "${SUPERVISOR_LOG}"
        exit 0
      fi
      echo 'plant recovery PID file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${control_repo}/phase1/scripts/run_0819_plant_structural_recovery_supervisor_20260821.sh" \
    --run "${control_repo}" "${control_commit}" >> "${SUPERVISOR_LOG}" 2>&1 </dev/null &
  supervisor_pid=$!
  printf '%s\n' "${supervisor_pid}" > "${SUPERVISOR_PID_FILE}"
  printf 'PLANT_STRUCTURAL_RECOVERY_SUPERVISOR_STARTED pid=%s log=%s\n' \
    "${supervisor_pid}" "${SUPERVISOR_LOG}"
  exit 0
fi

if [[ "${mode}" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_control
mkdir -p "${OUT_ROOT}"
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
  "${OUT_ROOT}/diagnostic_receipt_plant_0819.json"

builder_args=(
  --archive "${ARCHIVE}"
  --archive-relative-path "${ARCHIVE_REL}"
  --expect-archive-sha256 "${ARCHIVE_SHA}"
  --diagnostic-receipt "${OUT_ROOT}/diagnostic_receipt_plant_0819.json"
  --expect-source-commit "${control_commit}"
)
(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.build_structural_rejection_registry \
    "${builder_args[@]}" --output "${OUT_ROOT}/registry_a.json" \
    > "${OUT_ROOT}/registry_a.stdout"
  "${PYTHON}" -m phase1.build_structural_rejection_registry \
    "${builder_args[@]}" --output "${OUT_ROOT}/registry_b.json" \
    > "${OUT_ROOT}/registry_b.stdout"
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
    raise SystemExit("plant structural-rejection registry validation failed")
print("PLANT_STRUCTURAL_REJECTION_REGISTRY_VALIDATED", actual)
PY

continuation_start_line=0
if [[ -f "${CONTINUATION_LOG}" ]]; then
  continuation_start_line="$(wc -l < "${CONTINUATION_LOG}")"
fi
bash "${control_repo}/phase1/scripts/run_prospective_rejection_monitor_20260821.sh" \
  --initialize "${control_repo}" "${control_commit}" "${registry_sha}" "${DYNAMIC_TAG}"
continuation_pid="$(cat "${CONTINUATION_PID_FILE}")"
continuation_exited=false
for ((poll=0; poll<MAX_WAIT_POLLS; poll++)); do
  if ! kill -0 "${continuation_pid}" 2>/dev/null; then
    continuation_exited=true
    break
  fi
  continuation_cmdline="$(tr '\0' ' ' < "/proc/${continuation_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${continuation_cmdline}" != *run_prospective_rejection_monitor_20260821.sh* \
    || "${continuation_cmdline}" != *"${control_commit}"* \
    || "${continuation_cmdline}" != *"${DYNAMIC_TAG}"* ]]; then
    echo 'continuation monitor PID identity changed while waiting' >&2
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

(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.verify_prospective_archive_batch \
    --source-root "${SOURCE_ROOT}" \
    --state-root "${STATE_ROOT}" \
    --manifest "${control_repo}/phase1/results/prospective_0819_intake_plan_20260821/archive_manifest.json" \
    --expect-manifest-sha256 d0c0ac148d4277cb11df4a13e5a23f29f57a043772d83423aa606ee1f996f017 \
    --hash-source-archives --require-resolved \
    > "${OUT_ROOT}/batch_resolved_hashcheck.json"
)

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
  "${OUT_ROOT}/structural_rejections_0819.json" \
  "${OUT_ROOT}/batch_resolved_hashcheck.json" "${OUT_ROOT}/structural_gate_a.json" \
  > "${OUT_ROOT}/sha256_manifest.txt"
printf '%s PLANT_RECOVERY_AND_0819_BATCH_VERIFIED snapshot=%s outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot_sha}"
