#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

if [[ $# != 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  printf 'usage: %s RELEASE_COMMIT\n' "$0" >&2
  exit 64
fi

readonly RELEASE_COMMIT=$1
readonly PROTOCOL_FREEZE_COMMIT=14a97fb27dc3286b68d22f3b0db871f338694cae
readonly CANDIDATE=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly STATE=/research/d7/spc/yzyang4/prospective_decision_v1
readonly RESULT_ROOT=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly ROOT=${RESULT_ROOT}/target300_schema_v2_attempt_1
readonly ANCHOR=${RESULT_ROOT}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly V1_ROOT=${RESULT_ROOT}/monitor_after_98f2_v1
readonly PREVIOUS_ROOT=${RESULT_ROOT}/ab59a01-98f2cba9ca4b-9f69935923f7
readonly PREVIOUS=${PREVIOUS_ROOT}/producer_a
readonly PREVIOUS_MANIFEST_SHA=81831f68055cef1fcae654b8adad3d71c8bf2893a57ef4ba0785e2c2b475cb2e
readonly PREVIOUS_SUMMARY_SHA=01d67cec48537c28183eac8777ab2cf0b19c118ed637318dd5d959c69b9a8b42
readonly PREVIOUS_VERIFICATION_SHA=59624c596eb8d48a52540182c6632b89f90fdc71ad661b8a38d93a355e12ee12
readonly AMENDMENT=${ROOT}/target300_provenance_schema_amendment_v2.json
readonly AMENDMENT_SHA=ef6de30a9ba3cf9b2f893523765baa08b4fcf1c6f87ee4539e4ef594eb2d6df1
readonly FAILURE_RECEIPT=${ROOT}/target300_v1_schema_failure_safe_receipt_20260831.json
readonly FAILURE_RECEIPT_SHA=aef8d5a8a013610f0276b0fc96480e238133e15f28d14f256f47aabb00f5da42
readonly BASE_RUNNER=${ROOT}/run_score_channel_future_cohort_20260823.sh
readonly BASE_RUNNER_SHA=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly PATCHED_RUNNER=${ROOT}/run_score_channel_future_cohort_schema_v2_20260831.sh
readonly PATCHED_RUNNER_SHA=0f50c1dc8d0742b688a14a4c000d66cfa4e1bf95ccb90bdf4a2135221d5edbff

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
test -d "${V1_ROOT}" && test ! -L "${V1_ROOT}"
test "$(tr -d '\r\n' <"${V1_ROOT}/FAILED_RC")" = 2
test ! -e "${V1_ROOT}/COMPLETE"
test ! -e "${ANCHOR}"
test -d "${PREVIOUS_ROOT}" && test ! -L "${PREVIOUS_ROOT}"
test -d "${PREVIOUS}" && test ! -L "${PREVIOUS}"
test "$(sha256sum "${PREVIOUS_ROOT}/SHA256SUMS" | awk '{print $1}')" = "${PREVIOUS_MANIFEST_SHA}"
test "$(sha256sum "${PREVIOUS}/summary.json" | awk '{print $1}')" = "${PREVIOUS_SUMMARY_SHA}"
test "$(sha256sum "${PREVIOUS_ROOT}/verification_a.json" | awk '{print $1}')" = "${PREVIOUS_VERIFICATION_SHA}"
test -z "$(find "${PREVIOUS_ROOT}" -perm /022 -print -quit)"
test "$(tr -d '\r\n' <"${STATE}/LATEST")" = "${CANDIDATE}"
test "$(tr -d '\r\n' <"${ROOT}/release_commit.txt")" = "${RELEASE_COMMIT}"
test "$(tr -d '\r\n' <"${ROOT}/protocol_freeze_commit.txt")" = "${PROTOCOL_FREEZE_COMMIT}"
test -f "${AMENDMENT}" && test ! -L "${AMENDMENT}"
test -f "${FAILURE_RECEIPT}" && test ! -L "${FAILURE_RECEIPT}"
test -x "${BASE_RUNNER}" && test ! -L "${BASE_RUNNER}"
test "$(sha256sum "${AMENDMENT}" | awk '{print $1}')" = "${AMENDMENT_SHA}"
test "$(sha256sum "${FAILURE_RECEIPT}" | awk '{print $1}')" = "${FAILURE_RECEIPT_SHA}"
test "$(sha256sum "${BASE_RUNNER}" | awk '{print $1}')" = "${BASE_RUNNER_SHA}"

/research/d7/spc/yzyang4/venvs/exp/bin/python - "${AMENDMENT}" "${FAILURE_RECEIPT}" "${CANDIDATE}" <<'PY'
import json
import pathlib
import sys
amendment = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
failure = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
candidate = sys.argv[3]
assert amendment["status"] == "FROZEN_AFTER_V1_STRUCTURAL_FAILURE_BEFORE_SCIENTIFIC_READOUT"
assert amendment["fixed_candidate"]["latest_snapshot_sha256"] == candidate
assert amendment["fixed_candidate"]["alternate_snapshot_selection_allowed"] is False
assert amendment["failure_binding"]["v1_must_not_be_retried"] is True
assert amendment["schema_amendment"]["sole_optional_key"] == "competition_id_source"
assert amendment["schema_amendment"]["allowed_optional_values"] == [
    "archive_consensus_fallback", "explicit_journal"
]
assert amendment["scope"]["gpu_jobs_authorized"] == 0
assert amendment["scope"]["paid_api_calls_authorized"] == 0
assert amendment["scope"]["model_fits_authorized"] == 0
assert failure["status"] == "TARGET300_V1_SCHEMA_DRIFT_FAIL_CLOSED"
assert failure["v1_execution"]["formal_rc"] == 2
assert failure["v1_execution"]["v1_retry_permitted"] is False
assert failure["key_only_schema_audit"]["legacy_exact_rows"] == 495
assert failure["key_only_schema_audit"]["optional_source_rows"] == 25
assert all(value is False for value in failure["blindness"].values())
PY

exec 9>"${ROOT}/attempt.lock"
flock -n 9
test ! -e "${ROOT}/COMPLETE"
test ! -e "${ROOT}/FAILED_RC"
test ! -e "${PATCHED_RUNNER}"

cp "${BASE_RUNNER}" "${PATCHED_RUNNER}"
sed -i \
  's|^worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_${short}_nosmudge$|worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_${short}_schema_v2_30945550_nosmudge|' \
  "${PATCHED_RUNNER}"
sed -i \
  '/^latest_before=/a test "${latest_before}" = 30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f' \
  "${PATCHED_RUNNER}"
chmod 0500 "${PATCHED_RUNNER}"
bash -n "${PATCHED_RUNNER}"
test "$(sha256sum "${PATCHED_RUNNER}" | awk '{print $1}')" = "${PATCHED_RUNNER_SHA}"

cat >"${ROOT}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark; Target-300 structural identity closure only; PASS
02_question=can the v1-fixed candidate close after only the frozen provenance schema amendment; PASS
03_context=v1 rc2 retained, same candidate ${CANDIDATE}, previous 193-run exact prefix; PASS
04_unit=whole accepted archive then unique physical run in unchanged temporal order; PASS
05_schema=required 12 keys plus sole optional competition_id_source with fixed two-value enum; PASS
06_controls=legacy compatibility, mixed-schema positive, producer/verifier invalid-value negatives; PASS
07_repetitions=producer A/B and independent verifier A/B byte equality; PASS
08_independence=verifier independently parses provenance and rejects invalid optional value; PASS
09_reproducibility=exact release, amendment, failure receipt, runner hashes, clean worktree and tests; PASS
10_statistics=identity closure only; no labels, effect, accuracy, utility or truth support; PASS
11_resources=single-thread CPU; gpu api model-fit base-update 0/0/0/0; PASS
12_candidate=no caller snapshot, no alternate candidate, exact ${CANDIDATE}; PASS
13_failure=v2 failure retained without retry; anchor absent before attempt; PASS
EOF
test "$(wc -l <"${ROOT}/preflight_13.txt")" = 13
printf '%s schema_v2_start candidate=%s previous_runs=193 outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${CANDIDATE}" >>"${ROOT}/attempt.log"

set +e
bash "${PATCHED_RUNNER}" "${RELEASE_COMMIT}" "${PREVIOUS}" \
  >"${ROOT}/formal.private.stdout" 2>"${ROOT}/formal.stderr"
rc=$?
set -e
printf '%s schema_v2_finished candidate=%s rc=%s outcomes_read=false identities_read=false\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${CANDIDATE}" "${rc}" >>"${ROOT}/attempt.log"
printf '%s\n' "${rc}" >"${ROOT}/formal_rc.txt"
if (( rc != 0 )); then
  exit "${rc}"
fi
printf 'TARGET300_SCHEMA_V2_FORMAL_COMPLETE\n' >"${ROOT}/COMPLETE"
trap - EXIT
