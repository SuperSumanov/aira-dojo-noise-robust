#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

STATE_ROOT=/research/d7/spc/yzyang4/prospective_decision_v1
PYTHON=/research/d7/spc/yzyang4/venvs/exp/bin/python
SCORER_REPO=/research/d7/spc/yzyang4/worktrees/codex_wl_escrow_031edb3
SCORER_COMMIT=031edb34400781ca026bc9833ac7f850312ffb1c
PROTOCOL=${SCORER_REPO}/phase1/wl_graph_prediction_protocol_v1.json
PROTOCOL_SHA=e3d299863eacf3655d17de378e7838bbebecfc347d751f33d19249b6b9f0bda3
ACTIVATION=/research/d7/spc/yzyang4/wl-graph-activation-031edb3-v1/activation_receipt.json
ACTIVATION_SHA=0139670acc49c961e38e6851d0416d1e5bfa1c318024b50330c15d51823112fb
BUNDLE_RUN_ROOT=/research/d7/spc/yzyang4/wl-graph-multiview-f67157a-v1
BUNDLE_ROOT=${BUNDLE_RUN_ROOT}/result
BUNDLE=${BUNDLE_ROOT}/wl_graph_multiview_scorer.npz
BUNDLE_SHA=df02cd1f5ba74be6b171ee9c377eeb58cf209a310a470b2ade671f2db03ee19e
BUNDLE_SUMMARY=${BUNDLE_ROOT}/summary.json
BUNDLE_SUMMARY_SHA=d8d1b57172e4b63f391a0ca93b1213c0f040adf9592637c38d057ad6576622f5
BUNDLE_VERIFICATION=${BUNDLE_RUN_ROOT}/independent_verification.json
BUNDLE_VERIFICATION_SHA=9918e6797b8f48fa9bb72e8cb740d1d5fab0ef81c0a961809fef40250b3e6b6e
PRIOR_ROOT=/research/d7/spc/yzyang4/wl-graph-escrow-88cb-031edb3-v1
PRIOR_ARTIFACT=${PRIOR_ROOT}/artifact
PRIOR_SUMMARY_SHA=ff49cee419a2cc90230fb0dad44058b9e61bb73fd90c38b77509b91b512c13be
PRIOR_SNAPSHOT=88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8
RECOVERY_LOG=${STATE_ROOT}/logs/structural_recovery_supervisor_20260821.log
DIRECT_HANDOFF_LOG=${STATE_ROOT}/logs/direct_0819_batch_handoff_20260821.log
SUPERVISOR_LOG=${STATE_ROOT}/logs/post_0819_wl_graph_escrow_supervisor_20260821.log
SUPERVISOR_PID_FILE=${STATE_ROOT}/post_0819_wl_graph_escrow_supervisor_20260821.pid
DIRECT_SUPERVISOR_LOG=${STATE_ROOT}/logs/post_0819_wl_graph_escrow_direct_supervisor_20260821.log
DIRECT_SUPERVISOR_PID_FILE=${STATE_ROOT}/post_0819_wl_graph_escrow_direct_supervisor_20260821.pid
OUT_PARENT=/research/d7/spc/yzyang4/wl-graph-escrow-post0819
MAX_WAIT_POLLS=361
POLL_SECONDS=60

mode="${1:-}"
upstream_pid="${2:-}"
control_repo="${3:-}"
control_commit="${4:-}"
upstream_start_line="${5:-}"
if [[ ! "${upstream_pid}" =~ ^[0-9]+$ || -z "${control_repo}" \
  || ! "${control_commit}" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: supervisor (--initialize|--run|--direct-initialize|--direct-run) UPSTREAM_PID CONTROL_REPO FULL_CONTROL_COMMIT [UPSTREAM_START_LINE]' >&2
  exit 64
fi

if [[ "${mode}" == --direct-initialize || "${mode}" == --direct-run ]]; then
  upstream_log="${DIRECT_HANDOFF_LOG}"
  upstream_identity=run_0819_direct_batch_handoff_20260821.sh
  completion_marker=DIRECT_0819_BATCH_HANDOFF_VERIFIED
  active_supervisor_log="${DIRECT_SUPERVISOR_LOG}"
  active_supervisor_pid_file="${DIRECT_SUPERVISOR_PID_FILE}"
  child_mode=--direct-run
  upstream_label=direct_handoff
else
  upstream_log="${RECOVERY_LOG}"
  upstream_identity=run_0819_structural_recovery_supervisor_20260821.sh
  completion_marker=STRUCTURAL_RECOVERY_AND_0819_BATCH_VERIFIED
  active_supervisor_log="${SUPERVISOR_LOG}"
  active_supervisor_pid_file="${SUPERVISOR_PID_FILE}"
  child_mode=--run
  upstream_label=recovery
fi

verify_fixed_inputs() {
  command -v strace >/dev/null
  command -v timeout >/dev/null
  test -x "${PYTHON}"
  test "$(git -C "${control_repo}" rev-parse HEAD)" = "${control_commit}"
  test -z "$(git -C "${control_repo}" status --porcelain --untracked-files=all)"
  test "$(git -C "${SCORER_REPO}" rev-parse HEAD)" = "${SCORER_COMMIT}"
  test -z "$(git -C "${SCORER_REPO}" status --porcelain --untracked-files=all)"
  test "$(sha256sum "${PROTOCOL}" | awk '{print $1}')" = "${PROTOCOL_SHA}"
  test "$(sha256sum "${ACTIVATION}" | awk '{print $1}')" = "${ACTIVATION_SHA}"
  test "$(sha256sum "${BUNDLE}" | awk '{print $1}')" = "${BUNDLE_SHA}"
  test "$(sha256sum "${BUNDLE_SUMMARY}" | awk '{print $1}')" = "${BUNDLE_SUMMARY_SHA}"
  test "$(sha256sum "${BUNDLE_VERIFICATION}" | awk '{print $1}')" = "${BUNDLE_VERIFICATION_SHA}"
  test "$(sha256sum "${PRIOR_ARTIFACT}/summary.json" | awk '{print $1}')" = "${PRIOR_SUMMARY_SHA}"
  test ! -e "${STATE_ROOT}/BASELINE_INVALID"
}

if [[ "${mode}" == --initialize || "${mode}" == --direct-initialize ]]; then
  verify_fixed_inputs
  if ! kill -0 "${upstream_pid}" 2>/dev/null; then
    echo "${upstream_label} supervisor is not live at initialization" >&2
    exit 2
  fi
  upstream_cmdline="$(tr '\0' ' ' < "/proc/${upstream_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${upstream_cmdline}" != *"${upstream_identity}"* ]]; then
    echo "${upstream_label} supervisor PID identity mismatch" >&2
    exit 2
  fi
  mkdir -p "${STATE_ROOT}/logs" "${OUT_PARENT}"
  upstream_start_line="$(wc -l < "${upstream_log}")"

  echo 'PREFLIGHT_01_DIRECTION=current decision-corpus mainline; frozen WL escrow append only'
  echo "PREFLIGHT_02_CONTROL_COMMIT=${control_commit}"
  echo "PREFLIGHT_03_SCIENTIFIC_SCORER_COMMIT=${SCORER_COMMIT}"
  echo "PREFLIGHT_04_PROTOCOL_SHA256=${PROTOCOL_SHA}"
  echo "PREFLIGHT_05_ACTIVATION_SHA256=${ACTIVATION_SHA}"
  echo "PREFLIGHT_06_BUNDLE_SHA256=${BUNDLE_SHA}"
  echo "PREFLIGHT_07_PRIOR_SNAPSHOT=${PRIOR_SNAPSHOT}"
  echo 'PREFLIGHT_08_MATRIX=4 frozen arms; no training; no arm selection; no outcome metrics'
  echo 'PREFLIGHT_09_COHORT=exact post-0819 immutable LATEST snapshot after structural gate verification'
  echo 'PREFLIGHT_10_APPEND=all prior endpoint and pair rows must remain exactly unchanged'
  echo 'PREFLIGHT_11_LEAKAGE=strace producer+independent verifier; any forbidden path observation fails'
  echo 'PREFLIGHT_12_REPRO=independent numerical recomputation max_diff<=1e-12; verifier twice byte-identical'
  echo 'PREFLIGHT_13_SECURITY=umask077; credential-shape scan; no env/archive/outcome input'
  echo 'PREFLIGHT_14_RESOURCES=CPU only; 2 processes sequential; hard timeout 2h each; GPU=0; API=0'
  echo 'PREFLIGHT_15_ESTIMATE=producer 10-15m; verifier 10-15m; total 25-40m after intake closes'
  echo 'PREFLIGHT_16_FAILURE=any nonzero rc/hash/schema/subset/trace mismatch stops before promotion'

  if [[ -s "${active_supervisor_pid_file}" ]]; then
    old_pid="$(cat "${active_supervisor_pid_file}")"
    if [[ "${old_pid}" =~ ^[0-9]+$ ]] && kill -0 "${old_pid}" 2>/dev/null; then
      old_cmdline="$(tr '\0' ' ' < "/proc/${old_pid}/cmdline" 2>/dev/null || true)"
      if [[ "${old_cmdline}" == *run_post_0819_wl_graph_escrow_20260821.sh* ]]; then
        printf 'ALREADY_RUNNING pid=%s log=%s\n' "${old_pid}" "${active_supervisor_log}"
        exit 0
      fi
      echo 'post-0819 supervisor PID file points to a different live process' >&2
      exit 2
    fi
  fi
  nohup bash "${control_repo}/phase1/scripts/run_post_0819_wl_graph_escrow_20260821.sh" \
    "${child_mode}" "${upstream_pid}" "${control_repo}" "${control_commit}" "${upstream_start_line}" \
    >> "${active_supervisor_log}" 2>&1 </dev/null &
  supervisor_pid=$!
  printf '%s\n' "${supervisor_pid}" > "${active_supervisor_pid_file}"
  printf 'POST_0819_WL_ESCROW_SUPERVISOR_STARTED pid=%s log=%s\n' \
    "${supervisor_pid}" "${active_supervisor_log}"
  exit 0
fi

if [[ ( "${mode}" != --run && "${mode}" != --direct-run ) \
  || ! "${upstream_start_line}" =~ ^[0-9]+$ ]]; then
  echo 'invalid --run invocation' >&2
  exit 64
fi

verify_fixed_inputs
printf '%s waiting_for_%s_pid=%s start_line=%s outcomes_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${upstream_label}" "${upstream_pid}" "${upstream_start_line}"
upstream_exited=false
for ((poll=0; poll<MAX_WAIT_POLLS; poll++)); do
  if ! kill -0 "${upstream_pid}" 2>/dev/null; then
    upstream_exited=true
    break
  fi
  upstream_cmdline="$(tr '\0' ' ' < "/proc/${upstream_pid}/cmdline" 2>/dev/null || true)"
  if [[ "${upstream_cmdline}" != *"${upstream_identity}"* ]]; then
    echo "${upstream_label} supervisor PID identity changed while waiting" >&2
    exit 2
  fi
  sleep "${POLL_SECONDS}"
done
if [[ "${upstream_exited}" != true ]]; then
  echo "${upstream_label} supervisor did not exit within wait window" >&2
  exit 4
fi

upstream_segment="$(mktemp)"
trap 'rm -f "${upstream_segment}"' EXIT
tail -n "+$((upstream_start_line + 1))" "${upstream_log}" > "${upstream_segment}"
completion_line="$(grep "${completion_marker} snapshot=" "${upstream_segment}" | tail -n 1 || true)"
if [[ ! "${completion_line}" =~ snapshot=([0-9a-f]{64})[[:space:]]outcomes_read=false$ ]]; then
  echo "${upstream_label} supervisor lacks a fresh verified completion marker" >&2
  exit 2
fi
snapshot_sha="${BASH_REMATCH[1]}"
if [[ "$(tr -d '\r\n' < "${STATE_ROOT}/LATEST")" != "${snapshot_sha}" ]]; then
  echo 'LATEST changed after recovery completion' >&2
  exit 2
fi
snapshot_root="${STATE_ROOT}/snapshots/${snapshot_sha}"
test -d "${snapshot_root}"

out_root="${OUT_PARENT}/${snapshot_sha}-031edb3-v1"
staging="${out_root}.staging.$$"
test ! -e "${out_root}"
test ! -e "${staging}"
mkdir -p "${staging}"
trap 'rm -f "${upstream_segment}"; if [[ -d "${staging:-}" ]]; then echo "FAILED_STAGING_PRESERVED=${staging}"; fi' EXIT

producer_args=(
  --repo-root "${SCORER_REPO}"
  --source-commit "${SCORER_COMMIT}"
  --protocol "${PROTOCOL}"
  --expect-protocol-sha256 "${PROTOCOL_SHA}"
  --activation-receipt "${ACTIVATION}"
  --expect-activation-receipt-sha256 "${ACTIVATION_SHA}"
  --bundle "${BUNDLE}"
  --expect-bundle-sha256 "${BUNDLE_SHA}"
  --bundle-summary "${BUNDLE_SUMMARY}"
  --expect-bundle-summary-sha256 "${BUNDLE_SUMMARY_SHA}"
  --bundle-verification "${BUNDLE_VERIFICATION}"
  --expect-bundle-verification-sha256 "${BUNDLE_VERIFICATION_SHA}"
  --state-root "${STATE_ROOT}"
  --snapshot-root "${snapshot_root}"
  --expect-snapshot-sha256 "${snapshot_sha}"
  --output "${staging}/artifact"
)
set +e
(
  cd "${SCORER_REPO}"
  /usr/bin/time -v -o "${staging}/producer.time" \
    timeout --signal=TERM 2h strace -f -e trace=file -o "${staging}/producer.strace" \
    "${PYTHON}" -m phase1.prospective_wl_graph_escrow "${producer_args[@]}"
) > >(tee "${staging}/producer.log") 2>&1
producer_rc=${PIPESTATUS[0]}
set -e
printf '%s\n' "${producer_rc}" > "${staging}/producer.rc"
if [[ "${producer_rc}" -ne 0 ]]; then
  echo "WL escrow producer failed rc=${producer_rc}" >&2
  exit "${producer_rc}"
fi

verifier_args=(
  --state-root "${STATE_ROOT}"
  --snapshot-root "${snapshot_root}"
  --expect-snapshot-sha256 "${snapshot_sha}"
  --bundle "${BUNDLE}"
  --expect-bundle-sha256 "${BUNDLE_SHA}"
  --activation-receipt "${ACTIVATION}"
  --expect-activation-receipt-sha256 "${ACTIVATION_SHA}"
  --artifact "${staging}/artifact"
  --output "${staging}/independent_verification.json"
)
set +e
(
  cd "${SCORER_REPO}"
  /usr/bin/time -v -o "${staging}/verifier.time" \
    timeout --signal=TERM 2h strace -f -e trace=file -o "${staging}/verifier.strace" \
    "${PYTHON}" -m phase1.verify_prospective_wl_graph_escrow "${verifier_args[@]}"
) > >(tee "${staging}/verifier.log") 2>&1
verifier_rc=${PIPESTATUS[0]}
set -e
printf '%s\n' "${verifier_rc}" > "${staging}/verifier.rc"
if [[ "${verifier_rc}" -ne 0 ]]; then
  echo "WL escrow independent verifier failed rc=${verifier_rc}" >&2
  exit "${verifier_rc}"
fi

append_args=(
  --prior-artifact "${PRIOR_ARTIFACT}"
  --current-artifact "${staging}/artifact"
  --current-independent-verification "${staging}/independent_verification.json"
  --expect-scorer-commit "${SCORER_COMMIT}"
  --expect-prior-summary-sha256 "${PRIOR_SUMMARY_SHA}"
  --expect-prior-snapshot-sha256 "${PRIOR_SNAPSHOT}"
  --expect-current-snapshot-sha256 "${snapshot_sha}"
  --trace "${staging}/producer.strace"
  --trace "${staging}/verifier.strace"
  --scan-root "${staging}/artifact"
  --scan-root "${staging}/independent_verification.json"
  --scan-root "${staging}/producer.log"
  --scan-root "${staging}/verifier.log"
  --scan-root "${staging}/producer.strace"
  --scan-root "${staging}/verifier.strace"
)
(
  cd "${control_repo}"
  "${PYTHON}" -m phase1.verify_wl_graph_escrow_append \
    "${append_args[@]}" --output "${staging}/append_verification_a.json" \
    > "${staging}/append_verification_a.stdout"
  "${PYTHON}" -m phase1.verify_wl_graph_escrow_append \
    "${append_args[@]}" --output "${staging}/append_verification_b.json" \
    > "${staging}/append_verification_b.stdout"
)
cmp "${staging}/append_verification_a.json" "${staging}/append_verification_b.json"

(
  cd "${staging}"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)
mv "${staging}" "${out_root}"
trap 'rm -f "${upstream_segment}"' EXIT
printf '%s POST_0819_WL_ESCROW_VERIFIED snapshot=%s artifact=%s outcomes_read=false effect_metrics=0\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${snapshot_sha}" "${out_root}"
