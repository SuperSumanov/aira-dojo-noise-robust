#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly SCIENCE_COMMIT=ab59a011d945e4a96daf7dbbbc927a59027da077
readonly SCIENCE_PROTOCOL_SHA=54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d
readonly CONTINUATION_PROTOCOL_SHA=3a9027792d9d0b6a5466788007b363a9472b62f26409f2fc13eff88987670f97
readonly BASE_LATEST=98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa
readonly STATE=/research/d7/spc/yzyang4/prospective_decision_v1
readonly RESULT_ROOT=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly PREVIOUS_ROOT=${RESULT_ROOT}/ab59a01-98f2cba9ca4b-9f69935923f7
readonly PREVIOUS=${PREVIOUS_ROOT}/producer_a
readonly PREVIOUS_MANIFEST_SHA=81831f68055cef1fcae654b8adad3d71c8bf2893a57ef4ba0785e2c2b475cb2e
readonly PREVIOUS_SUMMARY_SHA=01d67cec48537c28183eac8777ab2cf0b19c118ed637318dd5d959c69b9a8b42
readonly PREVIOUS_VERIFICATION_SHA=59624c596eb8d48a52540182c6632b89f90fdc71ad661b8a38d93a355e12ee12
readonly ROOT=${RESULT_ROOT}/monitor_after_98f2_v1
readonly RUNNER_TEMPLATE=${ROOT}/run_score_channel_future_cohort_20260823.sh
readonly RUNNER_SHA=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly PROTOCOL=${ROOT}/target300_continuation_after_98f2_v1.json
readonly ANCHOR=${RESULT_ROOT}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly POLL_SECONDS=300
readonly STABLE_POLLS=5
readonly MAX_POLLS=144

fail_closed() {
  local rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" >"${ROOT}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap fail_closed EXIT

test -d "${STATE}" && test ! -L "${STATE}"
test -d "${ROOT}" && test ! -L "${ROOT}"
test -d "${PREVIOUS_ROOT}" && test ! -L "${PREVIOUS_ROOT}"
test -d "${PREVIOUS}" && test ! -L "${PREVIOUS}"
test -x "${RUNNER_TEMPLATE}" && test ! -L "${RUNNER_TEMPLATE}"
test -f "${PROTOCOL}" && test ! -L "${PROTOCOL}"
test "$(sha256sum "${RUNNER_TEMPLATE}" | awk '{print $1}')" = "${RUNNER_SHA}"
test "$(sha256sum "${PROTOCOL}" | awk '{print $1}')" = "${CONTINUATION_PROTOCOL_SHA}"
test "$(sha256sum "${PREVIOUS_ROOT}/SHA256SUMS" | awk '{print $1}')" = "${PREVIOUS_MANIFEST_SHA}"
test "$(sha256sum "${PREVIOUS}/summary.json" | awk '{print $1}')" = "${PREVIOUS_SUMMARY_SHA}"
test "$(sha256sum "${PREVIOUS_ROOT}/verification_a.json" | awk '{print $1}')" = "${PREVIOUS_VERIFICATION_SHA}"
test -f "${PREVIOUS_ROOT}/COMPLETE"
test -z "$(find "${PREVIOUS_ROOT}" -perm /022 -print -quit)"
test ! -e "${ANCHOR}"
test "$(tr -d '\r\n' <"${ROOT}/science_commit.txt")" = "${SCIENCE_COMMIT}"
test "$(tr -d '\r\n' <"${ROOT}/science_protocol_sha256.txt")" = "${SCIENCE_PROTOCOL_SHA}"
test "$(tr -d '\r\n' <"${ROOT}/continuation_protocol_sha256.txt")" = "${CONTINUATION_PROTOCOL_SHA}"

python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
"${python_bin}" - "${PREVIOUS}/summary.json" "${PREVIOUS_ROOT}/verification_a.json" <<'PY'
import json
import pathlib
import sys
summary = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
receipt = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
assert summary["status"] == "FUTURE_COHORT_COLLECTING"
assert summary["inventory"]["selected_physical_runs"] == 193
assert summary["inventory"]["selected_archives"] == 60
assert summary["inventory"]["selected_tasks"] == 30
assert summary["closure"]["remaining_runs_to_target"] == 107
assert summary["closure"]["boundary_archive"] is None
assert summary["blindness"]["label_vault_opened"] is False
assert summary["blindness"]["score_or_outcome_opened"] is False
assert summary["blindness"]["truth_support_computed"] is False
assert receipt["status"] == "PASS_COLLECTING_TRUTH_UNREAD"
assert receipt["label_vault_opened"] is False
assert receipt["score_or_outcome_opened"] is False
PY

exec 9>"${ROOT}/monitor.lock"
flock -n 9

cat >"${ROOT}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark; Target-300 identity closure only; PASS
02_question=does the frozen cohort close on the first stable successor observed after continuation deployment; PASS
03_context=base 98f2 plus independently verified 193-run and 60-archive exact prefix; PASS
04_unit=whole accepted archive then unique physical run in frozen temporal order; PASS
05_security=LATEST before trigger; fixed metadata-only runner after trigger; identities private and values forbidden; PASS
06_controls=exact previous prefix plus target 300 and complete boundary-archive overshoot; PASS
07_repetitions=producer A/B and independent verifier A/B byte equality; PASS
08_independence=existing verifier does not import producer and reconstructs closure; PASS
09_reproducibility=fixed science commit protocol runner hashes clean worktree tests traces and manifest; PASS
10_statistics=identity closure only; no effect estimate significance test or truth-support claim; PASS
11_resources=single-thread CPU; gpu api model-fit base-update 0/0/0/0; PASS
12_trigger=${STABLE_POLLS} stable polls x ${POLL_SECONDS}s; candidate change resets; no caller snapshot; PASS
13_failure=prefix hash candidate runner verifier secret or forbidden-open drift fails once without retry; PASS
EOF
test "$(wc -l <"${ROOT}/preflight_13.txt")" = 13

printf '%s monitor_start base=%s previous_runs=193 stable_polls=%s interval=%s outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${BASE_LATEST}" "${STABLE_POLLS}" "${POLL_SECONDS}" \
  >>"${ROOT}/monitor.log"

candidate=''
stable_count=0
for poll in $(seq 1 "${MAX_POLLS}"); do
  test ! -e "${ANCHOR}"
  current=$(tr -d '\r\n' <"${STATE}/LATEST")
  [[ ${current} =~ ^[0-9a-f]{64}$ ]]
  if [[ ${current} == "${BASE_LATEST}" ]]; then
    candidate=''
    stable_count=0
    printf '%s no_change poll=%s snapshot=%s outcomes_read=false identities_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current}" >>"${ROOT}/monitor.log"
  else
    if [[ ${current} == "${candidate}" ]]; then
      stable_count=$((stable_count + 1))
    else
      candidate=${current}
      stable_count=1
    fi
    printf '%s candidate poll=%s snapshot=%s stable_count=%s/%s outcomes_read=false identities_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current}" "${stable_count}" "${STABLE_POLLS}" \
      >>"${ROOT}/monitor.log"
    if (( stable_count >= STABLE_POLLS )); then
      prefix=${candidate:0:12}
      patched=${ROOT}/run_score_channel_future_cohort_${prefix}.sh
      diff_path=${ROOT}/runner_worktree_path_${prefix}.diff
      test ! -e "${patched}"
      test ! -e "${diff_path}"
      cp "${RUNNER_TEMPLATE}" "${patched}"
      sed -i \
        "s|^worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_\${short}_nosmudge$|worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_\${short}_${prefix}_nosmudge|" \
        "${patched}"
      chmod 0500 "${patched}"
      bash -n "${patched}"
      set +e
      diff -u "${RUNNER_TEMPLATE}" "${patched}" >"${diff_path}"
      diff_rc=$?
      set -e
      test "${diff_rc}" = 1
      test "$(grep -c '^@@' "${diff_path}")" = 1
      test "$(grep -c '^[-+]worktree=' "${diff_path}")" = 2
      test "$(grep -Ec '^[+-][^+-]' "${diff_path}")" = 2
      sha256sum "${RUNNER_TEMPLATE}" "${patched}" "${diff_path}" \
        >"${ROOT}/runner_bindings_${prefix}.sha256"
      printf '%s quiescent_trigger poll=%s snapshot=%s outcomes_read=false identities_read=false\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current}" >>"${ROOT}/monitor.log"
      set +e
      bash "${patched}" "${SCIENCE_COMMIT}" "${PREVIOUS}" \
        >"${ROOT}/formal.private.stdout" 2>"${ROOT}/formal.stderr"
      rc=$?
      set -e
      printf '%s formal_finished poll=%s snapshot=%s rc=%s outcomes_read=false identities_read=false\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${current}" "${rc}" \
        >>"${ROOT}/monitor.log"
      printf '%s\n' "${rc}" >"${ROOT}/formal_rc.txt"
      if (( rc == 0 )); then
        printf 'TARGET300_CONTINUATION_FORMAL_COMPLETE\n' >"${ROOT}/COMPLETE"
        trap - EXIT
        exit 0
      fi
      exit "${rc}"
    fi
  fi
  if (( poll < MAX_POLLS )); then
    sleep "${POLL_SECONDS}"
  fi
done

printf '124\n' >"${ROOT}/TIMEOUT_RC"
printf '%s monitor_timeout base=%s outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${BASE_LATEST}" >>"${ROOT}/monitor.log"
trap - EXIT
