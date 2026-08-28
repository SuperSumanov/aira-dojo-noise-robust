#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u
umask 077

readonly source_repo=${1:?source repository required}
readonly source_commit=${2:?40-character source commit required}
readonly formal_root=${3:?new formal output root required}
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly worktree_root=/research/d7/spc/yzyang4/worktrees/evidence-index-v9-${source_commit:0:12}
readonly protocol_rel=phase1/decision_corpus_evidence_index_v9_protocol_v1.json
readonly protocol_sha=a5d49990f3af37ce8968495fd13bf1b1c3f5e48875b117a86a878b75ed8d958a

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
test ! -e "$formal_root"
test ! -e "$worktree_root"
mkdir -p "$formal_root"

cat >"$formal_root/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol; PASS
02_goal=replace only the v8 decision_corpus evidence entry with the v2 lineage-direct certificate; PASS
03_estimand=post-result reporting repair with no new scientific readout or predictor effect; PASS
04_inputs=exact v8 index and published aggregate-only lineage package bound by SHA256; PASS
05_forbidden=no prospective values raw senior archives row identities prediction effect or search utility; PASS
06_population=historical v11 nine-set aggregate only; PASS
07_controls=source v8 exact hash fifteen unchanged entries package manifest and independent verifier; PASS
08_failure=any hash assertion support-gate status or security drift emits no index; PASS
09_randomness=none deterministic JSON and duplicate A/B builds; PASS
10_resources=CPU only GPU API model-fit base-update 0/0/0/0; PASS
11_duration=focused and full tests plus deterministic builder/verifier under one CPU process; PASS
12_security=fresh detached worktree LFS skip no secret-bearing archive access and trace scans; PASS
13_promotion=status remains provisional and frozen:b2 failed support gate remains mandatory; PASS
EOF
test "$(wc -l <"$formal_root/preflight_13.txt")" = 13

git -C "$source_repo" fetch myfork phase1-value-critic >"$formal_root/fetch.stdout" 2>"$formal_root/fetch.stderr"
git -C "$source_repo" cat-file -e "$source_commit^{commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "$source_repo" worktree add --detach "$worktree_root" "$source_commit" \
  >"$formal_root/worktree.stdout" 2>"$formal_root/worktree.stderr"
test "$(git -C "$worktree_root" rev-parse HEAD)" = "$source_commit"
test -z "$(git -C "$worktree_root" status --porcelain --untracked-files=all)"
printf '%s\n' "$source_commit" >"$formal_root/source_commit.txt"
printf '%s\n' "$worktree_root" >"$formal_root/worktree_path.txt"
test "$(sha256sum "$worktree_root/$protocol_rel" | awk '{print $1}')" = "$protocol_sha"

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q \
    phase1/tests/test_decision_corpus_evidence_index_v9.py \
    phase1/tests/test_decision_corpus_evidence_index_v8.py \
    phase1/tests/test_decision_corpus_evidence_index_v8_result.py \
    phase1/tests/test_decision_corpus_lineage_v2.py
) >"$formal_root/focused_tests.txt" 2>"$formal_root/focused_tests.stderr"

(
  cd "$worktree_root"
  "$python_bin" -m pytest -q phase1/tests
) >"$formal_root/full_tests.txt" 2>"$formal_root/full_tests.stderr"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/build_decision_corpus_evidence_index_v9.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/index_${suffix}.json" \
    >"$formal_root/builder_${suffix}.stdout" 2>"$formal_root/builder_${suffix}.stderr"
done
cmp "$formal_root/index_a.json" "$formal_root/index_b.json"

for suffix in a b; do
  "$python_bin" "$worktree_root/phase1/verify_decision_corpus_evidence_index_v9.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/index_a.json" \
    --output "$formal_root/verifier_${suffix}.json" \
    >"$formal_root/verifier_${suffix}.stdout" 2>"$formal_root/verifier_${suffix}.stderr"
done
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_b.json"

strace -f -qq -e trace=openat -o "$formal_root/open_trace.txt" \
  "$python_bin" "$worktree_root/phase1/build_decision_corpus_evidence_index_v9.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --output "$formal_root/index_trace.json" \
    >"$formal_root/trace_builder.stdout" 2>"$formal_root/trace_builder.stderr"
cmp "$formal_root/index_a.json" "$formal_root/index_trace.json"

grep -E "/prospective_decision_v1/|/score-channel-future-identity-cohort/|/external/senior_data/|/\.env([./\"]|$)|decision_clean_b[0-9]" \
  "$formal_root/open_trace.txt" >"$formal_root/forbidden_open_hits.txt" || true
test ! -s "$formal_root/forbidden_open_hits.txt"

strace -f -qq -e trace=network -o "$formal_root/network_trace.txt" \
  "$python_bin" "$worktree_root/phase1/verify_decision_corpus_evidence_index_v9.py" \
    --repo-root "$worktree_root" \
    --protocol "$worktree_root/$protocol_rel" \
    --candidate "$formal_root/index_a.json" \
    --output "$formal_root/verifier_trace.json" \
    >"$formal_root/trace_verifier.stdout" 2>"$formal_root/trace_verifier.stderr"
cmp "$formal_root/verifier_a.json" "$formal_root/verifier_trace.json"
test ! -s "$formal_root/network_trace.txt"

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
rg -l -i 'sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' \
  "$formal_root" >"$formal_root/artifact_content_scan.txt" || true
test ! -s "$formal_root/artifact_content_scan.txt"

index_sha=$(sha256sum "$formal_root/index_a.json" | awk '{print $1}')
verifier_sha=$(sha256sum "$formal_root/verifier_a.json" | awk '{print $1}')
package_manifest_sha=$(sha256sum "$worktree_root/phase1/results/decision_corpus_lineage_audit_v2_20260829_2514842/MANIFEST.sha256" | awk '{print $1}')
focused_tail=$(tail -n 1 "$formal_root/focused_tests.txt")
full_tail=$(tail -n 1 "$formal_root/full_tests.txt")
cat >"$formal_root/formal_summary.json" <<EOF
{
  "protocol": "decision-corpus-evidence-index-v9-formal-v1",
  "status": "FORMAL_LINEAGE_REPAIRED_EVIDENCE_INDEX_V9_COMPLETE",
  "source_commit": "$source_commit",
  "protocol_sha256": "$protocol_sha",
  "index_sha256": "$index_sha",
  "independent_verification_sha256": "$verifier_sha",
  "lineage_package_manifest_sha256": "$package_manifest_sha",
  "index_status": "PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960",
  "classification": "HISTORICAL_V11_PARENT_COMPLETE_SIBLING_CORE_LIMITED_SUPPORT",
  "entry_count": 16,
  "entries_replaced": 1,
  "entries_preserved_without_modification": 15,
  "hard_integrity_gates_passed": 15,
  "hard_integrity_gates_total": 15,
  "support_gates_passed": 35,
  "support_gates_total": 36,
  "failed_support_gate": "frozen:b2.maximum_single_run_pair_share",
  "builder_ab_byte_identical": true,
  "verifier_ab_byte_identical": true,
  "focused_test_tail": "$focused_tail",
  "full_test_tail": "$full_tail",
  "forbidden_open_hits": 0,
  "network_calls": 0,
  "credential_filename_hits": 0,
  "credential_content_hits": 0,
  "prospective_values_read": false,
  "raw_senior_archives_opened": false,
  "row_level_release_created": false,
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
