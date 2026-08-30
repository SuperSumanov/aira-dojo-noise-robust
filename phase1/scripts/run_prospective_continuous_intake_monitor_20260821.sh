#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

SOURCE_ROOT=/research/d7/spc/yzyang4/external/senior_data/mle
STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
SCIENTIFIC_REPO=/research/d7/spc/yzyang4/worktrees/prospective_score_identity_migration_5ed1988
SCIENTIFIC_COMMIT=5ed1988045a3fd8c365d001c87977314572383d9
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
EXTRA_0819_REGISTRY=/research/d7/spc/yzyang4/prospective_decision_v1/diagnostics/plant_0819_task_identity_20260821/structural_rejections_0819.json
EXTRA_0819_REGISTRY_SHA=0dc58a4f2b2770f615b4ebf6d077c25ec7866d0f0ad72a2cc2f312d8d4f1d503
EXTRA_0820_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260822/structural_rejections_0820.json
EXTRA_0820_REGISTRY_SHA=766a4fa678a4cb9ae55fdb460ae94b5f1be93ce2040b64ed7e48c13260f9aebd
EXTRA_0821_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260823/structural_rejections_0821.json
EXTRA_0821_REGISTRY_SHA=7c16889eb5ec57b1ca391b4171a997ad0fcd35d076ad6b34fddb53b556e35e6e
EXTRA_0822_REGISTRY_REL=phase1/results/prospective_structural_rejection_20260824/structural_rejections_0822.json
EXTRA_0822_REGISTRY_SHA=8d085fd9c195c306f2a9c01d66ad13044f44b1f182fc6170907912dbd80d344b
EXTRA_0822_AI4CODE_REGISTRY_REL=phase1/results/prospective_structural_rejection_ai4code_20260824/structural_rejections_ai4code_0822.json
EXTRA_0822_AI4CODE_REGISTRY_SHA=992d1a25267a66e161c7b2a4143c30110816011e09a3d82929f65cb8a00d33b7
EXTRA_0823_AI4CODE_REGISTRY_REL=phase1/results/prospective_structural_rejection_ai4code_20260825/structural_rejections_ai4code_0823.json
EXTRA_0823_AI4CODE_REGISTRY_SHA=0162c771ce1df3743776642456247d0974b7bc6e40550ca98fd626ee3dc6653f
EXTRA_0823_LMSYS_REGISTRY_REL=phase1/results/prospective_structural_rejection_lmsys_20260825/structural_rejections_lmsys_0823.json
EXTRA_0823_LMSYS_REGISTRY_SHA=81b9c87f140265b3438587953aadfd00ff3f53ca665799b807ec4c80596bd005
ARCHIVE_CONTENT_ALIAS_REGISTRY=/research/d7/spc/yzyang4/archive-content-alias/formal-9b7640a-v1/archive_content_alias_registry.json
ARCHIVE_CONTENT_ALIAS_REGISTRY_SHA=080a6df133c8b8184267f074e0620b2a9ebf1d21616b0dfb7674eebad2c28dcb
ARCHIVE_CONTENT_ALIAS_POSTFLIGHT=/research/d7/spc/yzyang4/archive-content-alias/postflight-9b7640a-v2
ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_MANIFEST_SHA=1fa3c81c257316d2c2886ddbd36f72e60f1d8ed85f889450916e4d59de3a8625
POLL_SECONDS=300
MAX_POLLS=145

mode="${1:-}"
control_repo="${2:-}"
control_commit="${3:-}"
if [[ -z "${control_repo}" || ! "${control_commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: monitor (--initialize|--run) CONTROL_REPO FULL_CONTROL_COMMIT' >&2
  exit 64
fi

registry="${control_repo}/${REGISTRY_REL}"
additional_registry="${control_repo}/${ADDITIONAL_REGISTRY_REL}"
extra_0816_registry="${control_repo}/${EXTRA_0816_REGISTRY_REL}"
extra_0817_registry="${control_repo}/${EXTRA_0817_REGISTRY_REL}"
extra_0818_registry="${control_repo}/${EXTRA_0818_REGISTRY_REL}"
extra_0820_registry="${control_repo}/${EXTRA_0820_REGISTRY_REL}"
extra_0821_registry="${control_repo}/${EXTRA_0821_REGISTRY_REL}"
extra_0822_registry="${control_repo}/${EXTRA_0822_REGISTRY_REL}"
extra_0822_ai4code_registry="${control_repo}/${EXTRA_0822_AI4CODE_REGISTRY_REL}"
extra_0823_ai4code_registry="${control_repo}/${EXTRA_0823_AI4CODE_REGISTRY_REL}"
extra_0823_lmsys_registry="${control_repo}/${EXTRA_0823_LMSYS_REGISTRY_REL}"
log_root="${STATE_ROOT}/logs"
monitor_log="${log_root}/continuous_intake_monitor_20260821.log"
pid_file="${STATE_ROOT}/continuous_intake_monitor_20260821.pid"
script="${control_repo}/phase1/scripts/run_prospective_continuous_intake_monitor_20260821.sh"

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
  test "$(sha256sum "${EXTRA_0819_REGISTRY}" | awk '{print $1}')" = "${EXTRA_0819_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0820_registry}" | awk '{print $1}')" = "${EXTRA_0820_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0821_registry}" | awk '{print $1}')" = "${EXTRA_0821_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0822_registry}" | awk '{print $1}')" = "${EXTRA_0822_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0822_ai4code_registry}" | awk '{print $1}')" = "${EXTRA_0822_AI4CODE_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0823_ai4code_registry}" | awk '{print $1}')" = "${EXTRA_0823_AI4CODE_REGISTRY_SHA}"
  test "$(sha256sum "${extra_0823_lmsys_registry}" | awk '{print $1}')" = "${EXTRA_0823_LMSYS_REGISTRY_SHA}"
  test -f "${ARCHIVE_CONTENT_ALIAS_POSTFLIGHT}/COMPLETE"
  test "$(sha256sum "${ARCHIVE_CONTENT_ALIAS_POSTFLIGHT}/SHA256SUMS" | awk '{print $1}')" = "${ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_MANIFEST_SHA}"
  test "$(sha256sum "${ARCHIVE_CONTENT_ALIAS_REGISTRY}" | awk '{print $1}')" = "${ARCHIVE_CONTENT_ALIAS_REGISTRY_SHA}"
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
      --extra-structural-rejection-registry "${EXTRA_0819_REGISTRY}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0819_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0820_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0820_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0821_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0821_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0822_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0822_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0822_ai4code_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0822_AI4CODE_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0823_ai4code_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0823_AI4CODE_REGISTRY_SHA}" \
      --extra-structural-rejection-registry "${extra_0823_lmsys_registry}" \
      --expect-extra-structural-rejection-registry-sha256 "${EXTRA_0823_LMSYS_REGISTRY_SHA}" \
      --archive-content-alias-registry "${ARCHIVE_CONTENT_ALIAS_REGISTRY}" \
      --expect-archive-content-alias-registry-sha256 "${ARCHIVE_CONTENT_ALIAS_REGISTRY_SHA}" \
      --minimum-age-seconds 21600 \
      --minimum-observations 3 \
      --minimum-observation-interval-seconds 300 \
      --minimum-stable-span-seconds 600 \
      "$@"
  )
}

if [[ "${mode}" == --initialize ]]; then
  verify_contracts
  mkdir -p "${log_root}"
  runner --observe-only > "${log_root}/continuous_intake_binding_smoke_20260821.log" 2>&1

  echo 'PREFLIGHT_01_DIRECTION=strict-future transition escrow append-only intake only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_SCIENTIFIC_COMMIT=${SCIENTIFIC_COMMIT}"
  echo "PREFLIGHT_04_0819_REJECTION_SHA256=${EXTRA_0819_REGISTRY_SHA}"
  echo "PREFLIGHT_04B_0820_REJECTION_SHA256=${EXTRA_0820_REGISTRY_SHA}"
  echo "PREFLIGHT_04C_0821_REJECTION_SHA256=${EXTRA_0821_REGISTRY_SHA}"
  echo "PREFLIGHT_04D_0822_REJECTION_SHA256=${EXTRA_0822_REGISTRY_SHA}"
  echo "PREFLIGHT_04E_0822_AI4CODE_REJECTION_SHA256=${EXTRA_0822_AI4CODE_REGISTRY_SHA}"
  echo "PREFLIGHT_04F_0823_AI4CODE_REJECTION_SHA256=${EXTRA_0823_AI4CODE_REGISTRY_SHA}"
  echo "PREFLIGHT_04G_0823_LMSYS_REJECTION_SHA256=${EXTRA_0823_LMSYS_REGISTRY_SHA}"
  echo "PREFLIGHT_04H_ARCHIVE_CONTENT_ALIAS_REGISTRY_SHA256=${ARCHIVE_CONTENT_ALIAS_REGISTRY_SHA}"
  echo "PREFLIGHT_04I_ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_MANIFEST_SHA256=${ARCHIVE_CONTENT_ALIAS_POSTFLIGHT_MANIFEST_SHA}"
  echo 'PREFLIGHT_05_INPUT=stable append-only senior archives bound by exact path size mtime and SHA256'
  echo 'PREFLIGHT_06_ESTIMAND=unchanged; no outcome metric and no historical backfill'
  echo 'PREFLIGHT_07_SECURITY=credential-first journal audit; env and live-event members never read; umask077'
  echo 'PREFLIGHT_08_LEAKAGE=outcomes label vault scores and predictions remain closed during intake'
  echo 'PREFLIGHT_09_REPRO=clean fixed scientific/control commits and immutable rejection registries'
  echo 'PREFLIGHT_10_RESOURCES=CPU only; GPU=0; API=0; base-LLM-update=0'
  echo 'PREFLIGHT_11_FAILURE=unknown structural or identity issue stops the monitor fail-closed'
  echo 'PREFLIGHT_12_STABILITY=minimum age 21600s; three observations; 300s spacing; 600s stable span'
  echo "PREFLIGHT_13_RUNTIME=${MAX_POLLS} polls x ${POLL_SECONDS}s; one ready archive per poll"

  if [[ -s "${pid_file}" ]]; then
    old_pid="$(cat "${pid_file}")"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline="$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${old_cmdline}" == *"${script} --run"* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${old_pid}" "${monitor_log}"
        exit 0
      fi
      echo 'pid file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${script}" --run "${control_repo}" "${control_commit}" \
    >> "${monitor_log}" 2>&1 </dev/null &
  monitor_pid=$!
  printf '%s\n' "${monitor_pid}" > "${pid_file}"
  printf 'PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_STARTED pid=%s log=%s\n' \
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
    printf '%s PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_FAIL_CLOSED poll=%d rc=%d\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${runner_rc}"
    exit "${runner_rc}"
  fi
  if (( poll + 1 < MAX_POLLS )); then
    sleep "${POLL_SECONDS}"
  fi
done
printf '%s PROSPECTIVE_CONTINUOUS_INTAKE_MONITOR_COMPLETE polls=%d outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${MAX_POLLS}"
