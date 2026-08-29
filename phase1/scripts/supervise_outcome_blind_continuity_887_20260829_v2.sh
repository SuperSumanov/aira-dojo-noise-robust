#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly control_commit=${OUTCOME_BLIND_SUPERVISOR_CONTROL_COMMIT:-}
readonly public_path=phase1/scripts/supervise_outcome_blind_continuity_887_20260829_v2.sh
readonly guard_public_path=phase1/scripts/guard_outcome_blind_continuity_887_20260829_v4.sh
readonly renewal_public_path=phase1/scripts/renew_outcome_blind_monitors_887_20260829_v4.sh
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly root=/research/d7/spc/yzyang4/monitor-relaunch-887/20260829-supervisor-v2
readonly failed_supervisor=/research/d7/spc/yzyang4/monitor-relaunch-887/20260829-supervisor-v1
readonly baseline=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly source_root=/research/d7/spc/yzyang4/external/senior_data/mle
readonly old_guard=/research/d7/spc/yzyang4/six-hour-structural-guard-20260829-v3
readonly new_guard=/research/d7/spc/yzyang4/six-hour-structural-guard-20260829-v4
readonly renewal_root=/research/d7/spc/yzyang4/monitor-relaunch-887/20260829-v4
readonly transition=/research/d7/spc/yzyang4/transition-future-escrow/monitor_7458f09_snapshot_chain_v1
readonly receipt=/research/d7/spc/yzyang4/prediction-receipt-common-support/monitor_9f2cbe9_v1
readonly config=/research/d7/spc/yzyang4/future-config-v2-readiness/monitor_20260829_v7
readonly target=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/monitor_519815d_after_887_v1

if [[ ! ${control_commit} =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'OUTCOME_BLIND_SUPERVISOR_CONTROL_COMMIT must be a 40-hex public commit' >&2
  exit 64
fi
test ! -e "${root}"
test ! -e "${new_guard}"
test ! -e "${renewal_root}"
mkdir -p "${root}"
exec 9> "${root}/supervisor.lock"
flock -n 9
printf '%s\n' "$$" > "${root}/supervisor.pid"

failure_receipt() {
  local rc=$?
  if (( rc != 0 )); then printf '%s\n' "${rc}" > "${root}/FAILED_RC" 2>/dev/null || true; fi
  exit "${rc}"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

lock_is_free() {
  local lock_path=$1
  test -f "${lock_path}" && test ! -L "${lock_path}"
  (
    exec 8< "${lock_path}"
    flock -n -s 8
  )
}

git -C "${repo}" fetch fork phase1-value-critic > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
remote_head=$(git -C "${repo}" rev-parse fork/phase1-value-critic)
git -C "${repo}" cat-file -e "${control_commit}^{commit}"
git -C "${repo}" merge-base --is-ancestor "${control_commit}" "${remote_head}"
for spec in \
  "${public_path}|source_script.sh" \
  "${guard_public_path}|guard_source.sh" \
  "${renewal_public_path}|renewal_source.sh"; do
  path=${spec%%|*}
  output=${spec#*|}
  git -C "${repo}" show "${control_commit}:${path}" > "${root}/${output}"
  bash -n "${root}/${output}"
done
cmp "$0" "${root}/source_script.sh"

cat > "${root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol only; PASS
02_goal=bridge expiring outcome-blind monitor windows without duplicate processes or structural gaps; PASS
03_control_commit=${control_commit}; PASS
04_scope=LATEST PID lock marker exact tail hash filename count and aggregate outcomes_read false summary only; PASS
05_forbidden=no label outcome prediction value accuracy utility sidecar content or raw archive content; PASS
06_order=certify old guard normal completion and v1 read-only-lock failure,launch v4 guard,then renew four support monitors; PASS
07_controls=public exact source old process death shared read-only lock probes exact baseline hashes and child postflight; PASS
08_failure=new snapshot or sidecar hands off without renewal unknown duplicate failure or drift fails closed; PASS
09_randomness=none fixed 60-second supervisor polling bounded by 480 polls; PASS
10_resources=CPU metadata polling only GPU API model-fit base-update 0/0/0/0; PASS
11_resume=no live monitor is restarted and each child has a fresh fixed root; PASS
12_security=config sidecar detection stops at filename count before redaction or review; PASS
13_promotion=child first-poll receipts and immutable supervisor manifest required; PASS
EOF
test "$(wc -l < "${root}/preflight_13.txt")" = 13

test "$(tr -d '\r\n' < "${state}/LATEST")" = "${baseline}"
test "$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)" = 0
test "$(tr -d '\r\n' < "${failed_supervisor}/FAILED_RC")" = 65
test ! -e "${failed_supervisor}/HANDOFF"
test ! -e "${failed_supervisor}/READY"
test ! -e "${failed_supervisor}/COMPLETE"
test "$(sha256sum "${failed_supervisor}/source_script.sh" | awk '{print $1}')" = \
  8febae8ee4397f5f9ec5b0a00da98f1a778acb138fe1d24a00aa41fc19b337e9
test "$(sha256sum "${failed_supervisor}/guard_source.sh" | awk '{print $1}')" = \
  7c67778bebe0c401a0b4b8e137f07f360eb5cae2f2829353f08baf60c7548a12
tail -n 1 "${failed_supervisor}/status.log" \
  | grep -Fq "latest=${baseline} sidecar_count=0 guard_launched=false renewal_launched=false"
lock_is_free "${failed_supervisor}/supervisor.lock"
old_guard_pid=$(tr -d '\r\n' < "${old_guard}/guard.pid")
[[ ${old_guard_pid} =~ ^[0-9]+$ ]]
! kill -0 "${old_guard_pid}" 2>/dev/null
lock_is_free "${old_guard}/guard.lock"
test ! -e "${old_guard}/FAILED_RC"
test -f "${old_guard}/READY"
test -f "${old_guard}/COMPLETE"
(cd "${old_guard}" && sha256sum -c SHA256SUMS > "${root}/old_guard_manifest_check.txt")
grep -Fq 'outcomes_read=false' "${old_guard}/status.log"

guard_launched=false
renewal_launched=false
for poll in $(seq 1 480); do
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  latest=$(tr -d '\r\n' < "${state}/LATEST")
  [[ ${latest} =~ ^[0-9a-f]{64}$ ]]
  sidecar_count=$(find "${source_root}" -xdev -type f -name '*.config_v2.jsonl' -printf '.' | wc -c)
  printf '%s poll=%s latest=%s sidecar_count=%s guard_launched=%s renewal_launched=%s\n' \
    "${now}" "${poll}" "${latest}" "${sidecar_count}" "${guard_launched}" "${renewal_launched}" >> "${root}/status.log"

  if test "${sidecar_count}" != 0; then
    printf 'status=CONFIG_V2_SIDECAR_METADATA_OBSERVED_HANDOFF\nobserved_at_utc=%s\ncount=%s\ncontents_opened=false\n' \
      "${now}" "${sidecar_count}" > "${root}/HANDOFF"
    break
  fi
  if test "${latest}" != "${baseline}"; then
    printf 'status=SUCCESSOR_IDENTITY_OBSERVED_HANDOFF\nobserved_at_utc=%s\nsnapshot_sha256=%s\nprospective_values_read=false\n' \
      "${now}" "${latest}" > "${root}/HANDOFF"
    break
  fi
  for watched in "${old_guard}" "${transition}" "${receipt}" "${config}" "${target}"; do
    test ! -e "${watched}/FAILED_RC"
    test ! -e "${watched}/CONTINUITY_GAP"
  done

  if [[ ${guard_launched} = false && -e ${old_guard}/COMPLETE ]]; then
    ! kill -0 "${old_guard_pid}" 2>/dev/null
    lock_is_free "${old_guard}/guard.lock"
    test ! -e "${old_guard}/FAILED_RC"
    test -f "${old_guard}/READY"
    (cd "${old_guard}" && sha256sum -c SHA256SUMS > "${root}/old_guard_manifest_check.txt")
    nohup env OUTCOME_BLIND_GUARD_CONTROL_COMMIT="${control_commit}" \
      bash "${root}/guard_source.sh" > "${root}/guard.stdout" 2> "${root}/guard.stderr" </dev/null &
    guard_pid=$!
    printf '%s\n' "${guard_pid}" > "${root}/guard.pid"
    for _ in $(seq 1 60); do
      if test -s "${new_guard}/status.log"; then break; fi
      kill -0 "${guard_pid}"
      sleep 2
    done
    test -s "${new_guard}/status.log"
    test "$(tr -d '\r\n' < "${new_guard}/guard.pid")" = "${guard_pid}"
    kill -0 "${guard_pid}"
    if lock_is_free "${new_guard}/guard.lock"; then exit 66; fi
    test ! -s "${root}/guard.stderr"
    test ! -e "${new_guard}/FAILED_RC"
    grep -Fq "latest=${baseline}" "${new_guard}/status.log"
    guard_launched=true
    printf '%s guard_v4_started pid=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${guard_pid}" >> "${root}/status.log"
  fi

  transition_done=false
  receipt_done=false
  config_done=false
  target_done=false
  if tail -n 1 "${transition}/monitor.log" | grep -Fq "monitor_complete prior_snapshot=${baseline}" \
      && lock_is_free "${transition}/monitor.lock"; then transition_done=true; fi
  if tail -n 1 "${receipt}/monitor.log" | grep -Fq "monitor_complete prior=${baseline}" \
      && lock_is_free "${receipt}/monitor.lock"; then receipt_done=true; fi
  if test -f "${config}/COMPLETE" \
      && grep -Fq 'status=NO_CONFIG_V2_SIDECAR_OBSERVED' "${config}/COMPLETE" \
      && grep -Fq 'contents_opened=false' "${config}/COMPLETE" \
      && lock_is_free "${config}/monitor.lock"; then config_done=true; fi
  if tail -n 1 "${target}/monitor.log" | grep -Fq "monitor_complete_without_quiescent_new_snapshot baseline=${baseline} outcomes_read=false" \
      && lock_is_free "${target}/monitor.lock"; then target_done=true; fi

  if [[ ${renewal_launched} = false && ${guard_launched} = true \
        && ${transition_done} = true && ${receipt_done} = true \
        && ${config_done} = true && ${target_done} = true ]]; then
    nohup env OUTCOME_BLIND_RENEWAL_CONTROL_COMMIT="${control_commit}" \
      bash "${root}/renewal_source.sh" > "${root}/renewal.stdout" 2> "${root}/renewal.stderr" </dev/null &
    renewal_pid=$!
    printf '%s\n' "${renewal_pid}" > "${root}/renewal.pid"
    for _ in $(seq 1 180); do
      if test -e "${renewal_root}/COMPLETE" || test -e "${renewal_root}/FAILED_RC"; then break; fi
      kill -0 "${renewal_pid}" 2>/dev/null || true
      sleep 2
    done
    test -e "${renewal_root}/COMPLETE"
    test ! -e "${renewal_root}/FAILED_RC"
    test ! -s "${root}/renewal.stderr"
    (cd "${renewal_root}" && sha256sum -c SHA256SUMS > "${root}/renewal_manifest_check.txt")
    renewal_launched=true
    printf '%s support_v4_started pid=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${renewal_pid}" >> "${root}/status.log"
  fi

  if [[ ${guard_launched} = true && ${renewal_launched} = true ]]; then break; fi
  sleep 60
done

if [[ ! -e ${root}/HANDOFF ]]; then
  test "${guard_launched}" = true
  test "${renewal_launched}" = true
fi
cat > "${root}/READY" <<EOF
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
control_commit=${control_commit}
remote_head_at_start=${remote_head}
supervisor_script_sha256=$(sha256sum "${root}/source_script.sh" | awk '{print $1}')
guard_script_sha256=$(sha256sum "${root}/guard_source.sh" | awk '{print $1}')
renewal_script_sha256=$(sha256sum "${root}/renewal_source.sh" | awk '{print $1}')
guard_launched=${guard_launched}
renewal_launched=${renewal_launched}
prospective_values_read=false
outcomes_read=false
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
