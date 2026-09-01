#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export BLIS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

readonly source_repo=${1:?source repository required}
readonly source_commit=${2:?40-character source commit required}
readonly formal_root=${3:?new formal output root required}
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly worktree_root=/research/d7/spc/yzyang4/worktrees/evidence-index-v10-${source_commit:0:12}
readonly protocol_rel=phase1/decision_corpus_evidence_index_v10_protocol_v1.json
readonly protocol_sha=a210f17f0ded3c64b795a6d898032e04be44ae403b3585eafe527bff3e12534d
readonly fetch_remote=${EVIDENCE_V10_FETCH_REMOTE:-fork}

readonly -a input_relatives=(
  "$protocol_rel"
  phase1/results/decision_corpus_evidence_index_v9_20260829_f108812/formal/index.json
  phase1/results/archive_disposition_longitudinal_replication_v2_20260831_43ce72a/a/result.json
  phase1/results/archive_disposition_longitudinal_replication_v2_20260831_43ce72a/a/independent_verification.json
  phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/result.json
  phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/independent_verification.json
  phase1/results/wl_snapshot_chain_20260901_e9e12c63/structural_summary.json
  phase1/results/wl_snapshot_chain_20260901_e9e12c63/snapshot_chain_receipt.json
  phase1/results/archive_rejection_support_census_20260902_7ad0164/result.json
  phase1/results/archive_rejection_support_census_20260902_7ad0164/independent_verification.json
  phase1/results/archive_rejection_support_floor_20260902_5609a8e/result.json
  phase1/results/archive_rejection_support_floor_20260902_5609a8e/independent_verification.json
  phase1/results/archive_rejection_support_floor_20260902_5609a8e/prior_evidence_crosswalk.json
)

failure_receipt() {
  rc=$?
  if (( rc != 0 )) && test -d "$formal_root"; then
    printf '%s\n' "$rc" >"$formal_root/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT

write_input_hashes() {
  local output=$1
  local relative
  : >"$output"
  for relative in "${input_relatives[@]}"; do
    test -f "$worktree_root/$relative"
    test ! -L "$worktree_root/$relative"
    printf '%s  %s\n' "$(sha256sum "$worktree_root/$relative" | awk '{print $1}')" "$relative" \
      >>"$output"
  done
}

[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
test -d "$source_repo/.git"
test -x "$python_bin"
"$python_bin" -c 'import pytest'
command -v grep >/dev/null
command -v strace >/dev/null
test ! -e "$formal_root"
test ! -e "$worktree_root"
mkdir -p "$formal_root"

cat >"$formal_root/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_goal=extend Evidence Index v9 by four distinct public audit entries and one non-distinct reconstruction record; PASS
03_estimand=post-result claim accounting and evidence de-duplication with no new scientific readout; PASS
04_inputs=exact public v9 index plus eleven published aggregate artifacts bound by SHA256; PASS
05_forbidden=no first960 Target300 Target522 values raw senior archives candidate identities predictor effect or search utility; PASS
06_population=published aggregate-only benchmark audit packages through the 517-run structural snapshot; PASS
07_controls=sixteen v9 entries unchanged independent verifier A/B and nineteen shared 0KI/0KW numeric fields exact; PASS
08_failure=any source hash assertion duplicate signature reconstruction pointer status or security drift emits no index; PASS
09_randomness=none deterministic JSON with duplicate builder and verifier executions; PASS
10_resources=CPU only one thread GPU API model-fit base-update 0/0/0/0; PASS
11_duration=focused evidence-index tests full phase1 tests builder verifier and traces under one CPU process; PASS
12_security=fresh detached no-smudge worktree input hashes before/after forbidden-open network and secret-shape scans; PASS
13_promotion=first960 remains provisional and support-floor reconstruction cannot count as distinct evidence; PASS
EOF
test "$(wc -l <"$formal_root/preflight_13.txt")" = 13
cat >"$formal_root/resource_limits.txt" <<EOF
OMP_NUM_THREADS=$OMP_NUM_THREADS
OPENBLAS_NUM_THREADS=$OPENBLAS_NUM_THREADS
MKL_NUM_THREADS=$MKL_NUM_THREADS
BLIS_NUM_THREADS=$BLIS_NUM_THREADS
NUMEXPR_NUM_THREADS=$NUMEXPR_NUM_THREADS
VECLIB_MAXIMUM_THREADS=$VECLIB_MAXIMUM_THREADS
TOKENIZERS_PARALLELISM=$TOKENIZERS_PARALLELISM
EOF

git -C "$source_repo" fetch "$fetch_remote" phase1-value-critic \
  >"$formal_root/fetch.stdout" 2>"$formal_root/fetch.stderr"
git -C "$source_repo" cat-file -e "$source_commit^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$source_repo" worktree add --detach "$worktree_root" "$source_commit" \
  >"$formal_root/worktree.stdout" 2>"$formal_root/worktree.stderr"
test "$(git -C "$worktree_root" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$worktree_root" status --porcelain --untracked-files=all)"
printf '%s\n' "$source_commit" >"$formal_root/source_commit.txt"
printf '%s\n' "$worktree_root" >"$formal_root/worktree_path.txt"
test "$(sha256sum "$worktree_root/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"
write_input_hashes "$formal_root/input_hashes_before.txt"
test "$(wc -l <"$formal_root/input_hashes_before.txt")" = "${#input_relatives[@]}"

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q phase1/tests/test_decision_corpus_evidence_index*.py
) >"$formal_root/focused_tests.txt" 2>"$formal_root/focused_tests.stderr"

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q phase1/tests
) >"$formal_root/full_tests.txt" 2>"$formal_root/full_tests.stderr"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/build_decision_corpus_evidence_index_v10.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/index_${suffix}.json" \
    >"$formal_root/builder_${suffix}.stdout" 2>"$formal_root/builder_${suffix}.stderr"
done
cmp "$formal_root/index_a.json" "$formal_root/index_b.json"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/verify_decision_corpus_evidence_index_v10.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/index_a.json" \
    --output "$formal_root/verifier_${suffix}.json" \
    >"$formal_root/verifier_${suffix}.stdout" 2>"$formal_root/verifier_${suffix}.stderr"
done
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_b.json"

strace -f -qq -e trace=openat -o "$formal_root/open_trace.txt" \
  "$python_bin" "$worktree_root/phase1/build_decision_corpus_evidence_index_v10.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/index_trace.json" \
    >"$formal_root/trace_builder.stdout" 2>"$formal_root/trace_builder.stderr"
cmp "$formal_root/index_a.json" "$formal_root/index_trace.json"

grep -E "/prospective_decision_v1/|/score-channel-future-identity-cohort/|/external/senior_data/|/\.env([./\"]|$)|decision_clean_b[0-9]|cards_cur\.jsonl" \
  "$formal_root/open_trace.txt" >"$formal_root/forbidden_open_hits.txt" || true
test ! -s "$formal_root/forbidden_open_hits.txt"

strace -f -qq -e trace=network -o "$formal_root/network_trace.txt" \
  "$python_bin" "$worktree_root/phase1/verify_decision_corpus_evidence_index_v10.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/index_a.json" \
    --output "$formal_root/verifier_trace.json" \
    >"$formal_root/trace_verifier.stdout" 2>"$formal_root/trace_verifier.stderr"
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_trace.json"
test ! -s "$formal_root/network_trace.txt"

write_input_hashes "$formal_root/input_hashes_after.txt"
cmp "$formal_root/input_hashes_before.txt" "$formal_root/input_hashes_after.txt"
test -z "$(git -C "$worktree_root" status --porcelain --untracked-files=all)"

cat >"$formal_root/access_attestation.txt" <<EOF
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_card_code_edge_or_row_identities_emitted=false
row_level_release_created=false
accuracy_effect_or_search_utility_computed=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

find "$formal_root" -type f \
  \( -iname '*.env' -o -iname '*api*key*' -o -iname '*secret*' -o -iname '*credential*' \) \
  -printf '%P\n' >"$formal_root/artifact_filename_scan.txt"
test ! -s "$formal_root/artifact_filename_scan.txt"
set +e
grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' \
  "$formal_root" >"$formal_root/artifact_content_scan.txt"
content_scan_rc=$?
set -e
test "$content_scan_rc" = 1
test ! -s "$formal_root/artifact_content_scan.txt"

index_sha=$(sha256sum "$formal_root/index_a.json" | awk '{print $1}')
verifier_sha=$(sha256sum "$formal_root/verifier_a.json" | awk '{print $1}')
distinct_entries=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["total_distinct_entry_count"])' "$formal_root/verifier_a.json")
distinct_added=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["distinct_entries_added"])' "$formal_root/verifier_a.json")
reconstructions=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["reconstruction_records_added"])' "$formal_root/verifier_a.json")
duplicates_counted=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["duplicate_claims_counted_as_distinct"])' "$formal_root/verifier_a.json")
shared_fields=$("$python_bin" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["shared_numeric_fields_crosschecked"])' "$formal_root/verifier_a.json")
focused_tail=$(tail -n 1 "$formal_root/focused_tests.txt")
full_tail=$(tail -n 1 "$formal_root/full_tests.txt")
cat >"$formal_root/formal_summary.json" <<EOF
{
  "protocol": "decision-corpus-evidence-index-v10-formal-v1",
  "status": "FORMAL_CLAIM_DEDUPLICATED_EVIDENCE_INDEX_V10_COMPLETE",
  "source_commit": "$source_commit",
  "protocol_sha256": "$protocol_sha",
  "index_sha256": "$index_sha",
  "independent_verification_sha256": "$verifier_sha",
  "index_status": "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960",
  "total_distinct_entry_count": $distinct_entries,
  "distinct_entries_added": $distinct_added,
  "reconstruction_records_added": $reconstructions,
  "duplicate_claims_counted_as_distinct": $duplicates_counted,
  "shared_numeric_fields_crosschecked": $shared_fields,
  "source_v9_entries_preserved_without_modification": 16,
  "builder_ab_byte_identical": true,
  "verifier_ab_byte_identical": true,
  "input_hashes_before_after_identical": true,
  "focused_test_tail": "$focused_tail",
  "full_test_tail": "$full_tail",
  "forbidden_open_hits": 0,
  "network_calls": 0,
  "credential_filename_hits": 0,
  "credential_content_hits": 0,
  "credential_content_scanner_rc": 1,
  "prospective_values_read": false,
  "raw_senior_archives_opened": false,
  "row_level_release_created": false,
  "cpu_thread_limit": 1,
  "gpu_api_model_fit_base_update": [0, 0, 0, 0]
}
EOF
"$python_bin" -m json.tool "$formal_root/formal_summary.json" >/dev/null

(
  cd "$formal_root"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$formal_root"
trap - EXIT
printf 'formal_root=%s\n' "$formal_root"
printf 'manifest_sha256=%s\n' "$(sha256sum "$formal_root/SHA256SUMS" | awk '{print $1}')"
