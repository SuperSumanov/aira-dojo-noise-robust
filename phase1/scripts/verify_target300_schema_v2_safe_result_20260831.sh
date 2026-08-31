#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u

readonly result_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
readonly attempt=${result_root}/target300_schema_v2_attempt_1
readonly anchor=${result_root}/FIRST_CLOSED_COHORT_ANCHOR.json
readonly release=4a68c83fba90655e9d60344081ae2b53b7c36104
readonly candidate=30945550b6b12a146dadd6eda733c3b676b467aef86636ae31ac59813133104f
readonly producer_sha=0273b1e1d6db0e8acc2d90682d03cbcd1da88dfe1cf3eabf84f76619c871d25f

test -f "${attempt}/COMPLETE" && test ! -e "${attempt}/FAILED_RC" && test ! -e "${attempt}/DEPLOY_FAILED_RC"
test "$(tr -d '\r\n' <"${attempt}/formal_rc.txt")" = 0
mapfile -t results < <(find "${result_root}" -mindepth 1 -maxdepth 1 -type d -name '4a68c83-30945550b6b1-*' -print | LC_ALL=C sort)
test "${#results[@]}" -eq 1
formal=${results[0]}
test -d "${formal}" && test ! -L "${formal}"
test -f "${formal}/COMPLETE"
test -z "$(find "${formal}" -perm /022 -print -quit)"
(cd "${formal}" && sha256sum -c SHA256SUMS >/dev/null)
test ! -s "${formal}/producer_reproducibility.diff"
test ! -s "${formal}/verifier_reproducibility.diff"
diff -r "${formal}/producer_a" "${formal}/producer_b" >/dev/null
cmp "${formal}/verification_a.json" "${formal}/verification_b.json"
test "$(tr -d '\r\n' <"${formal}/forbidden_open_count.txt")" = 0
test "$(tr -d '\r\n' <"${formal}/filename_scan_count.txt")" = 0
test "$(tr -d '\r\n' <"${formal}/content_scan_count.txt")" = 0
test ! -s "${formal}/status_before.txt"
test ! -s "${formal}/status_after.txt"
printf 'FORMAL_RESULT_BASENAME=%s\n' "$(basename "${formal}")"

/research/d7/spc/yzyang4/venvs/exp/bin/python - \
  "${formal}/producer_a/summary.json" "${formal}/verification_a.json" \
  "${candidate}" "${release}" "${producer_sha}" "${anchor}" <<'PY'
from __future__ import annotations
import hashlib
import json
import pathlib
import sys

summary_path = pathlib.Path(sys.argv[1])
verification_path = pathlib.Path(sys.argv[2])
candidate, release, producer_sha = sys.argv[3:6]
anchor = pathlib.Path(sys.argv[6])
summary = json.loads(summary_path.read_text(encoding="utf-8"))
verification = json.loads(verification_path.read_text(encoding="utf-8"))
status = summary["status"]
assert status in {
    "FUTURE_COHORT_COLLECTING",
    "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD",
}
inventory = summary["inventory"]
closure = summary["closure"]
inputs = summary["inputs"]
blindness = summary["blindness"]
previous = closure["append_only_previous"]
assert summary["source_commit"] == release
assert inputs["latest_sha256"] == candidate
assert summary["implementation"]["script_sha256"] == producer_sha
assert closure["accepted_unique_physical_run_target"] == 300
assert previous["previous_runs"] == 193
assert previous["previous_archives"] == 60
assert previous["exact_prefix_survived"] is True
assert verification["implementation_independent_of_producer"] is True
assert verification["producer_module_imported"] is False
assert verification["selected_archives"] == inventory["selected_archives"]
assert verification["selected_physical_runs"] == inventory["selected_physical_runs"]
assert verification["selected_tasks"] == inventory["selected_tasks"]
for key in (
    "raw_archive_payload_opened", "blind_code_view_opened", "label_vault_opened",
    "score_directory_opened", "score_or_outcome_opened", "truth_support_computed",
    "replay_submission_authorized",
):
    assert blindness[key] is False
    assert verification[key] is False
boundary_present = closure["boundary_archive"] is not None
if status == "FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD":
    assert boundary_present
    assert closure["remaining_runs_to_target"] == 0
    assert verification["status"] == "PASS_IDENTITY_CLOSED_TRUTH_UNREAD"
    assert anchor.is_file() and not anchor.is_symlink()
else:
    assert not boundary_present
    assert closure["remaining_runs_to_target"] > 0
    assert verification["status"] == "PASS_COLLECTING_TRUTH_UNREAD"
    assert not anchor.exists()
print("SAFE_RESULT_STATUS=PASS")
print(f"COHORT_STATUS={status}")
print(f"VERIFIER_STATUS={verification['status']}")
print(f"SELECTED_RUNS={inventory['selected_physical_runs']}")
print(f"SELECTED_ARCHIVES={inventory['selected_archives']}")
print(f"SELECTED_TASKS={inventory['selected_tasks']}")
print(f"REMAINING_RUNS={closure['remaining_runs_to_target']}")
print(f"BOUNDARY_PRESENT={str(boundary_present).lower()}")
print(f"OBSERVED_FUTURE_ARCHIVES={inventory['observed_future_archives']}")
print(f"FUTURE_TRANSACTIONS={inventory['future_transactions']}")
print(f"SETTLED_ARCHIVE_PREFIX={closure['settled_archive_prefix']}")
print(f"STRUCTURAL_REJECTIONS_IN_PREFIX={closure['structurally_rejected_in_settled_prefix']}")
print(f"PENDING_HEAD_PRESENT={str(closure['pending_head'] is not None).lower()}")
print(f"PREVIOUS_RUNS={previous['previous_runs']}")
print(f"PREVIOUS_ARCHIVES={previous['previous_archives']}")
print(f"EXACT_PREFIX_SURVIVED={str(previous['exact_prefix_survived']).lower()}")
print(f"SUMMARY_SHA256={hashlib.sha256(summary_path.read_bytes()).hexdigest()}")
print(f"VERIFICATION_SHA256={hashlib.sha256(verification_path.read_bytes()).hexdigest()}")
print("OUTCOMES_READ=false")
print("IDENTITIES_READ=false")
PY

printf 'FORMAL_MANIFEST_SHA256=%s\n' "$(sha256sum "${formal}/SHA256SUMS" | awk '{print $1}')"
printf 'FOCUSED_TEST_SUMMARY=%s\n' "$(tail -n 1 "${formal}/focused_tests.stdout")"
printf 'FULL_TEST_SUMMARY=%s\n' "$(tail -n 1 "${formal}/phase1_tests.stdout")"
printf 'FORBIDDEN_OPEN_COUNT=0\nFILENAME_SECRET_SCAN_COUNT=0\nCONTENT_SECRET_SCAN_COUNT=0\n'
printf 'PRIVATE_STDOUT_BYTES=%s\nPRIVATE_STDOUT_SHA256=%s\n' \
  "$(stat -c %s "${attempt}/formal.private.stdout")" \
  "$(sha256sum "${attempt}/formal.private.stdout" | awk '{print $1}')"
