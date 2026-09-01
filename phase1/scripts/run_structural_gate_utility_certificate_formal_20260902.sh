#!/usr/bin/env bash
set -Eeo pipefail
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
readonly worktree_root=/research/d7/spc/yzyang4/worktrees/structural-gate-utility-${source_commit:0:12}-v3
readonly protocol_rel=phase1/structural_gate_utility_certificate_v1.json
readonly protocol_sha=bb4091ff0585c288d0fb99614125e82148338d6871872ae023a1c41913c60308

readonly -a input_relatives=(
  "${protocol_rel}"
  phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/result.json
  phase1/results/archive_granularity_retention_v1_20260831_bc88298/a/independent_verification.json
  phase1/results/archive_rejection_support_census_20260902_7ad0164/result.json
  phase1/results/archive_rejection_support_census_20260902_7ad0164/independent_verification.json
  phase1/results/incremental_archive_rejection_support_20260901_ce9f505/a/result.json
  phase1/results/incremental_archive_rejection_support_20260901_ce9f505/a/independent_verification.json
  phase1/results/prospective_structural_rejection_no_checkpoint_20260901/safe_summary.json
  phase1/results/prospective_structural_rejection_no_checkpoint_20260901/independent_verification.json
)

failure_receipt() {
  local rc=$?
  if (( rc != 0 )) && test -d "${formal_root}"; then
    printf '%s\n' "${rc}" >"${formal_root}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

write_input_hashes() {
  local output=$1 relative
  : >"${output}"
  for relative in "${input_relatives[@]}"; do
    test -f "${worktree_root}/${relative}"
    test ! -L "${worktree_root}/${relative}"
    printf '%s  %s\n' "$(sha256sum "${worktree_root}/${relative}" | awk '{print $1}')" "${relative}" >>"${output}"
  done
}

[[ "${source_commit}" =~ ^[0-9a-f]{40}$ ]]
test -d "${source_repo}/.git"
test -x "${python_bin}"
"${python_bin}" -c 'import pytest'
command -v strace >/dev/null
command -v grep >/dev/null
git -C "${source_repo}" cat-file -e "${source_commit}^{commit}"
test ! -e "${formal_root}"
test ! -e "${worktree_root}"
mkdir -m 0700 "${formal_root}"

cat >"${formal_root}/preflight_13.txt" <<EOF
01_direction=Decision Corpus Predictor Benchmark Audit Protocol only; PASS
02_goal=certify whether observed structural rejection removed the last usable checkpoint support of any affected competition; PASS
03_estimand=seven distinct rejected competitions in the settled 283-archive aggregate census; PASS
04_inputs=eight exact published result and independent-verification JSON artifacts bound by SHA256; PASS
05_partition=six retained-support competitions plus one uniquely linked zero-checkpoint trigger; PASS
06_decision=logical exhaustive partition with zero observed last-usable-support elimination and no tunable threshold; PASS
07_independence=producer A/B and non-importing verifier A/B plus trace reproductions; PASS
08_failure=any input linkage count registry support floor checkpoint or attestation drift emits no certificate; PASS
09_randomness=none deterministic canonical JSON; PASS
10_resources=single-thread CPU GPU API model-fit base-update 0/0/0/0; PASS
11_scope=post-hoc derived synthesis not new independent evidence or fully blind confirmation; PASS
12_security=published aggregate JSON only no prospective values raw senior archives identities or row-level release; PASS
13_promotion=paper-safe within-state curation claim only no stationarity universal losslessness repair counterfactual or method effect; PASS
EOF
test "$(wc -l <"${formal_root}/preflight_13.txt")" = 13
cat >"${formal_root}/resource_limits.txt" <<EOF
OMP_NUM_THREADS=${OMP_NUM_THREADS}
OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS}
MKL_NUM_THREADS=${MKL_NUM_THREADS}
BLIS_NUM_THREADS=${BLIS_NUM_THREADS}
NUMEXPR_NUM_THREADS=${NUMEXPR_NUM_THREADS}
VECLIB_MAXIMUM_THREADS=${VECLIB_MAXIMUM_THREADS}
TOKENIZERS_PARALLELISM=${TOKENIZERS_PARALLELISM}
EOF

GIT_LFS_SKIP_SMUDGE=1 git \
  -c filter.lfs.process= -c filter.lfs.smudge=cat -c filter.lfs.required=false \
  -C "${source_repo}" worktree add --detach "${worktree_root}" "${source_commit}" \
  >"${formal_root}/worktree.stdout" 2>"${formal_root}/worktree.stderr"
test "$(git -C "${worktree_root}" rev-parse HEAD)" = "${source_commit}"
test -z "$(git -C "${worktree_root}" status --porcelain --untracked-files=all)"
printf '%s\n' "${source_commit}" >"${formal_root}/source_commit.txt"
printf '%s\n' "${worktree_root}" >"${formal_root}/worktree_path.txt"
test "$(sha256sum "${worktree_root}/${protocol_rel}" | awk '{print $1}')" = "${protocol_sha}"
write_input_hashes "${formal_root}/input_hashes_before.txt"
test "$(wc -l <"${formal_root}/input_hashes_before.txt")" = "${#input_relatives[@]}"

(
  cd "${worktree_root}"
  "${python_bin}" -m pytest -q \
    phase1/tests/test_structural_gate_utility_certificate.py \
    phase1/tests/test_structural_gate_utility_certificate_runner.py
) >"${formal_root}/focused_tests.txt" 2>"${formal_root}/focused_tests.stderr"

(
  cd "${worktree_root}"
  "${python_bin}" -m pytest -q phase1/tests
) >"${formal_root}/full_tests.txt" 2>"${formal_root}/full_tests.stderr"

for suffix in a b; do
  "${python_bin}" "${worktree_root}/phase1/build_structural_gate_utility_certificate.py" \
    --repo-root "${worktree_root}" \
    --protocol "${worktree_root}/${protocol_rel}" \
    --output "${formal_root}/certificate_${suffix}.json" \
    >"${formal_root}/builder_${suffix}.stdout" 2>"${formal_root}/builder_${suffix}.stderr"
done
cmp "${formal_root}/certificate_a.json" "${formal_root}/certificate_b.json"

for suffix in a b; do
  "${python_bin}" "${worktree_root}/phase1/verify_structural_gate_utility_certificate.py" \
    --repo-root "${worktree_root}" \
    --protocol "${worktree_root}/${protocol_rel}" \
    --candidate "${formal_root}/certificate_a.json" \
    --output "${formal_root}/verifier_${suffix}.json" \
    >"${formal_root}/verifier_${suffix}.stdout" 2>"${formal_root}/verifier_${suffix}.stderr"
done
cmp "${formal_root}/verifier_a.json" "${formal_root}/verifier_b.json"

strace -f -qq -e trace=openat -o "${formal_root}/open_trace.txt" \
  "${python_bin}" "${worktree_root}/phase1/build_structural_gate_utility_certificate.py" \
    --repo-root "${worktree_root}" \
    --protocol "${worktree_root}/${protocol_rel}" \
    --output "${formal_root}/certificate_trace.json" \
    >"${formal_root}/trace_builder.stdout" 2>"${formal_root}/trace_builder.stderr"
cmp "${formal_root}/certificate_a.json" "${formal_root}/certificate_trace.json"

grep -E '/prospective_decision_v1/|/score-channel-future-identity-cohort/|/external/senior_data/|/\.env([./"]|$)|decision_clean_b[0-9]|cards_cur\.jsonl' \
  "${formal_root}/open_trace.txt" >"${formal_root}/forbidden_open_hits.txt" || true
test ! -s "${formal_root}/forbidden_open_hits.txt"

strace -f -qq -e trace=network -o "${formal_root}/network_trace.txt" \
  "${python_bin}" "${worktree_root}/phase1/verify_structural_gate_utility_certificate.py" \
    --repo-root "${worktree_root}" \
    --protocol "${worktree_root}/${protocol_rel}" \
    --candidate "${formal_root}/certificate_a.json" \
    --output "${formal_root}/verifier_trace.json" \
    >"${formal_root}/trace_verifier.stdout" 2>"${formal_root}/trace_verifier.stderr"
cmp "${formal_root}/verifier_a.json" "${formal_root}/verifier_trace.json"
test ! -s "${formal_root}/network_trace.txt"

write_input_hashes "${formal_root}/input_hashes_after.txt"
cmp "${formal_root}/input_hashes_before.txt" "${formal_root}/input_hashes_after.txt"
test -z "$(git -C "${worktree_root}" status --porcelain --untracked-files=all)"

cat >"${formal_root}/access_attestation.txt" <<EOF
published_aggregate_json_only=true
prospective_label_grade_outcome_prediction_values_read=false
raw_senior_archives_opened=false
task_run_archive_competition_candidate_identity_values_emitted=false
row_level_release_created=false
predictor_accuracy_scaling_search_utility_or_causal_effect_computed=false
counts_as_distinct_claim_evidence=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

find "${formal_root}" -type f \
  \( -iname '*.env' -o -iname '*api*key*' -o -iname '*secret*' -o -iname '*credential*' \) \
  -printf '%P\n' >"${formal_root}/artifact_filename_scan.txt"
test ! -s "${formal_root}/artifact_filename_scan.txt"
set +e
grep -RIlE --binary-files=without-match \
  'sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' \
  "${formal_root}" >"${formal_root}/artifact_content_scan.txt"
content_scan_rc=$?
set -e
test "${content_scan_rc}" = 1
test ! -s "${formal_root}/artifact_content_scan.txt"

certificate_sha=$(sha256sum "${formal_root}/certificate_a.json" | awk '{print $1}')
verifier_sha=$(sha256sum "${formal_root}/verifier_a.json" | awk '{print $1}')
distinct=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["distinct_rejected_competitions"])' "${formal_root}/verifier_a.json")
retained=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["retained_usable_support_competitions"])' "${formal_root}/verifier_a.json")
invalid_only=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["invalid_only_trigger_competitions"])' "${formal_root}/verifier_a.json")
eliminated=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["observed_last_usable_support_elimination_competitions"])' "${formal_root}/verifier_a.json")
focused_tail=$(tail -n 1 "${formal_root}/focused_tests.txt")
full_tail=$(tail -n 1 "${formal_root}/full_tests.txt")
cat >"${formal_root}/formal_summary.json" <<EOF
{
  "protocol": "structural-gate-utility-certificate-formal-v1",
  "status": "FORMAL_OBSERVED_STRUCTURAL_GATE_SUPPORT_PRESERVING_DERIVED_CERTIFICATE_COMPLETE",
  "source_commit": "${source_commit}",
  "protocol_sha256": "${protocol_sha}",
  "certificate_sha256": "${certificate_sha}",
  "independent_verification_sha256": "${verifier_sha}",
  "distinct_rejected_competitions": ${distinct},
  "retained_usable_support_competitions": ${retained},
  "invalid_only_trigger_competitions": ${invalid_only},
  "observed_last_usable_support_elimination_competitions": ${eliminated},
  "counts_as_distinct_claim_evidence": false,
  "builder_ab_byte_identical": true,
  "verifier_ab_byte_identical": true,
  "input_hashes_before_after_identical": true,
  "focused_test_tail": "${focused_tail}",
  "full_test_tail": "${full_tail}",
  "forbidden_open_hits": 0,
  "network_calls": 0,
  "credential_filename_hits": 0,
  "credential_content_hits": 0,
  "credential_content_scanner_rc": 1,
  "prospective_values_read": false,
  "raw_senior_archives_opened": false,
  "identity_values_emitted": false,
  "row_level_release_created": false,
  "cpu_thread_limit": 1,
  "gpu_api_model_fit_base_update": [0, 0, 0, 0]
}
EOF
"${python_bin}" -m json.tool "${formal_root}/formal_summary.json" >/dev/null

(
  cd "${formal_root}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${formal_root}"
trap - EXIT
printf 'formal_root=%s\n' "${formal_root}"
printf 'manifest_sha256=%s\n' "$(sha256sum "${formal_root}/SHA256SUMS" | awk '{print $1}')"
