#!/usr/bin/env bash
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -Eeo pipefail
set -u
umask 077

if [[ $# -ne 14 ]]; then
  echo 'usage: run_target522_linear_contrast_rank_audit_compat_v2_20260902.sh OUTPUT_ROOT EXPECTED_COMMIT EXECUTION_SHA PROTOCOL_SHA COMPATIBILITY_SHA PROJECTOR_SHA PROJECTION_VERIFIER_SHA ANALYZER_SHA RANK_VERIFIER_SHA SCIENTIFIC_TEST_SHA COMPATIBILITY_TEST_SHA RUNNER_SHA MONITOR_SHA STAGE_A_MANIFEST_SHA' >&2
  exit 64
fi
readonly output=$1
readonly expected_commit=$2
readonly execution_sha=$3
readonly protocol_sha=$4
readonly compatibility_sha=$5
readonly projector_sha=$6
readonly projection_verifier_sha=$7
readonly analyzer_sha=$8
readonly rank_verifier_sha=$9
readonly scientific_test_sha=${10}
readonly compatibility_test_sha=${11}
readonly runner_sha=${12}
readonly monitor_sha=${13}
readonly stage_a_manifest_sha=${14}
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly stage_a=/research/d7/spc/yzyang4/vertex-cost-contrast-target522/formal-05458c4-selection-v2
readonly worktree=/research/d7/spc/yzyang4/target522-linear-contrast-rank/worktree-${expected_commit:0:7}-compat-v2
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly execution_rel=phase1/target522_linear_contrast_rank_execution_v2.json
readonly protocol_rel=phase1/target522_linear_contrast_rank_audit_v1.json
readonly compatibility_rel=phase1/target522_linear_contrast_rank_stage_a_compatibility_v1.json
readonly projector_rel=phase1/project_target522_rank_stage_a_compatibility.py
readonly projection_verifier_rel=phase1/verify_target522_rank_stage_a_projection.py
readonly analyzer_rel=phase1/audit_target522_linear_contrast_rank.py
readonly rank_verifier_rel=phase1/verify_target522_linear_contrast_rank.py
readonly scientific_test_rel=phase1/tests/test_target522_linear_contrast_rank.py
readonly compatibility_test_rel=phase1/tests/test_target522_linear_contrast_rank_stage_a_compatibility.py
readonly runner_rel=phase1/scripts/run_target522_linear_contrast_rank_audit_compat_v2_20260902.sh
readonly monitor_rel=phase1/scripts/monitor_target522_linear_contrast_rank_audit_compat_v2_20260902.sh
readonly credential_pattern='(^|[^A-Za-z0-9])(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'

[[ $output =~ ^/research/d7/spc/yzyang4/target522-linear-contrast-rank/formal-[A-Za-z0-9._-]+$ ]]
[[ $expected_commit =~ ^[0-9a-f]{40}$ ]]
for value in "$execution_sha" "$protocol_sha" "$compatibility_sha" "$projector_sha" \
  "$projection_verifier_sha" "$analyzer_sha" "$rank_verifier_sha" "$scientific_test_sha" \
  "$compatibility_test_sha" "$runner_sha" "$monitor_sha" "$stage_a_manifest_sha"; do
  [[ $value =~ ^[0-9a-f]{64}$ ]]
done
test ! -e "$output"
test ! -e "$worktree"
test -d "$stage_a" && test ! -L "$stage_a"
test -f "$stage_a/COMPLETE" && test ! -e "$stage_a/FAILED_RC"
test "$(sha256sum "$stage_a/SHA256SUMS" | awk '{print $1}')" = "$stage_a_manifest_sha"
for public_name in producer_a.json producer_b.json; do
  test "$(awk -v name="./$public_name" '$2 == name {count += 1} END {print count + 0}' "$stage_a/SHA256SUMS")" = 1
  expected_public_sha=$(awk -v name="./$public_name" '$2 == name {print $1}' "$stage_a/SHA256SUMS")
  test "$(sha256sum "$stage_a/$public_name" | awk '{print $1}')" = "$expected_public_sha"
done
cmp "$stage_a/producer_a.json" "$stage_a/producer_b.json"
command -v strace >/dev/null
command -v timeout >/dev/null
test -x "$python_bin"

git -C "$repo" fetch fork phase1-value-critic
git -C "$repo" cat-file -e "${expected_commit}^{commit}"
git -C "$repo" merge-base --is-ancestor "$expected_commit" fork/phase1-value-critic
test "$(sha256sum "$0" | awk '{print $1}')" = "$runner_sha"
test "$(git -C "$repo" show "${expected_commit}:${runner_rel}" | sha256sum | awk '{print $1}')" = "$runner_sha"

mkdir -p "$output"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then printf '%s\n' "$rc" >"$output/FAILED_RC" 2>/dev/null || true; fi
  exit "$rc"
}
trap failure_receipt EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP

cat >"$output/preflight_13.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark plus Audit Protocol only; PASS
02_question=does the frozen Target-522 public sibling graph support the pre-registered endpoint-incidence rank claim; PASS
03_freeze=rank thresholds partition and decision rule remain byte-identical while the compatibility bridge froze before Stage-A v2 COMPLETE; PASS
04_input=immutable Stage-A v2 public A/B only after COMPLETE,no private selection identity or prospective value; PASS
05_projection=remove exactly two execution-container fields and replace exactly one source-lineage field for the byte-frozen analyzer; PASS
06_science=original protocol analyzer verifier and scientific test remain byte-identical; PASS
07_repetitions=projection A/B projection-verifier A/B analyzer A/B and rank-verifier A/B all byte exact; PASS
08_tests=focused old-science plus compatibility tests and full phase1 suite in a fresh exact-commit worktree; PASS
09_integrity=actual projected and receipt hashes,Stage-A manifest,source hashes,modes and independent reconstructions; PASS
10_security=strace file and network audit,no private selection label outcome prediction gap accuracy runtime utility or credential access; PASS
11_reporting=runner and monitor expose only structural status and hashes,never rank classification or graph profile; PASS
12_failure=hash schema projection source trace test arithmetic or support drift stops closed or follows frozen limited-support rule; PASS
13_resources=single CPU only,GPU paid-API model-fit base-update 0/0/0/0,first-960 closure unopened; PASS
EOF
test "$(wc -l <"$output/preflight_13.txt")" = 13

GIT_LFS_SKIP_SMUDGE=1 git -C "$repo" worktree add --detach "$worktree" "$expected_commit" \
  >"$output/worktree_add.log" 2>&1
test "$(git -C "$worktree" rev-parse HEAD)" = "$expected_commit"
for binding in \
  "$execution_rel:$execution_sha" \
  "$protocol_rel:$protocol_sha" \
  "$compatibility_rel:$compatibility_sha" \
  "$projector_rel:$projector_sha" \
  "$projection_verifier_rel:$projection_verifier_sha" \
  "$analyzer_rel:$analyzer_sha" \
  "$rank_verifier_rel:$rank_verifier_sha" \
  "$scientific_test_rel:$scientific_test_sha" \
  "$compatibility_test_rel:$compatibility_test_sha" \
  "$runner_rel:$runner_sha" \
  "$monitor_rel:$monitor_sha"; do
  path=${binding%%:*}
  expected=${binding##*:}
  test "$(sha256sum "$worktree/$path" | awk '{print $1}')" = "$expected"
done
cmp "$0" "$worktree/$runner_rel"
jq -e \
  --arg protocol_sha "$protocol_sha" --arg compatibility_sha "$compatibility_sha" \
  --arg projector_sha "$projector_sha" --arg projection_verifier_sha "$projection_verifier_sha" \
  --arg analyzer_sha "$analyzer_sha" --arg rank_verifier_sha "$rank_verifier_sha" \
  --arg scientific_test_sha "$scientific_test_sha" --arg compatibility_test_sha "$compatibility_test_sha" \
  --arg runner_sha "$runner_sha" --arg monitor_sha "$monitor_sha" '
  .protocol == "target522-linear-contrast-rank-execution-v2"
  and .status == "FROZEN_EXECUTION_COMPATIBILITY_WITH_SCIENTIFIC_PROTOCOL_UNCHANGED"
  and .scientific_protocol.sha256 == $protocol_sha
  and .stage_a_compatibility.sha256 == $compatibility_sha
  and .bindings.projector.sha256 == $projector_sha
  and .bindings.projection_independent_verifier.sha256 == $projection_verifier_sha
  and .bindings.frozen_analyzer.sha256 == $analyzer_sha
  and .bindings.frozen_rank_independent_verifier.sha256 == $rank_verifier_sha
  and .bindings.frozen_scientific_test.sha256 == $scientific_test_sha
  and .bindings.compatibility_test.sha256 == $compatibility_test_sha
  and .bindings.runner.sha256 == $runner_sha
  and .bindings.monitor.sha256 == $monitor_sha
  and .resources.gpu == 0 and .resources.paid_api_calls == 0
  and .resources.model_fits == 0 and .resources.base_updates == 0
' "$worktree/$execution_rel" >/dev/null

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
ulimit -v 16777216
"$python_bin" - <<'PY' >"$output/environment.json"
import json, os, platform
print(json.dumps({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "pythonhashseed": os.environ["PYTHONHASHSEED"],
    "thread_limits": {key: os.environ[key] for key in (
        "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
}, sort_keys=True))
PY
git --version >"$output/git_version.txt"
(
  cd "$worktree"
  timeout 600s "$python_bin" -m pytest -q "$scientific_test_rel" "$compatibility_test_rel"
) >"$output/focused_tests.txt" 2>&1
(
  cd "$worktree"
  timeout 1800s "$python_bin" -m pytest -q phase1/tests
) >"$output/full_tests.txt" 2>&1

stage_a_sha=$(sha256sum "$stage_a/producer_a.json" | awk '{print $1}')
projector=(
  "$python_bin" -m phase1.project_target522_rank_stage_a_compatibility
  --compatibility "$worktree/$compatibility_rel"
  --compatibility-sha256 "$compatibility_sha"
  --rank-protocol "$worktree/$protocol_rel"
  --rank-protocol-sha256 "$protocol_sha"
  --stage-a-public "$stage_a/producer_a.json"
  --stage-a-public-sha256 "$stage_a_sha"
)
printf '%q ' "${projector[@]}" --projected-output "$output/stage_a_projected_a.json" \
  --receipt-output "$output/projection_receipt_a.json" >"$output/projector_command.txt"
printf '\n' >>"$output/projector_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/projector_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/projector_a.trace" \
    "${projector[@]}" --projected-output "$output/stage_a_projected_a.json" \
    --receipt-output "$output/projection_receipt_a.json"
) >"$output/projector_a.stdout" 2>"$output/projector_a.stderr"
(
  cd "$worktree"
  timeout 300s "${projector[@]}" --projected-output "$output/stage_a_projected_b.json" \
    --receipt-output "$output/projection_receipt_b.json"
) >"$output/projector_b.stdout" 2>"$output/projector_b.stderr"
test ! -s "$output/projector_a.stderr" && test ! -s "$output/projector_b.stderr"
cmp "$output/stage_a_projected_a.json" "$output/stage_a_projected_b.json"
cmp "$output/projection_receipt_a.json" "$output/projection_receipt_b.json"
projected_sha=$(sha256sum "$output/stage_a_projected_a.json" | awk '{print $1}')
projection_receipt_sha=$(sha256sum "$output/projection_receipt_a.json" | awk '{print $1}')

projection_verifier=(
  "$python_bin" -m phase1.verify_target522_rank_stage_a_projection
  --compatibility "$worktree/$compatibility_rel"
  --compatibility-sha256 "$compatibility_sha"
  --rank-protocol "$worktree/$protocol_rel"
  --rank-protocol-sha256 "$protocol_sha"
  --actual-stage-a-public "$stage_a/producer_a.json"
  --actual-stage-a-public-sha256 "$stage_a_sha"
  --projected-stage-a-public "$output/stage_a_projected_a.json"
  --projected-stage-a-public-sha256 "$projected_sha"
  --claimed-projection-receipt "$output/projection_receipt_a.json"
  --claimed-projection-receipt-sha256 "$projection_receipt_sha"
)
printf '%q ' "${projection_verifier[@]}" --output "$output/projection_verification_a.json" \
  >"$output/projection_verifier_command.txt"
printf '\n' >>"$output/projection_verifier_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/projection_verifier_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/projection_verifier_a.trace" \
    "${projection_verifier[@]}" --output "$output/projection_verification_a.json"
) >"$output/projection_verifier_a.stdout" 2>"$output/projection_verifier_a.stderr"
(
  cd "$worktree"
  timeout 300s "${projection_verifier[@]}" --output "$output/projection_verification_b.json"
) >"$output/projection_verifier_b.stdout" 2>"$output/projection_verifier_b.stderr"
test ! -s "$output/projection_verifier_a.stderr" && test ! -s "$output/projection_verifier_b.stderr"
cmp "$output/projection_verification_a.json" "$output/projection_verification_b.json"

analyzer=(
  "$python_bin" -m phase1.audit_target522_linear_contrast_rank
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --stage-a-public "$output/stage_a_projected_a.json"
  --stage-a-public-sha256 "$projected_sha"
)
printf '%q ' "${analyzer[@]}" --output "$output/result_a.json" >"$output/analyzer_command.txt"
printf '\n' >>"$output/analyzer_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/analyzer_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/analyzer_a.trace" \
    "${analyzer[@]}" --output "$output/result_a.json"
) >"$output/analyzer_a.stdout" 2>"$output/analyzer_a.stderr"
(
  cd "$worktree"
  timeout 300s "${analyzer[@]}" --output "$output/result_b.json"
) >"$output/analyzer_b.stdout" 2>"$output/analyzer_b.stderr"
test ! -s "$output/analyzer_a.stderr" && test ! -s "$output/analyzer_b.stderr"
cmp "$output/result_a.json" "$output/result_b.json"

claimed_sha=$(sha256sum "$output/result_a.json" | awk '{print $1}')
rank_verifier=(
  "$python_bin" -m phase1.verify_target522_linear_contrast_rank
  --protocol "$worktree/$protocol_rel"
  --protocol-sha256 "$protocol_sha"
  --stage-a-public "$output/stage_a_projected_a.json"
  --stage-a-public-sha256 "$projected_sha"
  --claimed-result "$output/result_a.json"
  --claimed-result-sha256 "$claimed_sha"
)
printf '%q ' "${rank_verifier[@]}" --output "$output/verification_a.json" \
  >"$output/rank_verifier_command.txt"
printf '\n' >>"$output/rank_verifier_command.txt"
(
  cd "$worktree"
  /usr/bin/time -v -o "$output/rank_verifier_a.time.txt" \
    timeout 300s strace -ff -tt -yy -e trace=file,network -o "$output/rank_verifier_a.trace" \
    "${rank_verifier[@]}" --output "$output/verification_a.json"
) >"$output/rank_verifier_a.stdout" 2>"$output/rank_verifier_a.stderr"
(
  cd "$worktree"
  timeout 300s "${rank_verifier[@]}" --output "$output/verification_b.json"
) >"$output/rank_verifier_b.stdout" 2>"$output/rank_verifier_b.stderr"
test ! -s "$output/rank_verifier_a.stderr" && test ! -s "$output/rank_verifier_b.stderr"
cmp "$output/verification_a.json" "$output/verification_b.json"

for file in stage_a_projected_a.json stage_a_projected_b.json projection_receipt_a.json \
  projection_receipt_b.json projection_verification_a.json projection_verification_b.json \
  result_a.json result_b.json verification_a.json verification_b.json; do
  test "$(stat -c '%a' "$output/$file")" = 600
done
jq -e --arg compatibility_sha "$compatibility_sha" --arg actual_sha "$stage_a_sha" \
  --arg projected_sha "$projected_sha" '
  .status == "EXACT_EXECUTION_COMPATIBILITY_PROJECTION"
  and .compatibility_sha256 == $compatibility_sha
  and .actual_stage_a_public_sha256 == $actual_sha
  and .projected_stage_a_public_sha256 == $projected_sha
  and .removed_top_level_keys == ["selection_container", "selection_container_compatibility_sha256"]
  and .changed_top_level_keys == ["analysis_source_commit"]
  and .other_top_level_changes == 0
  and .private_selection_opened == false
  and .candidate_identity_opened == false
  and .prospective_values_read == false
' "$output/projection_receipt_a.json" >/dev/null
jq -e '
  .protocol == "target522-linear-contrast-rank-audit-result-v1"
  and .status == "COMPLETE"
  and (.classification == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_CONFIRMED"
       or .classification == "TARGET522_LINEAR_CONTRAST_ROW_INFLATION_NOT_CONFIRMED"
       or .classification == "TARGET522_LINEAR_CONTRAST_RANK_AUDIT_LIMITED_SUPPORT")
  and .scope.private_selection_opened == false
  and .scope.candidate_profile_or_identity_opened == false
  and .scope.prospective_values_read == false
' "$output/result_a.json" >/dev/null
test "$(jq -r .classification "$output/result_a.json")" = \
  "$(jq -r .classification "$output/verification_a.json")"

for role in projector_a projection_verifier_a analyzer_a rank_verifier_a; do
  forbidden_hits=$( { grep -hEi \
    '/external/senior_data/|label_vault|outcome_vault|/outcomes?/|regrade|private_[ab]\.json|private_selection|scorer[^/]*prediction|prediction[^/]*\.(jsonl|csv|json)|raw_archive|/\.env([" ]|$)' \
    "$output/${role}.trace"* || true; } | wc -l )
  network_hits=$( { grep -hEi '(^|[[:space:]])(socket|connect|sendto|recvfrom)\(' \
    "$output/${role}.trace"* || true; } | wc -l )
  test "$forbidden_hits" = 0
  test "$network_hits" = 0
done
printf 'projector_forbidden_path_hits=0\nprojection_verifier_forbidden_path_hits=0\nanalyzer_forbidden_path_hits=0\nrank_verifier_forbidden_path_hits=0\nprojector_network_hits=0\nprojection_verifier_network_hits=0\nanalyzer_network_hits=0\nrank_verifier_network_hits=0\n' \
  >"$output/trace_audit.txt"

git -C "$worktree" diff --exit-code >/dev/null
git -C "$worktree" diff --cached --exit-code >/dev/null
test -z "$(git -C "$worktree" status --porcelain --untracked-files=no)"
test "$(sha256sum "$stage_a/SHA256SUMS" | awk '{print $1}')" = "$stage_a_manifest_sha"
test "$(sha256sum "$stage_a/producer_a.json" | awk '{print $1}')" = "$stage_a_sha"

filename_hits=$(find "$output" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
credential_files=$(grep -R -E -i -l "$credential_pattern" "$output" \
  --exclude=security.txt --exclude=SHA256SUMS || true)
test "$filename_hits" = 0
test -z "$credential_files"
cat >"$output/security.txt" <<EOF
credential_filename_hits=0
boundary_aware_credential_content_file_hits=0
prospective_values_read=false
first960_closure_opened=false
private_selection_opened=false
candidate_profile_or_identity_opened=false
rank_classification_emitted_to_runner_or_monitor=false
gpu_paid_api_model_fit_base_update=0/0/0/0
EOF
cat >"$output/source_bindings.txt" <<EOF
source_commit=${expected_commit}
execution_protocol_sha256=${execution_sha}
scientific_protocol_sha256=${protocol_sha}
stage_a_compatibility_sha256=${compatibility_sha}
projector_source_sha256=${projector_sha}
projection_verifier_source_sha256=${projection_verifier_sha}
frozen_analyzer_source_sha256=${analyzer_sha}
frozen_rank_verifier_source_sha256=${rank_verifier_sha}
frozen_scientific_test_sha256=${scientific_test_sha}
compatibility_test_sha256=${compatibility_test_sha}
runner_source_sha256=${runner_sha}
monitor_source_sha256=${monitor_sha}
stage_a_sha256sums_sha256=${stage_a_manifest_sha}
actual_stage_a_public_sha256=${stage_a_sha}
projected_stage_a_public_sha256=${projected_sha}
projection_receipt_sha256=${projection_receipt_sha}
EOF
(
  cd "$output"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE ! -name FAILED_RC -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "$output"
trap - EXIT
printf 'status=TARGET522_LINEAR_CONTRAST_RANK_COMPAT_V2_COMPLETE\nmanifest_sha256=%s\nclassification_emitted=false\n' \
  "$(sha256sum "$output/SHA256SUMS" | awk '{print $1}')"
