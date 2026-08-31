#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

if [[ $# != 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  printf 'usage: %s RELEASE_COMMIT\n' "$0" >&2
  exit 64
fi

readonly release_commit=$1
readonly protocol_freeze_commit=14a97fb27dc3286b68d22f3b0db871f338694cae
readonly candidate=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly base_repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly result_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly root=${result_root}/target300_schema_v2_attempt_1
readonly anchor=${result_root}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly v1_root=${result_root}/monitor_after_98f2_v1
readonly previous_root=${result_root}/ab59a01-98f2cba9ca4b-9f69935923f7
readonly previous_manifest_sha=81831f68055cef1fcae654b8adad3d71c8bf2893a57ef4ba0785e2c2b475cb2e
readonly previous_summary_sha=01d67cec48537c28183eac8777ab2cf0b19c118ed637318dd5d959c69b9a8b42
readonly previous_verification_sha=59624c596eb8d48a52540182c6632b89f90fdc71ad661b8a38d93a355e12ee12
readonly wrapper_path=phase1/scripts/run_target300_schema_v2_once_20260831.sh
readonly wrapper_sha=1674743050c7d333476c6a88b3627f869a2bcbde9b9318641298d530e39761c5
readonly base_runner_path=phase1/scripts/run_score_channel_future_cohort_20260823.sh
readonly base_runner_sha=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly amendment_path=phase1/target300_provenance_schema_amendment_v2.json
readonly amendment_sha=ef6de30a9ba3cf9b2f893523765baa08b4fcf1c6f87ee4539e4ef594eb2d6df1
readonly failure_path=phase1/target300_v1_schema_failure_safe_receipt_20260831.json
readonly failure_sha=aef8d5a8a013610f0276b0fc96480e238133e15f28d14f256f47aabb00f5da42

trap 'rc=$?; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT

test ! -e "${root}"
test ! -e "${anchor}"
test -d "${v1_root}" && test ! -L "${v1_root}"
test "$(tr -d '\r\n' <"${v1_root}/FAILED_RC")" = 2
test ! -e "${v1_root}/COMPLETE"
(exec 8<"${v1_root}/monitor.lock"; flock -n -s 8)
test -d "${previous_root}" && test ! -L "${previous_root}"
test "$(sha256sum "${previous_root}/SHA256SUMS" | awk '{print $1}')" = "${previous_manifest_sha}"
(cd "${previous_root}" && sha256sum -c SHA256SUMS >/dev/null)
test "$(sha256sum "${previous_root}/producer_a/summary.json" | awk '{print $1}')" = "${previous_summary_sha}"
test "$(sha256sum "${previous_root}/verification_a.json" | awk '{print $1}')" = "${previous_verification_sha}"
test -z "$(find "${previous_root}" -perm /022 -print -quit)"
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${candidate}"

git -C "${base_repo}" fetch fork phase1-value-critic >/tmp/target300_schema_v2_fetch.stdout 2>/tmp/target300_schema_v2_fetch.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"
git -C "${base_repo}" merge-base --is-ancestor "${protocol_freeze_commit}" "${release_commit}"

wrapper_tmp=$(mktemp /tmp/target300-schema-v2-wrapper.XXXXXX)
runner_tmp=$(mktemp /tmp/target300-schema-v2-runner.XXXXXX)
amendment_tmp=$(mktemp /tmp/target300-schema-v2-amendment.XXXXXX)
failure_tmp=$(mktemp /tmp/target300-schema-v2-failure.XXXXXX)
cleanup_tmp() {
  rm -f "${wrapper_tmp}" "${runner_tmp}" "${amendment_tmp}" "${failure_tmp}"
}
trap 'rc=$?; cleanup_tmp; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
git -C "${base_repo}" show "${release_commit}:${wrapper_path}" >"${wrapper_tmp}"
git -C "${base_repo}" show "${release_commit}:${base_runner_path}" >"${runner_tmp}"
git -C "${base_repo}" show "${release_commit}:${amendment_path}" >"${amendment_tmp}"
git -C "${base_repo}" show "${release_commit}:${failure_path}" >"${failure_tmp}"
test "$(sha256sum "${wrapper_tmp}" | awk '{print $1}')" = "${wrapper_sha}"
test "$(sha256sum "${runner_tmp}" | awk '{print $1}')" = "${base_runner_sha}"
test "$(sha256sum "${amendment_tmp}" | awk '{print $1}')" = "${amendment_sha}"
test "$(sha256sum "${failure_tmp}" | awk '{print $1}')" = "${failure_sha}"
bash -n "${wrapper_tmp}"
bash -n "${runner_tmp}"

mkdir "${root}"
chmod 0700 "${root}"
install -m 0500 "${wrapper_tmp}" "${root}/run_target300_schema_v2_once_20260831.sh"
install -m 0500 "${runner_tmp}" "${root}/run_score_channel_future_cohort_20260823.sh"
install -m 0400 "${amendment_tmp}" "${root}/target300_provenance_schema_amendment_v2.json"
install -m 0400 "${failure_tmp}" "${root}/target300_v1_schema_failure_safe_receipt_20260831.json"
printf '%s\n' "${release_commit}" >"${root}/release_commit.txt"
printf '%s\n' "${protocol_freeze_commit}" >"${root}/protocol_freeze_commit.txt"
cp /tmp/target300_schema_v2_fetch.stdout "${root}/fetch.stdout"
cp /tmp/target300_schema_v2_fetch.stderr "${root}/fetch.stderr"
cleanup_tmp

nohup bash "${root}/run_target300_schema_v2_once_20260831.sh" "${release_commit}" \
  >"${root}/launcher.stdout" 2>"${root}/launcher.stderr" </dev/null &
pid=$!
printf '%s\n' "${pid}" >"${root}/launcher.pid"
sleep 4
kill -0 "${pid}"
test ! -e "${root}/FAILED_RC"
test ! -e "${root}/DEPLOY_FAILED_RC"
test ! -s "${root}/launcher.stderr"
tr '\0' ' ' <"/proc/${pid}/cmdline" | grep -Fq "${root}/run_target300_schema_v2_once_20260831.sh"
grep -Fq "schema_v2_start candidate=${candidate} previous_runs=193 outcomes_read=false identities_read=false" "${root}/attempt.log"
if (exec 8<"${root}/attempt.lock"; flock -n -s 8); then
  printf 'schema v2 attempt lock is not held\n' >&2
  exit 1
fi

cat >"${root}/deployment_receipt.txt" <<EOF
deployed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=TARGET300_SCHEMA_V2_ATTEMPT_LIVE
pid=${pid}
release_commit=${release_commit}
protocol_freeze_commit=${protocol_freeze_commit}
fixed_candidate=${candidate}
previous_runs=193
previous_archives=60
previous_manifest_sha256=${previous_manifest_sha}
previous_summary_sha256=${previous_summary_sha}
previous_verification_sha256=${previous_verification_sha}
wrapper_sha256=${wrapper_sha}
base_runner_sha256=${base_runner_sha}
amendment_sha256=${amendment_sha}
failure_receipt_sha256=${failure_sha}
v1_retry=false
alternate_candidate=false
candidate_identities_read=false
outcomes_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
sha256sum \
  "${root}/run_target300_schema_v2_once_20260831.sh" \
  "${root}/run_score_channel_future_cohort_20260823.sh" \
  "${root}/target300_provenance_schema_amendment_v2.json" \
  "${root}/target300_v1_schema_failure_safe_receipt_20260831.json" \
  "${root}/deployment_receipt.txt" >"${root}/DEPLOY_STATIC_SHA256SUMS"
printf 'DEPLOY_STATUS=PASS\nPID=%s\nFIXED_CANDIDATE=%s\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${pid}" "${candidate}"
trap - EXIT
