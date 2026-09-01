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
readonly result_commit=c0f67fd8d171fccb6ca68e805c8111e4828e5813
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly selection=/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2
readonly formal=/research/d7/spc/yzyang4/target522-gap-recovery/formal-c0f67fd-v2
readonly protocol_path=phase1/target522_selection_gap_resume_v1.json
readonly protocol_sha=81f0406995f6d59e9180baa7fd65c47464b2f892348b54be3320fd05b4a222d4
readonly receipt_path=phase1/target522_selection_gap_recovery_safe_receipt_20260901.json
readonly receipt_sha=078a0c8b9d9d5de51f1aa2efd3247cb1657f4df4057d03fb7dd939d0a0d3ca71
readonly formal_manifest_sha=9c0f96eb9d652eefc7f57f451271b61bd72e85235b3157ca49b9e67f0e8864c0
readonly formal_summary_sha=db98021768139d873e8012d83f0b0716a8fa7d53f64f1efbb12674aa3ab76812
readonly formal_verification_sha=ef801e5d052dada9b40f3256d982da7489764338ae429ea27d54416c2d783e3b
readonly extension_sha=d998e8a3b40efb4d515793d1055e473435361313f38834c4b3da0e7771f28da9
readonly old_observed_sha=0e444525aed0e8f34892dda4334251260add7efa33e2e76ebc22773ef7f48c47
readonly recovered_observed_sha=0277463211df467fb241776d975b4afab0133009f75f8b9cd53d15785341170f
readonly old_observed_lines=22
readonly recovered_observed_lines=29
readonly old_last_snapshot=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly recovered_last_snapshot=e9e12c639fdeb54f3c18ef9d55841db60332baedfe8149774006e458ab8e8a6d
readonly old_last_runs=494
readonly recovered_last_runs=517
readonly target_runs=522
readonly selection_source_commit=42f10449f793a5c4feafc0a622b91804d45e59a7
readonly selection_protocol_sha=718224d9586b45a1bf6689c2bb9dd1d6b76e7243b8ddd2267dcf94fc6ea2667f
readonly selection_source_sha=8cab471b3c57c07711238f19cbcc80836aa7f4450faedf6ca50d60a306d4596b

tmp_observed=
cleanup() {
  rc=$?
  if [[ -n ${tmp_observed} ]]; then rm -f "${tmp_observed}"; fi
  if (( rc != 0 )); then printf '%s\n' "${rc}" >"${selection}/GAP_RECOVERY_DEPLOY_FAILED_RC" 2>/dev/null || true; fi
  exit "${rc}"
}
trap cleanup EXIT

test -d "${repo}" && test ! -L "${repo}"
test -d "${state}" && test ! -L "${state}"
test -d "${selection}" && test ! -L "${selection}"
test -d "${formal}" && test ! -L "${formal}"
test ! -e "${selection}/GAP_RECOVERY_APPLIED"
test ! -e "${selection}/GAP_RECOVERY_DEPLOY_FAILED_RC"
test ! -e "${selection}/gap_recovery_resume_preflight_13.txt"

readonly checkout=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
test "$(git -C "${checkout}" rev-parse HEAD)" = "${release_commit}"
test -z "$(git -C "${checkout}" status --porcelain --untracked-files=all)"
git -C "${repo}" fetch fork phase1-value-critic
test "$(git -C "${repo}" rev-parse fork/phase1-value-critic)" = "${release_commit}"
git -C "${repo}" merge-base --is-ancestor "${result_commit}" "${release_commit}"
test "$(sha256sum "${checkout}/${protocol_path}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${checkout}/${receipt_path}" | awk '{print $1}')" = "${receipt_sha}"
jq -e --arg latest "${recovered_last_snapshot}" --arg ledger "${recovered_observed_sha}" '
  .protocol == "target522-selection-gap-resume-v1"
  and .status == "FROZEN_BEFORE_APPEND_AND_RESUME"
  and .frozen_after_formal_result_before_ledger_mutation == true
  and .selection.expected_current_latest_sha256 == $latest
  and .ledger.expected_recovered_sha256 == $ledger
  and .ledger.final_runs == 517
  and .ledger.target_runs == 522
' "${checkout}/${protocol_path}" >/dev/null
jq -e '
  .status == "TARGET522_GAP_RECOVERY_NO_CROSSING_PASS"
  and .recovered_successors == 7
  and .previous_runs == 494
  and .final_runs == 517
  and .remaining_runs == 5
  and .outcomes_or_prediction_values_read == false
  and .candidate_identity_or_profile_read == false
' "${checkout}/${receipt_path}" >/dev/null

test -e "${formal}/COMPLETE" && test ! -e "${formal}/FAILED_RC"
test "$(sha256sum "${formal}/SHA256SUMS" | awk '{print $1}')" = "${formal_manifest_sha}"
(cd "${formal}" && sha256sum -c SHA256SUMS >/dev/null)
test -z "$(find "${formal}" -perm /022 -print -quit)"
test "$(sha256sum "${formal}/producer_a/summary.json" | awk '{print $1}')" = "${formal_summary_sha}"
test "$(sha256sum "${formal}/verification_a.json" | awk '{print $1}')" = "${formal_verification_sha}"
test "$(sha256sum "${formal}/producer_a/observed_extension.tsv" | awk '{print $1}')" = "${extension_sha}"

exec 9>"${selection}/monitor.lock"
flock -n 9
test ! -e "${selection}/candidate.tsv"
test ! -e "${selection}/READY"
test ! -e "${selection}/COMPLETE"
test ! -e "${selection}/FAILED_RC"
test ! -e "${selection}/CONTINUITY_GAP"
test -f "${selection}/TIMEOUT_RC"
test "$(tr -d '\r\n' <"${selection}/TIMEOUT_RC")" = 124
test "$(tr -d '\r\n' <"${state}/LATEST")" = "${recovered_last_snapshot}"
test "$(sha256sum "${selection}/source_script.sh" | awk '{print $1}')" = "${selection_source_sha}"
test "$(sha256sum "${selection}/protocol.json" | awk '{print $1}')" = "${selection_protocol_sha}"
test "$(sha256sum "${selection}/observed.tsv" | awk '{print $1}')" = "${old_observed_sha}"
test "$(wc -l <"${selection}/observed.tsv")" = "${old_observed_lines}"
test "$(tail -n 1 "${selection}/observed.tsv" | cut -f1)" = "${old_last_snapshot}"
test "$(tail -n 1 "${selection}/observed.tsv" | cut -f2)" = "${old_last_runs}"

cat >"${selection}/gap_recovery_resume_preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol; PASS
02_question=append exactly seven formally verified no-crossing observations and resume original first-crossing watcher; PASS
03_release_commit=${release_commit}; PASS
04_recovery_result_commit=${result_commit}; PASS
05_protocol_sha256=${protocol_sha}; PASS
06_old_ledger_sha256_lines_runs=${old_observed_sha}/${old_observed_lines}/${old_last_runs}; PASS
07_extension_sha256_successors=${extension_sha}/7; PASS
08_recovered_ledger_sha256_lines_runs=${recovered_observed_sha}/${recovered_observed_lines}/${recovered_last_runs}; PASS
09_latest=${recovered_last_snapshot},target=${target_runs},strictly_below_target=true; PASS
10_atomicity=exclusive monitor lock plus same-directory verified temp and atomic rename; PASS
11_resume=original source script commit/protocol/hash fixed and current LATEST must equal recovered tail; PASS
12_forbidden=no label outcome prediction accuracy utility candidate profile private identity raw archive; PASS
13_resources_and_failure=GPU/API/model-fit/base-update 0/0/0/0; drift or race fails closed; PASS
EOF
test "$(wc -l <"${selection}/gap_recovery_resume_preflight_13.txt")" = 13

tmp_observed=$(mktemp "${selection}/observed.tsv.gap-recovery.XXXXXX")
cat "${selection}/observed.tsv" "${formal}/producer_a/observed_extension.tsv" >"${tmp_observed}"
test "$(sha256sum "${tmp_observed}" | awk '{print $1}')" = "${recovered_observed_sha}"
test "$(wc -l <"${tmp_observed}")" = "${recovered_observed_lines}"
test "$(tail -n 1 "${tmp_observed}" | cut -f1)" = "${recovered_last_snapshot}"
test "$(tail -n 1 "${tmp_observed}" | cut -f2)" = "${recovered_last_runs}"
awk -F '\t' -v target="${target_runs}" '
  NR == 1 {next}
  $2 !~ /^[0-9]+$/ || $2 < previous || $2 >= target {exit 1}
  {previous=$2; count++}
  END {if (count != 28) exit 1}
' "${tmp_observed}"
chmod 0600 "${tmp_observed}"
mv "${tmp_observed}" "${selection}/observed.tsv"
tmp_observed=
sync -f "${selection}/observed.tsv"

cat >"${selection}/GAP_RECOVERY_APPLIED.tmp" <<EOF
status=TARGET522_GAP_RECOVERY_APPEND_PASS
applied_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
release_commit=${release_commit}
result_commit=${result_commit}
protocol_sha256=${protocol_sha}
formal_manifest_sha256=${formal_manifest_sha}
extension_sha256=${extension_sha}
old_observed_sha256=${old_observed_sha}
recovered_observed_sha256=${recovered_observed_sha}
recovered_successors=7
previous_runs=${old_last_runs}
final_runs=${recovered_last_runs}
target_runs=${target_runs}
remaining_runs=$((target_runs - recovered_last_runs))
outcomes_read=false
candidate_profile_or_private_identity_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
mv "${selection}/GAP_RECOVERY_APPLIED.tmp" "${selection}/GAP_RECOVERY_APPLIED"
sync -f "${selection}/GAP_RECOVERY_APPLIED"
test "$(sha256sum "${selection}/observed.tsv" | awk '{print $1}')" = "${recovered_observed_sha}"
flock -u 9
exec 9>&-

nohup bash "${selection}/source_script.sh" resume "${selection}" \
  "${selection_source_commit}" "${selection_protocol_sha}" \
  >"${selection}/resume_after_gap_recovery.stdout" \
  2>"${selection}/resume_after_gap_recovery.stderr" </dev/null &
launcher_pid=$!
for _ in $(seq 1 30); do
  if kill -0 "${launcher_pid}" 2>/dev/null \
    && test -f "${selection}/monitor.pid" \
    && test "$(tr -d '\r\n' <"${selection}/monitor.pid")" = "${launcher_pid}" \
    && ! flock -n "${selection}/monitor.lock" true; then
    break
  fi
  sleep 1
done
kill -0 "${launcher_pid}"
test "$(tr -d '\r\n' <"${selection}/monitor.pid")" = "${launcher_pid}"
if flock -n "${selection}/monitor.lock" true; then exit 1; fi
test ! -e "${selection}/TIMEOUT_RC"
test ! -e "${selection}/FAILED_RC"
test ! -e "${selection}/CONTINUITY_GAP"
test "$(sha256sum "${selection}/observed.tsv" | awk '{print $1}')" = "${recovered_observed_sha}"
test "$(tail -n 1 "${selection}/observed.tsv" | cut -f2)" = "${recovered_last_runs}"

cat >"${selection}/gap_recovery_resume_receipt.txt" <<EOF
status=TARGET522_SELECTION_WATCHER_RESUMED
verified_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
pid=${launcher_pid}
release_commit=${release_commit}
protocol_sha256=${protocol_sha}
observed_sha256=${recovered_observed_sha}
observed_runs=${recovered_last_runs}
target_runs=${target_runs}
remaining_runs=$((target_runs - recovered_last_runs))
lock_held=true
continuity_gap=false
outcomes_read=false
candidate_profile_or_private_identity_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
sha256sum "${selection}/GAP_RECOVERY_APPLIED" \
  "${selection}/gap_recovery_resume_preflight_13.txt" \
  "${selection}/gap_recovery_resume_receipt.txt" >"${selection}/GAP_RECOVERY_STATIC_SHA256SUMS"
printf 'STATUS=TARGET522_SELECTION_WATCHER_RESUMED\nPID=%s\nRUNS=%s\nTARGET=%s\nREMAINING=%s\nOBSERVED_SHA256=%s\nOUTCOMES_READ=false IDENTITIES_READ=false\n' \
  "${launcher_pid}" "${recovered_last_runs}" "${target_runs}" "$((target_runs - recovered_last_runs))" "${recovered_observed_sha}"
trap - EXIT
