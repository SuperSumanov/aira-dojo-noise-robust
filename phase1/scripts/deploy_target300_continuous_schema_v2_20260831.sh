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
readonly result_commit=8f5167e3a66733e0bee0ef53bf5f28021afca5d6
readonly base_repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly result_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly root=${result_root}/target300_continuous_schema_v2_v1
readonly anchor=${result_root}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly base_latest=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly previous_root=${result_root}/4a68c83-30945550b6b1-8e42f764cc05
readonly previous_manifest_sha=f05446579f8d808a7b37ad78566a0339a7999a9d70e1b2fec5388bce9b8fcbdc
readonly previous_summary_sha=6a9301af50fd8d471ffb40b55e59dee4dec987f73c94f0eccbbe6c803dd42428
readonly previous_verification_sha=5d3dec87aaab9e38f03fab7c89f05c390e54d091b004bf41cc7e3db69dcd785a
readonly monitor_path=phase1/scripts/monitor_target300_continuous_schema_v2_20260831.sh
readonly monitor_sha=1111950030bb2b1d93e7ed9a5e7a22fcd5ee1d58e74ed90c53a267e33e7a599d
readonly protocol_path=phase1/target300_continuous_schema_v2_continuation_v1.json
readonly protocol_sha=8a499b626c5e88549af6d9e797c36cef7f02e4461d7a3c2c9c66c3c6ccfa6a23
readonly runner_path=phase1/scripts/run_score_channel_future_cohort_20260823.sh
readonly runner_sha=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly safe_receipt_path=phase1/target300_schema_v2_safe_receipt_20260831.json
readonly safe_receipt_sha=41c23fa4ed50476969fdd4300b53e43cfcec288cfcdce10f8ddca9f6b8acd314

trap 'rc=$?; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT

test ! -e "${root}"
test ! -e "${anchor}"
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${base_latest}"
test -d "${previous_root}" && test ! -L "${previous_root}"
test "$(sha256sum "${previous_root}/SHA256SUMS" | awk '{print $1}')" = "${previous_manifest_sha}"
(cd "${previous_root}" && sha256sum -c SHA256SUMS >/dev/null)
test "$(sha256sum "${previous_root}/producer_a/summary.json" | awk '{print $1}')" = "${previous_summary_sha}"
test "$(sha256sum "${previous_root}/verification_a.json" | awk '{print $1}')" = "${previous_verification_sha}"
test -z "$(find "${previous_root}" -perm /022 -print -quit)"

git -C "${base_repo}" fetch fork phase1-value-critic >/tmp/target300_continuous_v2_fetch.stdout 2>/tmp/target300_continuous_v2_fetch.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"
git -C "${base_repo}" merge-base --is-ancestor "${result_commit}" "${release_commit}"

monitor_tmp=$(mktemp /tmp/target300-continuous-v2-monitor.XXXXXX)
protocol_tmp=$(mktemp /tmp/target300-continuous-v2-protocol.XXXXXX)
runner_tmp=$(mktemp /tmp/target300-continuous-v2-runner.XXXXXX)
receipt_tmp=$(mktemp /tmp/target300-continuous-v2-receipt.XXXXXX)
cleanup_tmp() {
  rm -f "${monitor_tmp}" "${protocol_tmp}" "${runner_tmp}" "${receipt_tmp}"
}
trap 'rc=$?; cleanup_tmp; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
git -C "${base_repo}" show "${release_commit}:${monitor_path}" >"${monitor_tmp}"
git -C "${base_repo}" show "${release_commit}:${protocol_path}" >"${protocol_tmp}"
git -C "${base_repo}" show "${release_commit}:${runner_path}" >"${runner_tmp}"
git -C "${base_repo}" show "${release_commit}:${safe_receipt_path}" >"${receipt_tmp}"
test "$(sha256sum "${monitor_tmp}" | awk '{print $1}')" = "${monitor_sha}"
test "$(sha256sum "${protocol_tmp}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${runner_tmp}" | awk '{print $1}')" = "${runner_sha}"
test "$(sha256sum "${receipt_tmp}" | awk '{print $1}')" = "${safe_receipt_sha}"
bash -n "${monitor_tmp}"
bash -n "${runner_tmp}"

mkdir "${root}"
chmod 0700 "${root}"
install -m 0500 "${monitor_tmp}" "${root}/monitor_target300_continuous_schema_v2_20260831.sh"
install -m 0400 "${protocol_tmp}" "${root}/target300_continuous_schema_v2_continuation_v1.json"
install -m 0500 "${runner_tmp}" "${root}/run_score_channel_future_cohort_20260823.sh"
install -m 0400 "${receipt_tmp}" "${root}/target300_schema_v2_safe_receipt_20260831.json"
printf '%s\n' "${release_commit}" >"${root}/release_commit.txt"
printf '%s\n' 4a68c83fba90655e9d60344081ae2b53b7c36104 >"${root}/science_commit.txt"
printf '%s\n' "${protocol_sha}" >"${root}/chain_protocol_sha256.txt"
cp /tmp/target300_continuous_v2_fetch.stdout "${root}/fetch.stdout"
cp /tmp/target300_continuous_v2_fetch.stderr "${root}/fetch.stderr"
cleanup_tmp

nohup bash "${root}/monitor_target300_continuous_schema_v2_20260831.sh" \
  >"${root}/launcher.stdout" 2>"${root}/launcher.stderr" </dev/null &
pid=$!
printf '%s\n' "${pid}" >"${root}/launcher.pid"
sleep 4
kill -0 "${pid}"
test ! -e "${root}/FAILED_RC"
test ! -e "${root}/DEPLOY_FAILED_RC"
test ! -s "${root}/launcher.stderr"
tr '\0' ' ' <"/proc/${pid}/cmdline" | grep -Fq "${root}/monitor_target300_continuous_schema_v2_20260831.sh"
grep -Fq "no_change poll=1 base=${base_latest} attempt=1 outcomes_read=false identities_read=false" "${root}/monitor.log"
if (exec 8<"${root}/monitor.lock"; flock -n -s 8); then
  printf 'continuous monitor lock is not held\n' >&2
  exit 1
fi

cat >"${root}/deployment_receipt.txt" <<EOF
deployed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=TARGET300_CONTINUOUS_SCHEMA_V2_LIVE
pid=${pid}
release_commit=${release_commit}
science_commit=4a68c83fba90655e9d60344081ae2b53b7c36104
base_latest=${base_latest}
previous_runs=219
previous_archives=69
remaining_runs=81
previous_manifest_sha256=${previous_manifest_sha}
previous_summary_sha256=${previous_summary_sha}
previous_verification_sha256=${previous_verification_sha}
monitor_sha256=${monitor_sha}
protocol_sha256=${protocol_sha}
runner_sha256=${runner_sha}
stable_polls=5
poll_seconds=300
max_polls=2016
ordered_chain=true
failed_candidate_retry=false
alternate_candidate=false
candidate_identities_read=false
outcomes_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
sha256sum \
  "${root}/monitor_target300_continuous_schema_v2_20260831.sh" \
  "${root}/target300_continuous_schema_v2_continuation_v1.json" \
  "${root}/run_score_channel_future_cohort_20260823.sh" \
  "${root}/target300_schema_v2_safe_receipt_20260831.json" \
  "${root}/deployment_receipt.txt" >"${root}/DEPLOY_STATIC_SHA256SUMS"
printf 'DEPLOY_STATUS=PASS\nPID=%s\nBASE_LATEST=%s\nPREVIOUS_RUNS=219\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${pid}" "${base_latest}"
trap - EXIT
