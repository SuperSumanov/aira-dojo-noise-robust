#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_task_balance_forward_v3_first_successor_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly output=$1
readonly expected_commit=$2
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly state_root=/research/d7/spc/yzyang4/prospective_decision_v1
readonly latch_v4=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v4
readonly latch_v5_failed=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5
readonly latch_v5_r2=/research/d7/spc/yzyang4/task-balance-v3-first-successor/latch-continuation-after-887-v5-r2
readonly continuation_v4_public_path=phase1/scripts/resume_task_balance_v3_first_successor_after_887_20260828.sh
readonly continuation_v5_r2_public_path=phase1/scripts/resume_task_balance_v3_first_successor_after_v4_20260828.sh
readonly failed_v5_fileset_sha=d3ee4736512f81ad6f40a6ec7bdeb5547d48b217f9452c72461187dc14e3ba50
readonly forbidden_snapshot=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly baseline_snapshot=7cdaefcf2be7786442e1af1f4d0b4012edee708932f1fad31e174c0dcaf803a1
readonly baseline_root=${state_root}/snapshots/${baseline_snapshot}/accumulator
readonly baseline_summary_sha=ad3e8fe4180fd6c6f7fcea121ef0c51c0f292445d77368e2b3ab4dc9a56d4585
readonly baseline_ledger_sha=43b1f16d5326fad5de490a5b63bd8a6f3c454ad303c031cd1fb54e607919cf83
readonly guard=phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836/guard.json
readonly guard_sha=2ffa91a5e10f17f31c1a79f51a69d2f4e2331353e9ac9cfab14c6c40352cd177
readonly guard_verification=phase1/results/task_balance_structural_only_v2_8579_20260826_1b9b836/guard_independent_verification.json
readonly guard_verification_sha=62f5fa00ad4535c0e6e8706daf62f5408ac4fa407506f761b42840d1c115310c
readonly protocol=phase1/task_balance_forward_v3_future_protocol_v1.json
readonly protocol_sha=6db91cddecc3b1937fd694e2b4903f02f8f81bd4c6a6cdd6b01f46944c552ee1
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

field() {
  local key=$1 file=$2 value
  value=$(sed -n "s/^${key}=//p" "${file}")
  test -n "${value}"
  test "$(grep -c "^${key}=" "${file}")" = 1
  printf '%s' "${value}"
}

test "$(git rev-parse HEAD)" = "${expected_commit}"
test ! -e "${output}"
mkdir -p "${output}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${output}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

if test -f "${latch_v4}/COMPLETE"; then
  test ! -e "${latch_v5_failed}"
  test ! -e "${latch_v5_r2}"
  readonly latch=${latch_v4}
  readonly continuation_public_path=${continuation_v4_public_path}
  readonly expected_ready_status=FIRST_SUCCESSOR_AND_SUPPORT_READY_AFTER_VERIFIED_CONTINUITY
  readonly timeout_handoff_generation=1
elif test -f "${latch_v4}/TIMEOUT_RC" \
  && test -f "${latch_v5_failed}/FAILED_RC" \
  && test -f "${latch_v5_r2}/COMPLETE"; then
  test "$(tr -d '\r\n' < "${latch_v4}/TIMEOUT_RC")" = 124
  test ! -e "${latch_v4}/FAILED_RC"
  test ! -e "${latch_v4}/COMPLETE"
  test "$(tr -d '\r\n' < "${latch_v5_failed}/FAILED_RC")" = 1
  test ! -e "${latch_v5_failed}/candidate.tsv"
  test ! -e "${latch_v5_failed}/READY"
  test ! -e "${latch_v5_failed}/COMPLETE"
  readonly latch=${latch_v5_r2}
  readonly continuation_public_path=${continuation_v5_r2_public_path}
  readonly expected_ready_status=FIRST_SUCCESSOR_AND_SUPPORT_READY_AFTER_SECOND_TIMEOUT_HANDOFF
  readonly timeout_handoff_generation=2
else
  printf '%s\n' 'no unique completed authoritative latch generation' >&2
  exit 65
fi

test -f "${latch}/COMPLETE"
test ! -e "${latch}/FAILED_RC"
test -f "${latch}/READY"
(cd "${latch}" && sha256sum -c SHA256SUMS > "${output}/latch_manifest_check.txt")
test "$(field status "${latch}/READY")" = "${expected_ready_status}"
control_commit=$(field control_commit "${latch}/READY")
continuation_script_sha=$(field continuation_script_sha256 "${latch}/READY")
[[ ${control_commit} =~ ^[0-9a-f]{40}$ ]]
[[ ${continuation_script_sha} =~ ^[0-9a-f]{64}$ ]]
git cat-file -e "${control_commit}^{commit}"
git merge-base --is-ancestor "${control_commit}" "${expected_commit}"
git show "${control_commit}:${continuation_public_path}" > "${output}/continuation_source_from_git.sh"
test "$(sha256sum "${output}/continuation_source_from_git.sh" | awk '{print $1}')" = "${continuation_script_sha}"
cmp "${latch}/source_script.sh" "${output}/continuation_source_from_git.sh"
test "$(field protocol_sha256 "${latch}/READY")" = "${protocol_sha}"
test "$(field baseline_snapshot_sha256 "${latch}/READY")" = "${forbidden_snapshot}"
test "$(field previous_latch_timeout_continuity "${latch}/READY")" = true
test "$(field manual_snapshot_choice "${latch}/READY")" = false
test "$(field earlier_successor_skipped "${latch}/READY")" = false
test "$(field balance_values_or_classification_read "${latch}/READY")" = false
test "$(field prospective_outcomes_or_prediction_values_read "${latch}/READY")" = false
if test "${timeout_handoff_generation}" = 2; then
  test "$(field timeout_handoff_generation "${latch}/READY")" = 2
  test "$(field timeout_handoff_generation "${latch}/candidate.tsv")" = 2
  test "$(field status "${latch}/candidate.tsv")" = FIRST_SUCCESSOR_BOUND_ACROSS_SECOND_TIMEOUT_HANDOFF
  test "$(field heartbeat_race_repair "${latch}/READY")" = true
  test "$(field heartbeat_race_repair "${latch}/candidate.tsv")" = true
  test "$(field failed_attempt_fileset_sha256 "${latch}/READY")" = "${failed_v5_fileset_sha}"
  test "$(field failed_attempt_fileset_sha256 "${latch}/candidate.tsv")" = "${failed_v5_fileset_sha}"
  handoff_mode=$(field handoff_mode "${latch}/READY")
  candidate_origin=$(field candidate_origin "${latch}/READY")
  case "${handoff_mode}" in
    CANDIDATE_PRESERVED_FROM_PREVIOUS_TIMEOUT|PRE_CANDIDATE_CONTIGUOUS_HANDOFF_AFTER_HEARTBEAT_RACE_REPAIR) ;;
    *) exit 66 ;;
  esac
  case "${candidate_origin}" in
    PREVIOUS_AUTHORITATIVE_LATCH|RECOVERED_SINGLE_SUCCESSOR_ACROSS_TIMEOUT_GAP|LATCHED_BY_SECOND_CONTINUATION) ;;
    *) exit 67 ;;
  esac
  test "$(field candidate_origin "${latch}/candidate.tsv")" = "${candidate_origin}"
fi

current_snapshot=$(field candidate_snapshot_sha256 "${latch}/READY")
[[ ${current_snapshot} =~ ^[0-9a-f]{64}$ ]]
test "${current_snapshot}" != "${forbidden_snapshot}"
test "$(field candidate_snapshot_sha256 "${latch}/candidate.tsv")" = "${current_snapshot}"
test "$(field control_commit "${latch}/candidate.tsv")" = "${control_commit}"
test "$(field continuation_script_sha256 "${latch}/candidate.tsv")" = "${continuation_script_sha}"
test "$(field previous_latch_timeout_continuity "${latch}/candidate.tsv")" = true
current_root=${state_root}/snapshots/${current_snapshot}/accumulator
current_summary=${current_root}/summary.json
current_ledger=${current_root}/provisional_first960_runs.jsonl
current_summary_sha=$(field summary_sha256 "${latch}/candidate.tsv")
current_ledger_sha=$(field ledger_sha256 "${latch}/candidate.tsv")
common_support=$(field common_support_verification_path "${latch}/READY")
common_support_sha=$(field common_support_verification_sha256 "${latch}/READY")
[[ ${current_summary_sha} =~ ^[0-9a-f]{64}$ ]]
[[ ${current_ledger_sha} =~ ^[0-9a-f]{64}$ ]]
[[ ${common_support_sha} =~ ^[0-9a-f]{64}$ ]]
[[ ${common_support} =~ ^/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1/[A-Za-z0-9_.-]+/verification_a.json$ ]]
test -f "${current_summary}"
test -f "${current_ledger}"
test -f "${common_support}"
test ! -L "${current_summary}"
test ! -L "${current_ledger}"
test ! -L "${common_support}"
test "$(sha256sum "${current_summary}" | awk '{print $1}')" = "${current_summary_sha}"
test "$(sha256sum "${current_ledger}" | awk '{print $1}')" = "${current_ledger_sha}"
test "$(sha256sum "${common_support}" | awk '{print $1}')" = "${common_support_sha}"
test "$(sha256sum "${baseline_root}/summary.json" | awk '{print $1}')" = "${baseline_summary_sha}"
test "$(sha256sum "${baseline_root}/provisional_first960_runs.jsonl" | awk '{print $1}')" = "${baseline_ledger_sha}"
test "$(sha256sum "${guard}" | awk '{print $1}')" = "${guard_sha}"
test "$(sha256sum "${guard_verification}" | awk '{print $1}')" = "${guard_verification_sha}"
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"

cat > "${output}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=does first automatically latched successor satisfy fixed dominant-task pair-share cap; PASS
03_selection=latch ${latch},candidate ${current_snapshot},manual false,earlier skipped false; PASS
04_baseline=${baseline_snapshot},fixed 25-percent cap and exact debt; PASS
05_task_universe=monotone expansion with explicit baseline-zero counts,no deletion or dominant change; PASS
06_inputs=hash-bound summary,ledger,guard,independent guard,and receipt-only common support; PASS
07_primary=CAP_PASS iff all shares <=0.25 and exact debt zero,else CAP_FAIL; PASS
08_secondary=HHI,TV,debt direction cannot rescue primary; PASS
09_controls=producer A/B,non-importing verifier A/B,focused/full tests; PASS
10_randomness=none,PYTHONHASHSEED 0/1,numeric threads 1; PASS
11_resources=CPU only,1800-second timeout,32-GiB virtual memory,GPU/API/model-fit/base-update 0/0/0/0; PASS
12_forbidden=887 reuse,manual skip,label,outcome,prediction values,accuracy,effect,utility,raw archives; PASS
13_failure=immutable FAILED_RC,no task,threshold,population,snapshot or interpretation rescue; PASS
EOF

export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

git status --porcelain=v1 > "${output}/git_status_before.txt"
test ! -s "${output}/git_status_before.txt"
timeout 1800s "${python}" -m pytest -q \
  phase1/tests/test_task_balance_structural_only_v2.py \
  phase1/tests/test_20260828_future_protocols.py \
  > "${output}/focused_tests.txt"
timeout 1800s "${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

producer=(
  "${python}" -m phase1.task_balance_guard_forward_validation_v3
  --guard "${guard}"
  --expect-guard-sha256 "${guard_sha}"
  --guard-verification "${guard_verification}"
  --expect-guard-verification-sha256 "${guard_verification_sha}"
  --baseline-summary "${baseline_root}/summary.json"
  --expect-baseline-summary-sha256 "${baseline_summary_sha}"
  --baseline-ledger "${baseline_root}/provisional_first960_runs.jsonl"
  --expect-baseline-ledger-sha256 "${baseline_ledger_sha}"
  --baseline-snapshot-sha256 "${baseline_snapshot}"
  --current-summary "${current_summary}"
  --expect-current-summary-sha256 "${current_summary_sha}"
  --current-ledger "${current_ledger}"
  --expect-current-ledger-sha256 "${current_ledger_sha}"
  --current-snapshot-sha256 "${current_snapshot}"
  --current-common-support-verification "${common_support}"
  --expect-current-common-support-verification-sha256 "${common_support_sha}"
)
PYTHONHASHSEED=0 timeout 1800s strace -f -e trace=file -o "${output}/producer_a.trace" \
  "${producer[@]}" --output "${output}/producer_a.json" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${producer[@]}" --output "${output}/producer_b.json" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
test ! -s "${output}/producer_a.stderr"
test ! -s "${output}/producer_b.stderr"
cmp "${output}/producer_a.json" "${output}/producer_b.json"
producer_sha=$(sha256sum "${output}/producer_a.json" | awk '{print $1}')

verifier=(
  "${python}" -m phase1.verify_task_balance_guard_forward_validation_v3
  --guard "${guard}"
  --expect-guard-sha256 "${guard_sha}"
  --guard-verification "${guard_verification}"
  --expect-guard-verification-sha256 "${guard_verification_sha}"
  --baseline-summary "${baseline_root}/summary.json"
  --expect-baseline-summary-sha256 "${baseline_summary_sha}"
  --baseline-ledger "${baseline_root}/provisional_first960_runs.jsonl"
  --expect-baseline-ledger-sha256 "${baseline_ledger_sha}"
  --baseline-snapshot-sha256 "${baseline_snapshot}"
  --current-summary "${current_summary}"
  --expect-current-summary-sha256 "${current_summary_sha}"
  --current-ledger "${current_ledger}"
  --expect-current-ledger-sha256 "${current_ledger_sha}"
  --current-snapshot-sha256 "${current_snapshot}"
  --current-common-support-verification "${common_support}"
  --expect-current-common-support-verification-sha256 "${common_support_sha}"
  --result "${output}/producer_a.json"
  --expect-result-sha256 "${producer_sha}"
)
PYTHONHASHSEED=0 timeout 1800s strace -f -e trace=file -o "${output}/verifier_a.trace" \
  "${verifier[@]}" --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
PYTHONHASHSEED=1 timeout 1800s "${verifier[@]}" --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
test ! -s "${output}/verifier_a.stderr"
test ! -s "${output}/verifier_b.stderr"
cmp "${output}/verification_a.json" "${output}/verification_b.json"

for trace in "${output}/producer_a.trace" "${output}/verifier_a.trace"; do
  forbidden_hits=$(grep -Eic \
    '/external/senior_data/|label_vault|/outcomes?/|pair_predictions\.jsonl|endpoint_scores\.csv|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv)|raw_archive|/\.env([" ]|$)' \
    "${trace}" || true)
  test "${forbidden_hits}" = 0
done

cap_pass=$(jq -r '.frozen_guard_forward_result.current_cap_pass' "${output}/producer_a.json")
test "${cap_pass}" = true || test "${cap_pass}" = false
if test "${cap_pass}" = true; then classification=CAP_PASS; else classification=CAP_FAIL; fi
jq -n \
  --arg classification "${classification}" \
  --arg commit "${expected_commit}" \
  --arg snapshot "${current_snapshot}" \
  --arg producer_sha "${producer_sha}" \
  --arg verifier_sha "$(sha256sum "${output}/verification_a.json" | awk '{print $1}')" \
  '{
    protocol:"task-balance-forward-v3-first-successor-formal-v1",
    status:"FORMAL_TASK_BALANCE_FORWARD_V3_COMPLETE",
    classification:$classification,
    source_commit:$commit,
    current_snapshot_sha256:$snapshot,
    producer_sha256:$producer_sha,
    independent_verification_sha256:$verifier_sha,
    producer_ab_byte_identical:true,
    verifier_ab_byte_identical:true,
    secondary_cannot_rescue_primary:true,
    task_identities_emitted:true,
    labels_outcomes_prediction_values_read:false,
    gpu_api_model_fit_base_update:[0,0,0,0]
  }' > "${output}/classification.json"

credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=security_scan_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
printf '%s\n' \
  'boundary_aware_credential_file_hits=0' \
  'credential_filename_hits=0' \
  'labels_outcomes_prediction_values_read=false' \
  'raw_senior_archives_opened=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' \
  > "${output}/access_attestation.txt"

git status --porcelain=v1 > "${output}/git_status_after.txt"
test ! -s "${output}/git_status_after.txt"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${output}"
trap - EXIT
cat "${output}/classification.json"
sha256sum "${output}/producer_a.json" "${output}/verification_a.json" "${output}/SHA256SUMS"
printf '%s\n' FORMAL_TASK_BALANCE_FORWARD_V3_COMPLETE
