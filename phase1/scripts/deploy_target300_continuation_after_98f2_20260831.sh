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
readonly science_commit=ab59a011d945e4a96daf7dbbbc927a59027da077
readonly base_latest=98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa
readonly base_repo=/research/d7/spc/yzyang4/aira-dojo
readonly result_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly previous_root=${result_root}/ab59a01-98f2cba9ca4b-9f69935923f7
readonly previous_manifest_sha=81831f68055cef1fcae654b8adad3d71c8bf2893a57ef4ba0785e2c2b475cb2e
readonly previous_summary_sha=01d67cec48537c28183eac8777ab2cf0b19c118ed637318dd5d959c69b9a8b42
readonly previous_verification_sha=59624c596eb8d48a52540182c6632b89f90fdc71ad661b8a38d93a355e12ee12
readonly old_monitor=${result_root}/monitor_519815d_after_887_v1
readonly runner_source=${old_monitor}/run_score_channel_future_cohort_20260823.sh
readonly runner_sha=c6f6ed7abda2fbe6252271f2707e576845b1fd950aa9884d03597b86be8f660e
readonly monitor_repo_path=phase1/scripts/monitor_target300_after_98f2_20260831.sh
readonly monitor_sha=e35ea6e2ed7cb243e93e20acc1edecbd655155033fb9c5fa4b86ffc453a1be7b
readonly protocol_repo_path=phase1/target300_continuation_after_98f2_v1.json
readonly protocol_sha=3a9027792d9d0b6a5466788007b363a9472b62f26409f2fc13eff88987670f97
readonly safe_receipt_path=phase1/target300_progress_98f2_safe_receipt_20260830.json
readonly safe_receipt_sha=bde76f2798e341cd866d57dd4e3c0d9a8a9c76a4d2ce7f37ed252921006aa9ea
readonly root=${result_root}/monitor_after_98f2_v1
readonly anchor=${result_root}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1

trap 'rc=$?; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT

test ! -e "${root}"
test ! -e "${anchor}"
test -d "${previous_root}" && test ! -L "${previous_root}"
test "$(sha256sum "${previous_root}/SHA256SUMS" | awk '{print $1}')" = "${previous_manifest_sha}"
(cd "${previous_root}" && sha256sum -c SHA256SUMS >/dev/null)
test "$(sha256sum "${previous_root}/producer_a/summary.json" | awk '{print $1}')" = "${previous_summary_sha}"
test "$(sha256sum "${previous_root}/verification_a.json" | awk '{print $1}')" = "${previous_verification_sha}"
test -z "$(find "${previous_root}" -perm /022 -print -quit)"
test -x "${runner_source}" && test ! -L "${runner_source}"
test "$(sha256sum "${runner_source}" | awk '{print $1}')" = "${runner_sha}"
test -f "${old_monitor}/monitor.lock" && test ! -L "${old_monitor}/monitor.lock"
(exec 8<"${old_monitor}/monitor.lock"; flock -n -s 8)
current=$(tr -d '\r\n' <"${state}/LATEST")
[[ ${current} =~ ^[0-9a-f]{64}$ ]]
test "${current}" != "${base_latest}"

git -C "${base_repo}" fetch fork phase1-value-critic >/tmp/target300_after_98f2_fetch.stdout 2>/tmp/target300_after_98f2_fetch.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"
git -C "${base_repo}" merge-base --is-ancestor "${science_commit}" "${release_commit}"
test "$(git -C "${base_repo}" show "${release_commit}:${safe_receipt_path}" | sha256sum | awk '{print $1}')" = "${safe_receipt_sha}"

monitor_tmp=$(mktemp /tmp/target300-monitor.XXXXXX)
protocol_tmp=$(mktemp /tmp/target300-protocol.XXXXXX)
cleanup_tmp() {
  rm -f "${monitor_tmp}" "${protocol_tmp}"
}
trap 'rc=$?; cleanup_tmp; if (( rc != 0 )) && [[ -d "${root}" ]]; then printf "%s\n" "${rc}" >"${root}/DEPLOY_FAILED_RC" 2>/dev/null || true; fi; exit "${rc}"' EXIT
git -C "${base_repo}" show "${release_commit}:${monitor_repo_path}" >"${monitor_tmp}"
git -C "${base_repo}" show "${release_commit}:${protocol_repo_path}" >"${protocol_tmp}"
test "$(sha256sum "${monitor_tmp}" | awk '{print $1}')" = "${monitor_sha}"
test "$(sha256sum "${protocol_tmp}" | awk '{print $1}')" = "${protocol_sha}"
bash -n "${monitor_tmp}"

mkdir "${root}"
chmod 0700 "${root}"
install -m 0500 "${monitor_tmp}" "${root}/monitor_target300_after_98f2_20260831.sh"
install -m 0400 "${protocol_tmp}" "${root}/target300_continuation_after_98f2_v1.json"
install -m 0500 "${runner_source}" "${root}/run_score_channel_future_cohort_20260823.sh"
printf '%s\n' "${release_commit}" >"${root}/release_commit.txt"
printf '%s\n' "${science_commit}" >"${root}/science_commit.txt"
printf '%s\n' 54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d >"${root}/science_protocol_sha256.txt"
printf '%s\n' "${protocol_sha}" >"${root}/continuation_protocol_sha256.txt"
cp /tmp/target300_after_98f2_fetch.stdout "${root}/fetch.stdout"
cp /tmp/target300_after_98f2_fetch.stderr "${root}/fetch.stderr"
cleanup_tmp

nohup bash "${root}/monitor_target300_after_98f2_20260831.sh" \
  >"${root}/launcher.stdout" 2>"${root}/launcher.stderr" </dev/null &
pid=$!
printf '%s\n' "${pid}" >"${root}/launcher.pid"
sleep 4
kill -0 "${pid}"
test ! -e "${root}/FAILED_RC"
test ! -e "${root}/DEPLOY_FAILED_RC"
test ! -s "${root}/launcher.stderr"
tr '\0' ' ' <"/proc/${pid}/cmdline" | grep -Fq "${root}/monitor_target300_after_98f2_20260831.sh"
grep -Fq "candidate poll=1 snapshot=${current} stable_count=1/5 outcomes_read=false identities_read=false" "${root}/monitor.log"
if (exec 8<"${root}/monitor.lock"; flock -n -s 8); then
  printf 'new monitor lock is not held\n' >&2
  exit 1
fi

cat >"${root}/deployment_receipt.txt" <<EOF
deployed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status=TARGET300_AFTER_98F2_CONTINUATION_LIVE
pid=${pid}
release_commit=${release_commit}
science_commit=${science_commit}
base_latest=${base_latest}
first_observed_candidate=${current}
previous_runs=193
previous_archives=60
previous_remaining_runs=107
previous_manifest_sha256=${previous_manifest_sha}
previous_summary_sha256=${previous_summary_sha}
previous_verification_sha256=${previous_verification_sha}
monitor_sha256=${monitor_sha}
runner_sha256=${runner_sha}
continuation_protocol_sha256=${protocol_sha}
poll_seconds=300
stable_polls=5
max_polls=144
candidate_identities_read=false
outcomes_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
sha256sum \
  "${root}/monitor_target300_after_98f2_20260831.sh" \
  "${root}/target300_continuation_after_98f2_v1.json" \
  "${root}/run_score_channel_future_cohort_20260823.sh" \
  "${root}/deployment_receipt.txt" \
  >"${root}/DEPLOY_STATIC_SHA256SUMS"
printf 'DEPLOY_STATUS=PASS\nPID=%s\nFIRST_CANDIDATE=%s\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${pid}" "${current}"
trap - EXIT
