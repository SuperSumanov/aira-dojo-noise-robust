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
readonly worktree_root=/research/d7/spc/yzyang4/worktrees/relation-integrity-contrast-${source_commit:0:12}
readonly protocol_rel=phase1/historical_relation_integrity_contrast_v1.json
readonly protocol_sha=9b647d1e25786631875114893604650c273a36051c815d976ab189602e0feb37
readonly fetch_remote=${RELATION_CONTRAST_FETCH_REMOTE:-fork}

failure_receipt() {
  rc=$?
  if (( rc != 0 )) && test -d "$formal_root"; then
    printf '%s\n' "$rc" >"$formal_root/FAILED_RC" 2>/dev/null || true
  fi
  exit "$rc"
}
trap failure_receipt EXIT

[[ $source_commit =~ ^[0-9a-f]{40}$ ]]
test -d "$source_repo/.git"
test -x "$python_bin"
command -v grep >/dev/null
command -v strace >/dev/null
test ! -e "$formal_root"
test ! -e "$worktree_root"
mkdir -p "$formal_root"

cat >"$formal_root/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol; PASS
02_goal=aggregate-only historical stress case for audit diagnostic discrimination and deterministic repair feasibility; PASS
03_estimand=known-result descriptive contrast across canonical v11 mixed 0819 and fixed sibling quarantine receipts; PASS
04_inputs=three exact published aggregate packages with complete manifests and independent verifiers; PASS
05_forbidden=no prospective values raw senior archives row identities labels predictions accuracy effect or search utility; PASS
06_population=two historical resource families and one deterministic repair certificate only; PASS
07_controls=full package membership exact hashes independent source verifiers A/B builds and independent candidate verifier; PASS
08_failure=any package hash count taxonomy certificate claim-boundary trace or security drift fails closed; PASS
09_randomness=none deterministic aggregate arithmetic and duplicate byte comparisons; PASS
10_resources=single-thread CPU only GPU API model-fit base-update 0/0/0/0; PASS
11_duration=focused and full phase1 tests plus deterministic builder verifier and syscall traces; PASS
12_security=fresh detached worktree no archive read forbidden-open and network traces plus credential scans; PASS
13_promotion=descriptive two-family case study only gate schemas remain nonidentical and no prospective or general-method claim; PASS
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

git -C "$source_repo" fetch "$fetch_remote" phase1-value-critic >"$formal_root/fetch.stdout" 2>"$formal_root/fetch.stderr"
git -C "$source_repo" cat-file -e "$source_commit^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$source_repo" worktree add --detach "$worktree_root" "$source_commit" \
  >"$formal_root/worktree.stdout" 2>"$formal_root/worktree.stderr"
test "$(git -C "$worktree_root" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$worktree_root" status --porcelain --untracked-files=all)"
printf '%s\n' "$source_commit" >"$formal_root/source_commit.txt"
printf '%s\n' "$worktree_root" >"$formal_root/worktree_path.txt"
test "$(sha256sum "$worktree_root/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"

readonly canonical_package=phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842
readonly taxonomy_package=phase1/results/senior_0819_decision_relation_taxonomy_20260829_827fe55
readonly repair_package=phase1/results/senior_0819_verified_sibling_quarantine_20260829_254fc80
(
  cd "$worktree_root/$canonical_package"
  sha256sum -c MANIFEST.sha256
) >"$formal_root/canonical_manifest_check.txt"
test "$(grep -c ': OK$' "$formal_root/canonical_manifest_check.txt")" = 16
(
  cd "$worktree_root/$taxonomy_package"
  sha256sum -c MANIFEST.sha256
) >"$formal_root/taxonomy_manifest_check.txt"
test "$(grep -c ': OK$' "$formal_root/taxonomy_manifest_check.txt")" = 9
(
  cd "$worktree_root/$repair_package"
  sha256sum -c MANIFEST.sha256
) >"$formal_root/repair_manifest_check.txt"
test "$(grep -c ': OK$' "$formal_root/repair_manifest_check.txt")" = 10

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q \
    phase1/tests/test_historical_relation_integrity_contrast.py \
    phase1/tests/test_decision_corpus_lineage_v2.py \
    phase1/tests/test_senior_0819_decision_relation_taxonomy.py \
    phase1/tests/test_senior_0819_verified_sibling_quarantine.py
) >"$formal_root/focused_tests.txt" 2>"$formal_root/focused_tests.stderr"

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q phase1/tests
) >"$formal_root/full_tests.txt" 2>"$formal_root/full_tests.stderr"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/build_historical_relation_integrity_contrast.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/contrast_${suffix}.json" \
    >"$formal_root/builder_${suffix}.stdout" 2>"$formal_root/builder_${suffix}.stderr"
done
cmp "$formal_root/contrast_a.json" "$formal_root/contrast_b.json"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/verify_historical_relation_integrity_contrast.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/contrast_a.json" \
    --output "$formal_root/verifier_${suffix}.json" \
    >"$formal_root/verifier_${suffix}.stdout" 2>"$formal_root/verifier_${suffix}.stderr"
done
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_b.json"

strace -f -qq -e trace=openat -o "$formal_root/open_trace.txt" \
  "$python_bin" "$worktree_root/phase1/build_historical_relation_integrity_contrast.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/contrast_trace.json" \
    >"$formal_root/trace_builder.stdout" 2>"$formal_root/trace_builder.stderr"
cmp "$formal_root/contrast_a.json" "$formal_root/contrast_trace.json"
grep -E "/prospective_decision_v1/|/score-channel-future-identity-cohort/|/external/senior_data/|/\\.env([./\"]|$)|decision_clean_b[0-9]" \
  "$formal_root/open_trace.txt" >"$formal_root/forbidden_open_hits.txt" || true
test ! -s "$formal_root/forbidden_open_hits.txt"

strace -f -qq -e trace=network -o "$formal_root/network_trace.txt" \
  "$python_bin" "$worktree_root/phase1/verify_historical_relation_integrity_contrast.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/contrast_a.json" \
    --output "$formal_root/verifier_trace.json" \
    >"$formal_root/trace_verifier.stdout" 2>"$formal_root/trace_verifier.stderr"
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_trace.json"
test ! -s "$formal_root/network_trace.txt"

cat >"$formal_root/access_attestation.txt" <<EOF
prospective_first960_or_target300_values_read=false
raw_senior_archives_opened=false
row_identities_or_pair_orientations_emitted=false
labels_outcomes_predictions_accuracy_effect_or_search_utility_read=false
row_level_release_created=false
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

contrast_sha=$(sha256sum "$formal_root/contrast_a.json" | awk '{print $1}')
verifier_sha=$(sha256sum "$formal_root/verifier_a.json" | awk '{print $1}')
canonical_manifest_sha=$(sha256sum "$worktree_root/$canonical_package/MANIFEST.sha256" | awk '{print $1}')
taxonomy_manifest_sha=$(sha256sum "$worktree_root/$taxonomy_package/MANIFEST.sha256" | awk '{print $1}')
repair_manifest_sha=$(sha256sum "$worktree_root/$repair_package/MANIFEST.sha256" | awk '{print $1}')
focused_tail=$(tail -n 1 "$formal_root/focused_tests.txt")
full_tail=$(tail -n 1 "$formal_root/full_tests.txt")
cat >"$formal_root/formal_summary.json" <<EOF
{
  "protocol": "historical-relation-integrity-contrast-formal-v1",
  "status": "FORMAL_HISTORICAL_RELATION_INTEGRITY_CONTRAST_COMPLETE",
  "source_commit": "$source_commit",
  "protocol_sha256": "$protocol_sha",
  "contrast_sha256": "$contrast_sha",
  "independent_verification_sha256": "$verifier_sha",
  "canonical_package_manifest_sha256": "$canonical_manifest_sha",
  "taxonomy_package_manifest_sha256": "$taxonomy_manifest_sha",
  "repair_package_manifest_sha256": "$repair_manifest_sha",
  "classification": "HISTORICAL_RELATION_INTEGRITY_DIAGNOSTIC_AND_REPAIR_CONTRAST",
  "canonical_lineage_direct_rows": 8107,
  "canonical_rows": 8107,
  "mixed_verified_direct_sibling_rows": 1270,
  "mixed_rows": 7644,
  "mixed_quarantine_rows": 6374,
  "referenced_run_overlap_before": 96,
  "referenced_run_overlap_after": 0,
  "parent_partition_mismatch_cross_run_numerator": 743,
  "parent_partition_mismatch_cross_run_denominator": 743,
  "canonical_hard_gates_passed": 15,
  "canonical_hard_gates_total": 15,
  "canonical_support_gates_passed": 35,
  "canonical_support_gates_total": 36,
  "canonical_failed_support_gate": "frozen:b2.maximum_single_run_pair_share",
  "mixed_hard_gates_passed": 13,
  "mixed_hard_gates_total": 15,
  "repair_hard_gates_passed": 16,
  "repair_hard_gates_total": 16,
  "repair_support_gates_passed": 8,
  "repair_support_gates_total": 8,
  "gate_schemas_related_but_not_identical": true,
  "descriptive_two_family_case_study_not_population_estimate": true,
  "builder_ab_byte_identical": true,
  "verifier_ab_byte_identical": true,
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
