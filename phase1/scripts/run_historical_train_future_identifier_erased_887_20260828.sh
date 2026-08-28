#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_historical_train_future_identifier_erased_887_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly output=$1
readonly expected_commit=$2
readonly state=/research/d7/spc/yzyang4/prospective_decision_v1
readonly snapshot_sha=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697
readonly snapshot=${state}/snapshots/${snapshot_sha}
readonly registry_sha=37e41460c85661fd9afc6f8789a065088a9da88dde027b955ff4bc366d5bbcd8
readonly runs_sha=510d81820d7825fc6baa6db562b2371e50eb7d71d04cb1cc0bd17d095d6cdbca
readonly summary_sha=2f28b5b53cca5d6ea5ebf16f746a70f9c1de0e3197487a6ed78d41b4cb611302
readonly cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75
readonly protocol=phase1/historical_train_future_identifier_erased_887_protocol_v1.json
readonly protocol_sha=aa3b232c732c53bb24bf2fbac6932276d458f2e6a6ae20321edee0ff2d04ca1b
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test "$(git rev-parse HEAD)" = "${expected_commit}"
test ! -e "${output}"
test -d "${snapshot}"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test "$(sha256sum "${snapshot}/intake_registry.jsonl" | awk '{print $1}')" = "${registry_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
test "$(sha256sum "${snapshot}/accumulator/summary.json" | awk '{print $1}')" = "${summary_sha}"
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
mkdir -p "${output}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${output}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

cat > "${output}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=fixed v11 train to exact 435-run future identifier/literal-erased overlap; PASS
03_population=5519 historical endpoints versus fingerprintable endpoints in ${snapshot_sha}; PASS
04_inputs=historical cards/pairs plus hash-bound blind snapshot manifests only; PASS
05_representation=keywords/operators preserved,other names/numbers/strings erased,token5gram,BLAKE2b128,min20; PASS
06_thresholds=17/20 primary,19/20 sensitivity,no task/run prefilter,no sensitivity rescue; PASS
07_interpretation=ZERO_IDENTIFIER_ERASED_LINKS then LOW_IDENTIFIER_ERASED_OVERLAP_ONLY then INTEGRITY_GATE_FAIL; PASS
08_controls=alpha rename positive,unrelated negative,producer A/B,non-importing verifier A/B,256x256 brute force; PASS
09_randomness=none,PYTHONHASHSEED=0,numeric threads=1,exact integer threshold; PASS
10_resources=CPU only,1800-second command timeout,32-GiB virtual memory,GPU/API/model-fit/base-update 0/0/0/0; PASS
11_security=trace and credential gates,no endpoint/code/task/run identities emitted; PASS
12_forbidden=prospective label,outcome,prediction,accuracy,effect,utility,raw senior archives,historical label fields as inputs; PASS
13_failure=immutable FAILED_RC,no population,representation,threshold,task,run,subset or interpretation rescue; PASS
EOF

git lfs pull fork --include='phase1/cards_current_v11.jsonl' --exclude='' \
  > "${output}/lfs_pull.txt" 2>&1
test "$(stat -c '%s' phase1/cards_current_v11.jsonl)" = 305750663
test "$(sha256sum phase1/cards_current_v11.jsonl | awk '{print $1}')" = "${cards_sha}"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

git status --porcelain=v1 > "${output}/git_status_before.txt"
test ! -s "${output}/git_status_before.txt"
"${python}" -m pytest -q \
  phase1/tests/test_historical_train_future_identifier_erased_overlap.py \
  phase1/tests/test_historical_train_future_fuzzy_overlap.py \
  phase1/tests/test_historical_train_future_identifier_erased_overlap_result.py \
  phase1/tests/test_historical_train_future_fuzzy_overlap_result.py \
  > "${output}/focused_tests.txt"
"${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

producer=(
  "${python}" -m phase1.audit_historical_train_future_identifier_erased_overlap
  --repo-root "$(pwd)"
  --state-root "${state}"
  --snapshot-root "${snapshot}"
  --source-commit "${expected_commit}"
)
/usr/bin/time -v -o "${output}/producer_a.time.txt" \
  timeout 1800s strace -f -e trace=file -o "${output}/producer_a.trace" \
  "${producer[@]}" --output "${output}/producer_a.json" \
  > "${output}/producer_a.stdout"
timeout 1800s "${producer[@]}" --output "${output}/producer_b.json" \
  > "${output}/producer_b.stdout"
cmp "${output}/producer_a.json" "${output}/producer_b.json"

verifier=(
  "${python}" -m phase1.verify_historical_train_future_identifier_erased_overlap
  --repo-root "$(pwd)"
  --state-root "${state}"
  --snapshot-root "${snapshot}"
)
/usr/bin/time -v -o "${output}/verifier_a.time.txt" \
  timeout 1800s strace -f -e trace=file -o "${output}/verifier_a.trace" \
  "${verifier[@]}" --receipt "${output}/producer_a.json" \
  --output "${output}/verification_a.json" > "${output}/verifier_a.stdout"
timeout 1800s "${verifier[@]}" --receipt "${output}/producer_b.json" \
  --output "${output}/verification_b.json" > "${output}/verifier_b.stdout"
cmp "${output}/verification_a.json" "${output}/verification_b.json"

for trace in "${output}/producer_a.trace" "${output}/verifier_a.trace"; do
  forbidden_hits=$(grep -Eic \
    '/external/senior_data/|label_vault|/outcomes?/|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|/\.env([" ]|$)' \
    "${trace}" || true)
  test "${forbidden_hits}" = 0
done

jq -e \
  --arg commit "${expected_commit}" \
  --arg snapshot "${snapshot_sha}" '
  .protocol == "historical_train_to_prospective_identifier_erased_overlap_v1"
  and .source_commit == $commit
  and .snapshot_sha256 == $snapshot
  and .historical_scope.union_endpoints == 5519
  and .historical_scope.union_runs == 333
  and .prospective_scope.observed_runs == 435
  and .prospective_scope.observed_endpoints == 11906
  and .representation_contract.name == "python_token_identifier_erased_v1"
  and .historical_scope.historical_label_or_observation_fields_used == false
  and .interpretation_contract.historical_label_or_observation_fields_used == false
  and .security.prospective_label_vault_opened == false
  and .security.prospective_outcome_files_opened == []
  and .security.prediction_values_read == false
  and .security.code_or_identity_values_emitted == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
' "${output}/producer_a.json" > /dev/null
jq -e '
  .protocol == "independent_historical_train_to_prospective_identifier_erased_overlap_v1"
  and .producer_aggregate_matches == true
  and .subset_bruteforce_matches == true
  and .imports_new_producer_code == false
  and .historical_label_or_observation_fields_used == false
  and .prospective_outcomes_read == false
  and .prediction_values_read == false
' "${output}/verification_a.json" > /dev/null

"${python}" - \
  "${output}/producer_a.json" "${output}/verification_a.json" \
  "${output}/focused_tests.txt" "${output}/full_tests.txt" \
  "${output}/formal_summary.json" <<'PY'
import json
import pathlib
import re
import sys

producer_path, verifier_path, focused_path, full_path, output_path = map(
    pathlib.Path, sys.argv[1:]
)
producer = json.loads(producer_path.read_text(encoding="utf-8"))
verifier = json.loads(verifier_path.read_text(encoding="utf-8"))

def counts(path: pathlib.Path) -> dict[str, int]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    summary = next((line for line in reversed(lines) if " passed" in line), "")
    values = {"passed": 0, "skipped": 0, "warnings": 0}
    for key in values:
        match = re.search(rf"(\d+) {key}", summary)
        if match:
            values[key] = int(match.group(1))
    return values

primary = producer["primary_jaccard_0_85"]
strict = producer["strict_jaccard_0_95"]
gate = producer["pre_registered_gate"]
if gate["strong_low_identifier_erased_overlap_support"] and primary["near_duplicate_pairs"] == 0:
    classification = "ZERO_IDENTIFIER_ERASED_LINKS"
elif gate["strong_low_identifier_erased_overlap_support"]:
    classification = "LOW_IDENTIFIER_ERASED_OVERLAP_ONLY"
else:
    classification = "INTEGRITY_GATE_FAIL"
payload = {
    "protocol": "historical-train-future-identifier-erased-887-extension-v1",
    "status": "FORMAL_PROVISIONAL_IDENTIFIER_ERASED_OVERLAP_887_COMPLETE",
    "classification": classification,
    "source_commit": producer["source_commit"],
    "snapshot_sha256": producer["snapshot_sha256"],
    "historical_endpoints": producer["historical_scope"]["union_endpoints"],
    "historical_runs": producer["historical_scope"]["union_runs"],
    "historical_fingerprinted_endpoints": producer["historical_fingerprinting"]["fingerprinted_endpoints"],
    "historical_fingerprint_coverage": producer["historical_fingerprinting"]["coverage"],
    "prospective_runs": producer["prospective_scope"]["observed_runs"],
    "prospective_endpoints": producer["prospective_scope"]["observed_endpoints"],
    "prospective_fingerprinted_endpoints": producer["prospective_fingerprinting"]["fingerprinted_endpoints"],
    "prospective_fingerprint_coverage": producer["prospective_fingerprinting"]["coverage"],
    "primary_candidate_pairs": primary["candidate_pairs_exactly_checked"],
    "primary_near_duplicate_pairs": primary["near_duplicate_pairs"],
    "primary_same_task_pairs": primary["same_task_pairs"],
    "primary_cross_task_pairs": primary["cross_task_pairs"],
    "primary_historical_affected_endpoints": primary["historical_affected_endpoints"],
    "primary_prospective_affected_endpoints": primary["prospective_affected_endpoints"],
    "primary_cross_task_prospective_affected_endpoints": primary["cross_task_prospective_affected_endpoints"],
    "primary_components": primary["components"],
    "primary_largest_component_endpoints": primary["largest_component_endpoints"],
    "primary_largest_component_tasks": primary["largest_component_tasks"],
    "primary_large_multitask_components": primary["large_multitask_components"],
    "strict_near_duplicate_pairs": strict["near_duplicate_pairs"],
    "strict_prospective_affected_endpoints": strict["prospective_affected_endpoints"],
    "gate_checks": gate["checks"],
    "strong_low_identifier_erased_overlap_support": gate["strong_low_identifier_erased_overlap_support"],
    "producer_ab_byte_identical": True,
    "verifier_ab_byte_identical": True,
    "independent_aggregate_matches": verifier["producer_aggregate_matches"],
    "subset_bruteforce_matches": verifier["subset_bruteforce_matches"],
    "focused_tests": counts(focused_path),
    "full_tests": counts(full_path),
    "forbidden_path_hits": 0,
    "credential_hits": 0,
    "historical_label_or_observation_fields_used": False,
    "prospective_outcomes_read": False,
    "prediction_values_read": False,
    "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    "semantic_equivalence_proven": False,
    "pretraining_contamination_absence_proven": False,
    "closure_rerun_required": True,
}
output_path.write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
PY

credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=credential_scan_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
cat > "${output}/access_attestation.txt" <<EOF
production_forbidden_path_hits=0
boundary_aware_credential_file_hits=0
credential_filename_hits=0
historical_label_or_observation_fields_used=false
endpoint_code_task_run_identities_emitted=false
prospective_label_outcome_prediction_values_read=false
raw_senior_archives_opened=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test "$(sha256sum "${snapshot}/intake_registry.jsonl" | awk '{print $1}')" = "${registry_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_first960_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
test "$(sha256sum "${snapshot}/accumulator/summary.json" | awk '{print $1}')" = "${summary_sha}"
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
cat "${output}/formal_summary.json"
sha256sum "${output}/producer_a.json" "${output}/verification_a.json" "${output}/SHA256SUMS"
printf '%s\n' FORMAL_HISTORICAL_IDENTIFIER_ERASED_887_COMPLETE
