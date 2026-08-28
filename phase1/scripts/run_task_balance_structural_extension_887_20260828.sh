#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_task_balance_structural_extension_887_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly root=$1
readonly expected_commit=$2
readonly actual_commit=$(git rev-parse HEAD)
readonly protocol=phase1/task_balance_structural_extension_887_protocol_v1.json
readonly protocol_sha=a87cd673618bc2f31eae1eacea7062c92ee31a07a1c4eaa877b6a138b1f7cc9a
readonly original=phase1/scripts/run_task_balance_structural_only_v2_20260826.sh
readonly original_sha=b2c25c271b9e82382418f2f7bef8eee1b9ea5ec35f5ed381c26d08c5961fe2ac
readonly patched=${root}/run_task_balance_structural_only_v2_887.sh
readonly artifact=${root}/artifact
readonly snapshot=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly current_summary_sha=2f28b5b53cca5d6ea5ebf16f746a70f9c1de0e3197487a6ed78d41b4cb611302
readonly current_ledger_sha=510d81820d7825fc6baa6db562b2371e50eb7d71d04cb1cc0bd17d095d6cdbca
readonly common_path=/research/d7/spc/yzyang4/prediction-receipt-common-support/artifacts_9f2cbe9_v1/20260828T012831Z_887491a021d7/verification_a.json
readonly common_sha=82f56f8dae175f60adb0e0c7545be053cade98b1f84388ce282b187f74e70c78

test "${actual_commit}" = "${expected_commit}"
test ! -e "${root}"
mkdir -p "${root}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${root}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

cat > "${root}/preflight_13.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus benchmark balance; structural-only extension
PREFLIGHT_02_QUESTION=does the frozen 25-percent dominant-task cap pass, improve without passing, or not improve at 435 runs
PREFLIGHT_03_PROTOCOL=${protocol_sha}; frozen before current per-task distribution was read
PREFLIGHT_04_COHORT=7cda frozen guard to exact ${snapshot}; known totals 435 runs/3053 pairs/34 tasks
PREFLIGHT_05_PRIMARY=cap status then preordered directional classification against public ad0b 850/2884 and debt 516
PREFLIGHT_06_INPUTS=current summary ${current_summary_sha}; ledger ${current_ledger_sha}; receipt ${common_sha}
PREFLIGHT_07_ONLY_CODE_CHANGE=mechanically retarget existing structural-only v2 harness to fixed current snapshot and receipt
PREFLIGHT_08_FORBIDDEN=prediction pair/value/matrix,label,grade,outcome,winner,accuracy,effect,utility,raw archive
PREFLIGHT_09_REPRO=producer A/B,non-importing verifier A/B,exact chronology and common-support checks
PREFLIGHT_10_RANDOMNESS=none
PREFLIGHT_11_RESOURCES=CPU single-thread;GPU/API/model_fit/base_update=0/0/0/0
PREFLIGHT_12_SUCCESS=all hashes,counts,A/B,trace,credential and full tests pass regardless of direction
PREFLIGHT_13_FAILURE=immutable failure receipt;no threshold,task,subset or snapshot rescue
EOF

test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
test "$(sha256sum "${original}" | awk '{print $1}')" = "${original_sha}"
test "$(sha256sum "${common_path}" | awk '{print $1}')" = "${common_sha}"
test "$(sha256sum "/research/d7/spc/yzyang4/prospective_decision_v1/snapshots/${snapshot}/accumulator/summary.json" | awk '{print $1}')" = "${current_summary_sha}"
test "$(sha256sum "/research/d7/spc/yzyang4/prospective_decision_v1/snapshots/${snapshot}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')" = "${current_ledger_sha}"

cp "${original}" "${patched}"
sed -i \
  -e "s|^current_snapshot=.*$|current_snapshot=${snapshot}|" \
  -e "s|^current_summary_sha=.*$|current_summary_sha=${current_summary_sha}|" \
  -e "s|^current_ledger_sha=.*$|current_ledger_sha=${current_ledger_sha}|" \
  -e "s|^common=.*$|common=${common_path}|" \
  -e "s|^common_sha=.*$|common_sha=${common_sha}|" \
  "${patched}"
chmod 0500 "${patched}"
bash -n "${patched}"
set +e
diff -u "${original}" "${patched}" > "${root}/harness_fixed_input_only.diff"
diff_rc=$?
set -e
test "${diff_rc}" = 1
test "$(grep -c '^@@' "${root}/harness_fixed_input_only.diff")" -le 5
test "$(grep -Ec '^[-+](current_snapshot|current_summary_sha|current_ledger_sha|common|common_sha)=' "${root}/harness_fixed_input_only.diff")" = 10
test "$(grep -Ec '^[+-][^+-]' "${root}/harness_fixed_input_only.diff")" = 10
sha256sum "${protocol}" "${original}" "${patched}" > "${root}/control_hashes.txt"

bash "${patched}" "${artifact}" "${expected_commit}" \
  > "${root}/formal.stdout" 2> "${root}/formal.stderr"
test -f "${artifact}/COMPLETE"
(cd "${artifact}" && sha256sum -c SHA256SUMS > /dev/null)
test ! -s "${artifact}/forbidden_trace_hits.txt"
test ! -s "${artifact}/name_scan_hits.txt"
test ! -s "${artifact}/content_scan_hits.txt"
cmp "${artifact}/guard_a.json" "${artifact}/guard_b.json"
cmp "${artifact}/guard_verify_a.json" "${artifact}/guard_verify_b.json"
cmp "${artifact}/forward_a.json" "${artifact}/forward_b.json"
cmp "${artifact}/forward_verify_a.json" "${artifact}/forward_verify_b.json"

jq -e --arg snapshot "${snapshot}" --arg summary "${current_summary_sha}" --arg ledger "${current_ledger_sha}" --arg common "${common_sha}" '
  .status == "STRUCTURAL_ONLY_FORWARD_ACCOUNTING_EXACT"
  and .inputs.current_snapshot_sha256 == $snapshot
  and .inputs.current_accumulator_summary_sha256 == $summary
  and .inputs.current_first960_runs_sha256 == $ledger
  and .inputs.current_receipt_common_support_verification_sha256 == $common
  and .source_validation.current_summary_and_ledger_revalidated == true
  and .source_validation.current_total_cross_checked_by_receipt_only_independent_verifier == true
  and .source_validation.prediction_matrix_input_used == false
  and .frozen_guard_forward_result.debt_accounting_identity_exact == true
  and .claim_boundary.predictor_accuracy_effect_or_search_utility_computed == false
  and .access_attestation.prediction_values_read_or_aggregated == false
  and .access_attestation.labels_grades_outcomes_or_winner_orientation_read == false
  and .access_attestation.raw_archive_payload_read == false
' "${artifact}/forward_a.json" > /dev/null

jq -n --slurpfile forward "${artifact}/forward_a.json" '
  ($forward[0].frozen_guard_forward_result) as $r
  | (if ($r.current_cap_pass == true and $r.observed_current_debt == 0)
      then "CAP_PASS"
      elif (($r.current_dominant_pairs * 2884 < 850 * 3053) and ($r.observed_current_debt < 516))
      then "DIRECTIONAL_BALANCE_GAIN_ONLY"
      else "NO_BALANCE_GAIN"
    end) as $classification
  | {
      protocol: "task-balance-structural-extension-887-v1",
      classification: $classification,
      current: {
        total_pairs: 3053,
        dominant_task: $r.dominant_task,
        dominant_pairs: $r.current_dominant_pairs,
        dominant_share: $r.current_dominant_share,
        debt: $r.observed_current_debt,
        cap_pass: $r.current_cap_pass
      },
      frozen_guard_baseline: {
        debt: $r.baseline_debt
      },
      accrual: {
        dominant_pairs: $r.future_dominant_pairs,
        nondominant_pairs: $r.future_nondominant_pairs,
        debt_delta: $r.debt_delta,
        debt_direction: $r.debt_direction,
        immediate_action_adherence: $r.immediate_action_adherence
      },
      public_ad0b_reference: {
        total_pairs: 2884,
        dominant_pairs: 850,
        debt: 516
      },
      claim_boundary: {
        causal_acquisition_claim: false,
        predictor_effect_claim: false,
        cap_failure_rescued_by_secondary_metric: false
      }
    }
' > "${root}/classification.json"

jq -e '.classification == "CAP_PASS" or .classification == "DIRECTIONAL_BALANCE_GAIN_ONLY" or .classification == "NO_BALANCE_GAIN"' \
  "${root}/classification.json" > /dev/null
cat > "${root}/security.txt" <<EOF
prediction_pair_files_opened=0
prediction_values_read_or_aggregated=false
label_grade_outcome_winner_read=false
raw_archive_payload_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF
sha256sum \
  "${artifact}/SHA256SUMS" \
  "${artifact}/guard_a.json" \
  "${artifact}/guard_verify_a.json" \
  "${artifact}/forward_a.json" \
  "${artifact}/forward_verify_a.json" \
  "${common_path}" \
  > "${root}/result_bindings.sha256"
printf 'TASK_BALANCE_STRUCTURAL_EXTENSION_887_COMPLETE\n' > "${root}/COMPLETE"
(
  cd "${root}"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
)
chmod -R a-w "${root}"
trap - EXIT

cat "${root}/classification.json"
sha256sum "${root}/SHA256SUMS"
echo 'access_attestation=structural_only_no_prediction_values_or_outcomes'
