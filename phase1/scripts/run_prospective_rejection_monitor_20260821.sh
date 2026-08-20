#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
SCIENTIFIC_REPO=/research/d7/spc/yzyang4/worktrees/prospective_production_90842c4
SCIENTIFIC_COMMIT=90842c49dbd73d41d405a5ecdad2224ee447b375
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
REGISTRY_REL=phase1/results/prospective_structural_rejection_20260816/structural_rejections.json
REGISTRY_SHA=d32cd70b7c755a8ad340cf376fd88f54ca1bea0a50cffbc5fa4cb58bc97ffb01
ADDITIONAL_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260816/structural_rejections_0815.json
ADDITIONAL_REGISTRY_SHA=64e009d3ff1460101b84ff269e12d437ae95a4b0df27fe5a904dc259e09555c2
EXTRA_0816_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260818/structural_rejections_0816.json
EXTRA_0816_REGISTRY_SHA=02f51081e6cdbc6451a3ffdc3d4f14761e627c28bf9c646529fcfb5755b219a6
EXTRA_0817_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260819/structural_rejections_0817.json
EXTRA_0817_REGISTRY_SHA=f4758f9dbb634607b65c128cd03430e0d9494c09d674293912275bd0941da545
EXTRA_0818_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260820/structural_rejections_0818.json
EXTRA_0818_REGISTRY_SHA=91369ba5cc571f607907d1bf209b4bc77a370137110bf167226173a664e324c6
BATCH_MANIFEST_REL=phase1/results/prospective_0819_intake_plan_20260821/archive_manifest.json
BATCH_MANIFEST_SHA=d0c0ac148d4277cb11df4a13e5a23f29f57a043772d83423aa606ee1f996f017
POLL_SECONDS=60
MAX_POLLS=181

mode="${1:-}"
control_repo="${2:-}"
control_commit="${3:-}"
dynamic_registry_sha="${4:-}"
dynamic_registry_tag="${5:-multi_modal_0819_task_identity_20260821}"
if [[ -z "${control_repo}" || ! "${control_commit}" =~ ^[0-9a-f]{40}$ \
  || ! "${dynamic_registry_sha}" =~ ^[0-9a-f]{64}$ \
  || ! "${dynamic_registry_tag}" =~ ^[a-z0-9_]+$ ]]; then
  echo 'usage: monitor (--initialize|--run) CONTROL_REPO FULL_CONTROL_COMMIT DYNAMIC_REGISTRY_SHA [DYNAMIC_REGISTRY_TAG]' >&2
  exit 64
fi

dynamic_root=${STATE_ROOT}/diagnostics/${dynamic_registry_tag}
dynamic_registry=${dynamic_root}/structural_rejections_0819.json

registry="${control_repo}/${REGISTRY_REL}"
additional_registry="${control_repo}/${ADDITIONAL_REGISTRY_REL}"
extra_0816_registry="${control_repo}/${EXTRA_0816_REGISTRY_REL}"
extra_0817_registry="${control_repo}/${EXTRA_0817_REGISTRY_REL}"
extra_0818_registry="${control_repo}/${EXTRA_0818_REGISTRY_REL}"
batch_manifest="${control_repo}/${BATCH_MANIFEST_REL}"
log_root="${STATE_ROOT}/logs"
monitor_log="${log_root}/monitor_rejection_20260821.log"
pid_file="${STATE_ROOT}/rejection_monitor_20260821.pid"

verify_contracts() {
  test -x "${PYTHON}"
  test -d "${SOURCE_ROOT}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(git -C "${SCIENTIFIC_REPO}" rev-parse HEAD)" = "${SCIENTIFIC_COMMIT}"
  test -z "$(git -C "${SCIENTIFIC_REPO}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${registry}" | awk '{print $1}')" = "${REGISTRY_SHA}"
  test "$(sha256sum "${additional_registry}" | awk '{print $1}')" = "${ADDITIONAL_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0816_registry}" | awk '{print $1}')" = "${EXTRA_0816_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0817_registry}" | awk '{print $1}')" = "${EXTRA_0817_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0818_registry}" | awk '{print $1}')" = "${EXTRA_0818_REGISTRY_SHA}"
  test "$(sha256sum "${batch_manifest}" | awk '{print $1}')" = "${BATCH_MANIFEST_SHA}"
  test "$(sha256sum "${dynamic_registry}" | awk '{print $1}')" = "${dynamic_registry_sha}"
  test "$(tr -d '\r\n' < "${STATE_ROOT}/production_commit.txt")" = "${SCIENTIFIC_COMMIT}"
  test ! -e "${STATE_ROOT}/BASELINE_INVALID"
}

runner() {
  (
    cd "${control_repo}"
    "${PYTHON}" -m phase1.prospective_production_runner \
      --source-root "${SOURCE_ROOT}" \
      --state-root "${STATE_ROOT}" \
      --repo-root "${SCIENTIFIC_REPO}" \
      --expected-commit "${SCIENTIFIC_COMMIT}" \
      --structural-rejection-registry "${registry}" \
      --expect-structural-rejection-registry-sha256 "${REGISTRY_SHA}" \
      --additional-structural-rejection-registry "${additional_registry}" \
      --expect-additional-structural-rejection-registry-sha256 "${ADDITIONAL_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0816_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0816_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0817_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0817_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0818_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0818_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${dynamic_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${dynamic_registry_sha}" \
      --minimum-age-seconds 21600 \
      --minimum-observations 3 \
      --minimum-observation-interval-seconds 300 \
      --minimum-stable-span-seconds 600 \
      "$@"
  )
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
  verify_contracts
  mkdir -p "${log_root}"
  runner --observe-only > "${log_root}/rejection_binding_smoke_20260821.log" 2>&1
  batch_status --hash-source-archives > "${log_root}/batch_manifest_smoke_20260821.log"

  echo 'PREFLIGHT_01_DIRECTION=first-960 outcome-blind corpus extension only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_SCIENTIFIC_COMMIT=${SCIENTIFIC_COMMIT}"
  echo "PREFLIGHT_04_BATCH_MANIFEST_SHA256=${BATCH_MANIFEST_SHA}"
  echo "PREFLIGHT_05_DYNAMIC_REJECTION_REGISTRY_SHA256=${dynamic_registry_sha}"
  echo "PREFLIGHT_05B_DYNAMIC_REJECTION_REGISTRY_TAG=${dynamic_registry_tag}"
  echo 'PREFLIGHT_06_INPUT=8 exact 0819 archives bound by path size mtime and SHA256'
  echo 'PREFLIGHT_07_ESTIMAND=unchanged first-960 structural prefix; no label estimand'
  echo 'PREFLIGHT_08_EXPECTED=7 valid commits plus 1 exact structural rejection if audit supports it'
  echo 'PREFLIGHT_09_SECURITY=credential-first audit; env/live-event payloads unread; umask077'
  echo 'PREFLIGHT_10_LEAKAGE=outcomes label vault frozen scores and predictions remain closed'
  echo 'PREFLIGHT_11_REPRO=clean exact commits immutable manifests registries transactions snapshots'
  echo 'PREFLIGHT_12_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_13_FAILURE=any identity binding intake or batch disposition mismatch fails closed'
  echo "PREFLIGHT_14_RUNTIME=${MAX_POLLS} polls x ${POLL_SECONDS}s; early stop when all 8 resolved"

  if [[ -s "${pid_file}" ]]; then
    old_pid="$(cat "${pid_file}")"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline="$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${old_cmdline}" == *run_prospective_rejection_monitor_20260821.sh* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${old_pid}" "${monitor_log}"
        exit 0
      fi
      echo 'pid file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${control_repo}/phase1/scripts/run_prospective_rejection_monitor_20260821.sh" \
    --run "${control_repo}" "${control_commit}" "${dynamic_registry_sha}" "${dynamic_registry_tag}" \
    >> "${monitor_log}" 2>&1 </dev/null &
  monitor_pid=$!
  printf '%s\n' "${monitor_pid}" > "${pid_file}"
  printf 'PROSPECTIVE_REJECTION_MONITOR_STARTED pid=%s log=%s\n' \
    "${monitor_pid}" "${monitor_log}"
  exit 0
fi

if [[ "${mode}" != --run ]]; then
  echo 'first argument must be --initialize or --run' >&2
  exit 64
fi

verify_contracts
for ((poll=0; poll<MAX_POLLS; poll++)); do
  printf '%s poll_start=%d\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}"
  set +e
  runner --require-strace
  runner_rc=$?
  set -e
  printf '%s poll_end=%d rc=%d\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${runner_rc}"
  if (( runner_rc != 0 )); then
    printf '%s PROSPECTIVE_REJECTION_MONITOR_FAIL_CLOSED poll=%d rc=%d\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${runner_rc}"
    exit "${runner_rc}"
  fi

  status_file="${log_root}/batch_status_20260821.json"
  set +e
  batch_status --require-resolved > "${status_file}.tmp"
  batch_rc=$?
  set -e
  mv "${status_file}.tmp" "${status_file}"
  cat "${status_file}"
  if (( batch_rc == 0 )); then
    batch_status --hash-source-archives --require-resolved \
      > "${log_root}/batch_complete_hashcheck_20260821.json"
    printf '%s PROSPECTIVE_0819_BATCH_COMPLETE polls=%d outcomes_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$((poll + 1))"
    exit 0
  fi
  if (( batch_rc != 3 )); then
    printf '%s PROSPECTIVE_0819_BATCH_FAIL_CLOSED poll=%d rc=%d\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${batch_rc}"
    exit "${batch_rc}"
  fi
  sleep "${POLL_SECONDS}"
done
printf '%s PROSPECTIVE_0819_BATCH_TIMEOUT polls=%d\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${MAX_POLLS}"
exit 4
