#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_prospective_identifier_erased_clone_887_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
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
readonly protocol=phase1/prospective_identifier_erased_clone_887_protocol_v1.json
readonly protocol_sha=a0c5e73c2e6bde6eed920c69909d13d6b0207271758e327b30eb0b346e654f52
readonly representation=python_token_identifier_erased_v1
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test "$(git rev-parse HEAD)" = "${expected_commit}"
test ! -e "${output}"
test -d "${snapshot}"
test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test "$(sha256sum "${snapshot}/intake_registry.jsonl" | awk '{print $1}')" = "${registry_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
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
02_question=internal identifier/literal-erased near-duplicate locality in exact 435-run snapshot; PASS
03_population=${snapshot_sha},435 runs,11906 endpoints,34 tasks,closure false; PASS
04_inputs=registry ${registry_sha},runs ${runs_sha},summary ${summary_sha},protocol ${protocol_sha}; PASS
05_representation=keywords/operators preserved,other names/numbers/strings erased,token5gram,BLAKE2b128,min20; PASS
06_thresholds=17/20 primary,19/20 sensitivity,no task/run prefilter,no sensitivity rescue; PASS
07_interpretation=STRICT_LINEAGE_LOCAL_PASS then LOW_CROSS_RUN_ONLY then INTEGRITY_GATE_FAIL; PASS
08_controls=alpha rename positive,unrelated negative,producer A/B,non-importing verifier A/B,384 brute force; PASS
09_randomness=none,PYTHONHASHSEED=0,numeric threads=1,exact integer threshold; PASS
10_resources=CPU only,1800-second command timeout,32-GiB virtual memory,GPU/API/model-fit/base-update 0/0/0/0; PASS
11_security=trace and credential gates,no task/run/card/code identities emitted; PASS
12_forbidden=label,outcome,prediction,accuracy,effect,utility,raw senior archives; PASS
13_failure=immutable FAILED_RC,no population,representation,threshold,subset,task or interpretation rescue; PASS
EOF

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
  phase1/tests/test_audit_prospective_fuzzy_code_clones.py \
  phase1/tests/test_historical_train_future_identifier_erased_overlap.py \
  > "${output}/focused_tests.txt"
"${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

producer=(
  "${python}" -m phase1.audit_prospective_fuzzy_code_clones
  --state-root "${state}"
  --snapshot-root "${snapshot}"
  --cohort-run-target 960
  --source-commit "${expected_commit}"
  --representation "${representation}"
)
/usr/bin/time -v -o "${output}/producer_a.time.txt" \
  timeout 1800s strace -f -e trace=file -o "${output}/producer_a.trace" \
  "${producer[@]}" --output "${output}/producer_a.json" \
  > "${output}/producer_a.stdout"
timeout 1800s "${producer[@]}" --output "${output}/producer_b.json" \
  > "${output}/producer_b.stdout"
cmp "${output}/producer_a.json" "${output}/producer_b.json"

verifier=(
  "${python}" -m phase1.verify_prospective_fuzzy_code_clones
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
  --arg snapshot "${snapshot_sha}" \
  --arg registry "${registry_sha}" \
  --arg runs "${runs_sha}" \
  --arg summary "${summary_sha}" \
  --arg representation "${representation}" '
  .protocol == "prospective_identifier_erased_fuzzy_code_clone_audit_v1"
  and .snapshot_sha256 == $snapshot
  and .scope.observed_runs == 435
  and .scope.observed_endpoints == 11906
  and .inputs.intake_registry_sha256 == $registry
  and .inputs.provisional_runs_sha256 == $runs
  and .inputs.accumulator_summary_sha256 == $summary
  and .fingerprinting.representation == $representation
  and .interpretation_contract.identifier_and_literal_erasure_used == true
  and .interpretation_contract.semantic_clone_absence_claimed == false
  and .security.label_vault_opened == false
  and .security.outcome_files_opened == []
  and .security.scorer_prediction_files_opened == []
  and .security.task_card_or_run_values_emitted == false
  and .security.gpu_calls == 0
  and .security.api_calls == 0
  and .security.model_fits == 0
  and .security.base_llm_updates == 0
' "${output}/producer_a.json" > /dev/null
jq -e '
  .protocol == "independent_prospective_identifier_erased_fuzzy_code_clone_verifier_v1"
  and .representation == "python_token_identifier_erased_v1"
  and .producer_aggregate_matches == true
  and .subset_bruteforce_matches == true
  and .imports_producer_code == false
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
if gate["strict_lineage_local_support"]:
    classification = "STRICT_LINEAGE_LOCAL_PASS"
elif gate["strong_low_fuzzy_clone_support"]:
    classification = "LOW_CROSS_RUN_ONLY"
else:
    classification = "INTEGRITY_GATE_FAIL"
payload = {
    "protocol": "prospective-identifier-erased-clone-887-formal-v1",
    "status": "FORMAL_PROVISIONAL_IDENTIFIER_ERASED_INTERNAL_CLONE_AUDIT_COMPLETE",
    "classification": classification,
    "source_commit": producer["source_commit"],
    "snapshot_sha256": producer["snapshot_sha256"],
    "observed_runs": producer["scope"]["observed_runs"],
    "observed_endpoints": producer["scope"]["observed_endpoints"],
    "fingerprinted_endpoints": producer["fingerprinting"]["fingerprinted_endpoints"],
    "fingerprint_coverage": producer["fingerprinting"]["coverage"],
    "primary_candidate_pairs": primary["candidate_pairs_exactly_checked"],
    "primary_near_duplicate_pairs": primary["near_duplicate_pairs"],
    "primary_relation_pair_counts": primary["relation_pair_counts"],
    "primary_cross_run_pairs": primary["cross_run_pairs"],
    "primary_cross_run_affected_endpoints": primary["cross_run_affected_endpoints"],
    "primary_cross_run_affected_endpoint_fraction": primary["cross_run_affected_endpoint_fraction"],
    "primary_cross_task_affected_endpoints": primary["cross_task_affected_endpoints"],
    "primary_cross_task_affected_endpoint_fraction": primary["cross_task_affected_endpoint_fraction"],
    "primary_cross_run_components": primary["cross_run_components"],
    "primary_largest_cross_run_component_endpoints": primary["largest_cross_run_component_endpoints"],
    "primary_largest_cross_run_component_tasks": primary["largest_cross_run_component_tasks"],
    "primary_large_multitask_components": primary["large_multitask_components"],
    "strict_near_duplicate_pairs": strict["near_duplicate_pairs"],
    "strict_cross_run_pairs": strict["cross_run_pairs"],
    "strict_cross_run_affected_endpoints": strict["cross_run_affected_endpoints"],
    "gate_checks": gate["checks"],
    "strong_low_fuzzy_clone_support": gate["strong_low_fuzzy_clone_support"],
    "strict_lineage_local_support": gate["strict_lineage_local_support"],
    "producer_ab_byte_identical": True,
    "verifier_ab_byte_identical": True,
    "independent_aggregate_matches": verifier["producer_aggregate_matches"],
    "subset_bruteforce_matches": verifier["subset_bruteforce_matches"],
    "focused_tests": counts(focused_path),
    "full_tests": counts(full_path),
    "forbidden_path_hits": 0,
    "credential_hits": 0,
    "prospective_outcomes_read": False,
    "prediction_values_read": False,
    "gpu_api_model_fit_base_update": [0, 0, 0, 0],
    "semantic_equivalence_proven": False,
    "closure_rerun_required": True,
}
output_path.write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=credential_scan_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
printf '%s\n' \
  'production_forbidden_path_hits=0' \
  'boundary_aware_credential_file_hits=0' \
  'credential_filename_hits=0' \
  'task_run_card_code_identities_emitted=false' \
  'prospective_label_outcome_prediction_values_read=false' \
  'raw_senior_archives_opened=false' \
  'gpu_api_model_fit_base_update=0/0/0/0' \
  > "${output}/access_attestation.txt"

test "$(tr -d '\r\n' < "${state}/LATEST")" = "${snapshot_sha}"
test "$(sha256sum "${snapshot}/intake_registry.jsonl" | awk '{print $1}')" = "${registry_sha}"
test "$(sha256sum "${snapshot}/accumulator/provisional_runs.jsonl" | awk '{print $1}')" = "${runs_sha}"
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
echo FORMAL_PROSPECTIVE_IDENTIFIER_ERASED_CLONE_887_COMPLETE
