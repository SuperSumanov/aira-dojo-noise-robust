#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly SCIENCE_COMMIT=4a68c83fba90655e9d60344081ae2b53b7c36104
readonly SCIENCE_PROTOCOL_SHA=54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d
readonly CHAIN_PROTOCOL_SHA=8a499b626c5e88549af6d9e797c36cef7f02e4461d7a3c2c9c66c3c6ccfa6a23
readonly BASE_RUNNER_SHA=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly INITIAL_BASE=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly INITIAL_PREVIOUS_ROOT=/research/d7/spc/yzyang4/score-channel-future-identity-cohort/4a68c83-30945550b6b1-8e42f764cc05
readonly INITIAL_MANIFEST_SHA=f05446579f8d808a7b37ad78566a0339a7999a9d70e1b2fec5388bce9b8fcbdc
readonly INITIAL_SUMMARY_SHA=6a9301af50fd8d471ffb40b55e59dee4dec987f73c94f0eccbbe6c803dd42428
readonly INITIAL_VERIFICATION_SHA=5d3dec87aaab9e38f03fab7c89f05c390e54d091b004bf41cc7e3db69dcd785a
readonly STATE=/research/d7/spc/yzyang4/prospective_decision_v1
readonly RESULT_ROOT=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly ROOT=${RESULT_ROOT}/target300_continuous_schema_v2_v1
readonly ANCHOR=${RESULT_ROOT}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly PROTOCOL=${ROOT}/target300_continuous_schema_v2_continuation_v1.json
readonly BASE_RUNNER=${ROOT}/run_score_channel_future_cohort_20260823.sh
readonly POLL_SECONDS=300
readonly STABLE_POLLS=5
readonly MAX_POLLS=2016

fail_closed() {
  local rc=$?
  if (( rc != 0 )) && [[ ! -e "${ROOT}/FAILED_RC" ]]; then
    printf '%s\n' "${rc}" >"${ROOT}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap fail_closed EXIT

test -d "${ROOT}" && test ! -L "${ROOT}"
test -d "${STATE}" && test ! -L "${STATE}"
test ! -e "${ANCHOR}"
test -f "${PROTOCOL}" && test ! -L "${PROTOCOL}"
test -x "${BASE_RUNNER}" && test ! -L "${BASE_RUNNER}"
test "$(sha256sum "${PROTOCOL}" | awk '{print $1}')" = "${CHAIN_PROTOCOL_SHA}"
test "$(sha256sum "${BASE_RUNNER}" | awk '{print $1}')" = "${BASE_RUNNER_SHA}"
test "$(tr -d '\r\n' <"${ROOT}/science_commit.txt")" = "${SCIENCE_COMMIT}"
test "$(tr -d '\r\n' <"${ROOT}/chain_protocol_sha256.txt")" = "${CHAIN_PROTOCOL_SHA}"
test -d "${INITIAL_PREVIOUS_ROOT}" && test ! -L "${INITIAL_PREVIOUS_ROOT}"
test "$(sha256sum "${INITIAL_PREVIOUS_ROOT}/SHA256SUMS" | awk '{print $1}')" = "${INITIAL_MANIFEST_SHA}"
test "$(sha256sum "${INITIAL_PREVIOUS_ROOT}/producer_a/summary.json" | awk '{print $1}')" = "${INITIAL_SUMMARY_SHA}"
test "$(sha256sum "${INITIAL_PREVIOUS_ROOT}/verification_a.json" | awk '{print $1}')" = "${INITIAL_VERIFICATION_SHA}"
test -z "$(find "${INITIAL_PREVIOUS_ROOT}" -perm /022 -print -quit)"
test "$(tr -d '\r\n' <"${STATE}/LATEST")" = "${INITIAL_BASE}"

/research/d7/spc/yzyang4/venvs/exp/bin/python - \
  "${PROTOCOL}" "${INITIAL_PREVIOUS_ROOT}/producer_a/summary.json" \
  "${INITIAL_PREVIOUS_ROOT}/verification_a.json" <<'PY'
import json
import pathlib
import sys
protocol = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
summary = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
verification = json.loads(pathlib.Path(sys.argv[3]).read_text(encoding="utf-8"))
assert protocol["status"] == "FROZEN_BEFORE_ANY_POST_309_SUCCESSOR"
assert protocol["successor_rule"]["alternate_candidate_selection_allowed"] is False
assert protocol["chain_rule"]["formal_failure_stops_entire_chain"] is True
assert summary["status"] == "FUTURE_COHORT_COLLECTING"
assert summary["inventory"]["selected_physical_runs"] == 219
assert summary["inventory"]["selected_archives"] == 69
assert summary["closure"]["remaining_runs_to_target"] == 81
assert verification["status"] == "PASS_COLLECTING_TRUTH_UNREAD"
for value in (summary["blindness"], verification):
    assert value["label_vault_opened"] is False
    assert value["score_or_outcome_opened"] is False
    assert value["truth_support_computed"] is False
PY

exec 9>"${ROOT}/monitor.lock"
flock -n 9
cat >"${ROOT}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark; Target-300 identity closure only; PASS
02_question=does ordered first-stable-successor chaining close the fixed temporal cohort; PASS
03_context=base 30945550 and verified 219-run 69-archive exact prefix; PASS
04_unit=whole accepted archive then unique physical run in unchanged temporal order; PASS
05_candidate=first non-base LATEST stable 5x300s, caller cannot choose snapshot; PASS
06_chain=each collecting formal becomes the next exact previous prefix; PASS
07_repetitions=producer A/B and independent verifier A/B byte equality per candidate; PASS
08_independence=existing verifier reconstructs provenance, order, prefix and boundary; PASS
09_reproducibility=fixed science commit/protocol/runner, tests, traces, hashes and read-only manifest; PASS
10_statistics=identity closure only; no effect estimate, truth support, accuracy or utility; PASS
11_resources=single-thread CPU; gpu api model-fit base-update 0/0/0/0; PASS
12_security=no candidate identities/profile/private selection or outcomes in public monitor log; PASS
13_failure=any drift or formal failure stops the chain without retry or alternate candidate; PASS
EOF
test "$(wc -l <"${ROOT}/preflight_13.txt")" = 13

base=${INITIAL_BASE}
previous_root=${INITIAL_PREVIOUS_ROOT}
previous=${previous_root}/producer_a
candidate=''
stable_count=0
attempt=1
printf '%s chain_start base=%s previous_runs=219 outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${base}" >>"${ROOT}/monitor.log"

for poll in $(seq 1 "${MAX_POLLS}"); do
  test ! -e "${ANCHOR}"
  current=$(tr -d '\r\n' <"${STATE}/LATEST")
  [[ ${current} =~ ^[0-9a-f]{64}$ ]]
  if [[ ${current} == "${base}" ]]; then
    candidate=''
    stable_count=0
    printf '%s no_change poll=%s base=%s attempt=%s outcomes_read=false identities_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${base}" "${attempt}" >>"${ROOT}/monitor.log"
  else
    if [[ ${current} == "${candidate}" ]]; then
      stable_count=$((stable_count + 1))
    else
      candidate=${current}
      stable_count=1
    fi
    printf '%s candidate poll=%s snapshot=%s stable_count=%s/%s attempt=%s outcomes_read=false identities_read=false\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${candidate}" "${stable_count}" "${STABLE_POLLS}" "${attempt}" \
      >>"${ROOT}/monitor.log"
    if (( stable_count >= STABLE_POLLS )); then
      prefix=${candidate:0:12}
      patched=${ROOT}/runner_attempt_${attempt}_${prefix}.sh
      diff_path=${ROOT}/runner_attempt_${attempt}_${prefix}.diff
      test ! -e "${patched}" && test ! -e "${diff_path}"
      cp "${BASE_RUNNER}" "${patched}"
      sed -i \
        "s|^worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_\${short}_nosmudge$|worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_\${short}_${prefix}_schema_v2_chain_${attempt}_nosmudge|" \
        "${patched}"
      sed -i "/^latest_before=/a test \"\${latest_before}\" = ${candidate}" "${patched}"
      chmod 0500 "${patched}"
      bash -n "${patched}"
      set +e
      diff -u "${BASE_RUNNER}" "${patched}" >"${diff_path}"
      diff_rc=$?
      set -e
      test "${diff_rc}" = 1
      test "$(grep -c '^@@' "${diff_path}")" = 2
      test "$(grep -c '^[-+]worktree=' "${diff_path}")" = 2
      test "$(grep -c '^+test "${latest_before}" = ' "${diff_path}")" = 1
      test "$(tr -d '\r\n' <"${STATE}/LATEST")" = "${candidate}"
      printf '%s formal_start poll=%s snapshot=%s attempt=%s outcomes_read=false identities_read=false\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${poll}" "${candidate}" "${attempt}" >>"${ROOT}/monitor.log"
      set +e
      bash "${patched}" "${SCIENCE_COMMIT}" "${previous}" \
        >"${ROOT}/attempt_${attempt}.private.stdout" 2>"${ROOT}/attempt_${attempt}.stderr"
      rc=$?
      set -e
      printf '%s formal_end snapshot=%s attempt=%s rc=%s outcomes_read=false identities_read=false\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${candidate}" "${attempt}" "${rc}" >>"${ROOT}/monitor.log"
      printf '%s\n' "${rc}" >"${ROOT}/attempt_${attempt}.rc"
      if (( rc != 0 )); then
        exit "${rc}"
      fi
      mapfile -t formal_roots < <(find "${RESULT_ROOT}" -mindepth 1 -maxdepth 1 -type d \
        -name "4a68c83-${prefix}-*" -print | LC_ALL=C sort)
      test "${#formal_roots[@]}" = 1
      formal=${formal_roots[0]}
      test -f "${formal}/COMPLETE"
      test -z "$(find "${formal}" -perm /022 -print -quit)"
      (cd "${formal}" && sha256sum -c SHA256SUMS >/dev/null)
      /research/d7/spc/yzyang4/venvs/exp/bin/python - \
        "${formal}/producer_a/summary.json" "${formal}/verification_a.json" \
        "${candidate}" "${previous}/summary.json" "${ROOT}/attempt_${attempt}.safe_receipt" <<'PY'
import hashlib
import json
import pathlib
import sys
summary_path, verification_path, candidate, previous_summary_path, receipt_path = sys.argv[1:]
summary_path = pathlib.Path(summary_path)
verification_path = pathlib.Path(verification_path)
summary = json.loads(summary_path.read_text(encoding="utf-8"))
verification = json.loads(verification_path.read_text(encoding="utf-8"))
previous_summary = json.loads(pathlib.Path(previous_summary_path).read_text(encoding="utf-8"))
assert summary["inputs"]["latest_sha256"] == candidate
assert summary["status"] in {"FUTURE_COHORT_COLLECTING", "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD"}
previous = summary["closure"]["append_only_previous"]
assert previous["previous_summary_sha256"] == hashlib.sha256(pathlib.Path(previous_summary_path).read_bytes()).hexdigest()
assert previous["previous_runs"] == previous_summary["inventory"]["selected_physical_runs"]
assert previous["previous_archives"] == previous_summary["inventory"]["selected_archives"]
assert previous["exact_prefix_survived"] is True
assert verification["selected_physical_runs"] == summary["inventory"]["selected_physical_runs"]
assert verification["selected_archives"] == summary["inventory"]["selected_archives"]
for value in (summary["blindness"], verification):
    assert value["label_vault_opened"] is False
    assert value["score_or_outcome_opened"] is False
    assert value["truth_support_computed"] is False
safe = {
    "status": summary["status"],
    "verifier_status": verification["status"],
    "selected_runs": summary["inventory"]["selected_physical_runs"],
    "selected_archives": summary["inventory"]["selected_archives"],
    "selected_tasks": summary["inventory"]["selected_tasks"],
    "remaining_runs": summary["closure"]["remaining_runs_to_target"],
    "boundary_present": summary["closure"]["boundary_archive"] is not None,
    "previous_runs": previous["previous_runs"],
    "exact_prefix_survived": True,
    "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
    "verification_sha256": hashlib.sha256(verification_path.read_bytes()).hexdigest(),
    "outcomes_read": False,
    "identities_read": False,
}
pathlib.Path(receipt_path).write_text(json.dumps(safe, sort_keys=True) + "\n", encoding="utf-8")
PY
      status=$(/research/d7/spc/yzyang4/venvs/exp/bin/python -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' \
        "${ROOT}/attempt_${attempt}.safe_receipt")
      sha256sum "${patched}" "${diff_path}" "${ROOT}/attempt_${attempt}.safe_receipt" \
        >"${ROOT}/attempt_${attempt}.sha256"
      if [[ ${status} == FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD ]]; then
        test -f "${ANCHOR}" && test ! -L "${ANCHOR}"
        printf 'TARGET300_CONTINUOUS_SCHEMA_V2_CLOSED\n' >"${ROOT}/COMPLETE"
        trap - EXIT
        exit 0
      fi
      test "${status}" = FUTURE_COHORT_COLLECTING
      test ! -e "${ANCHOR}"
      previous_root=${formal}
      previous=${formal}/producer_a
      base=${candidate}
      candidate=''
      stable_count=0
      attempt=$((attempt + 1))
      printf '%s chain_advanced new_base=%s next_attempt=%s outcomes_read=false identities_read=false\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${base}" "${attempt}" >>"${ROOT}/monitor.log"
    fi
  fi
  if (( poll < MAX_POLLS )); then sleep "${POLL_SECONDS}"; fi
done

printf '124\n' >"${ROOT}/TIMEOUT_RC"
printf '%s chain_timeout base=%s attempts=%s outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${base}" "$((attempt - 1))" >>"${ROOT}/monitor.log"
trap - EXIT
