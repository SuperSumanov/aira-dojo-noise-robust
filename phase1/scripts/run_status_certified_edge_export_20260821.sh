#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_status_certified_edge_export_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/status_certified_edges_${short}_nosmudge
output=/research/d7/spc/yzyang4/status-certified-edge-manifest/${short}-v1
parent_input=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
status_input=/research/d7/spc/yzyang4/source-journal-status-v11-42cb6b1-a2/producer/per_child.jsonl
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
protocol_rel=phase1/status_certified_edge_export_protocol_v1.json
parent_sha=75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03
status_sha=bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

test -x "${python_bin}"
test -f "${parent_input}"
test -f "${status_input}"
test "$(sha256sum "${parent_input}" | awk '{print $1}')" = "${parent_sha}"
test "$(sha256sum "${status_input}" | awk '{print $1}')" = "${status_sha}"
test ! -e "${worktree}"
test ! -e "${output}"

git -C "${base_repo}" fetch fork phase1-value-critic > /tmp/status_edge_fetch_${short}.stdout 2> /tmp/status_edge_fetch_${short}.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > /tmp/status_edge_worktree_${short}.stdout 2> /tmp/status_edge_worktree_${short}.stderr
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
export PYTHONPATH=${worktree}
protocol=${worktree}/${protocol_rel}
test -f "${protocol}"

mkdir -p "${output}"
cp /tmp/status_edge_fetch_${short}.stdout "${output}/fetch.stdout"
cp /tmp/status_edge_fetch_${short}.stderr "${output}/fetch.stderr"
cp /tmp/status_edge_worktree_${short}.stdout "${output}/worktree.stdout"
cp /tmp/status_edge_worktree_${short}.stderr "${output}/worktree.stderr"
printf '%s\n' "${commit}" > "${output}/control_commit.txt"
printf '%s  per_parent.csv\n%s  per_child.jsonl\n' "${parent_sha}" "${status_sha}" > "${output}/input_sha256.txt"
git -C "${worktree}" status --porcelain --untracked-files=all > "${output}/worktree_status_before.txt"
"${python_bin}" --version > "${output}/python_version.txt" 2>&1
git --version > "${output}/git_version.txt"

cat > "${output}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=status-certified source partial order explicit edge release
PREFLIGHT_02_QUESTION=can every audited aggregate relation be released as a reproducible child-ID edge
PREFLIGHT_03_INPUT=three pinned v11 b0 pair identity sets plus parent SHA ${parent_sha} and status SHA ${status_sha}
PREFLIGHT_04_UNIT=one explicit finite-child validity-dominates certified-invalid-child edge within a fixed source parent
PREFLIGHT_05_PRIMARY=exact edge reconstruction equality and complete original-gate sensitivity after excluding grade-absent edges
PREFLIGHT_06_DENOMINATOR=source pair capacity from the frozen 3252-parent census
PREFLIGHT_07_INFERENCE=finite-population identity export; no IID interval
PREFLIGHT_08_LEAKAGE=pair orientation gap score code and prospective outcomes forbidden as decision inputs
PREFLIGHT_09_REPRO=producer x2 independent verifier x2 exact commit and pinned hashes
PREFLIGHT_10_FAILURE=edge count mismatch duplicate identity endpoint overlap artifact drift or any original sensitivity gate failure
PREFLIGHT_11_SCOPE=post-result release engineering not a second confirmatory result
PREFLIGHT_12_RESOURCES=single-thread CPU GPU 0 API 0 base-LLM update 0
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including complete phase1 regression
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  "${parent_input}" "${status_input}" > "${output}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_status_certified_edges.py -q \
    > "${output}/focused_tests.stdout" 2> "${output}/focused_tests.stderr"
)

producer=(
  "${python_bin}" -m phase1.export_status_certified_edges
  --repo-root "${worktree}" --protocol "${protocol}"
  --per-parent "${parent_input}" --status-jsonl "${status_input}"
  --source-commit "${commit}"
)
verifier=(
  "${python_bin}" -m phase1.verify_status_certified_edges
  --repo-root "${worktree}" --protocol "${protocol}"
  --per-parent "${parent_input}" --status-jsonl "${status_input}"
  --source-commit "${commit}"
)

printf '%q ' "${producer[@]}" --output "${output}/producer_a" > "${output}/producer_a.command.txt"
printf '\n' >> "${output}/producer_a.command.txt"
printf '%q ' "${producer[@]}" --output "${output}/producer_b" > "${output}/producer_b.command.txt"
printf '\n' >> "${output}/producer_b.command.txt"
/usr/bin/time -v -o "${output}/producer_a.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_a.strace" \
  "${producer[@]}" --output "${output}/producer_a" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
/usr/bin/time -v -o "${output}/producer_b.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_b.strace" \
  "${producer[@]}" --output "${output}/producer_b" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
diff -r "${output}/producer_a" "${output}/producer_b" > "${output}/producer_reproducibility.diff"

printf '%q ' "${verifier[@]}" --artifact "${output}/producer_a" --output "${output}/verification_a.json" > "${output}/verifier_a.command.txt"
printf '\n' >> "${output}/verifier_a.command.txt"
printf '%q ' "${verifier[@]}" --artifact "${output}/producer_b" --output "${output}/verification_b.json" > "${output}/verifier_b.command.txt"
printf '\n' >> "${output}/verifier_b.command.txt"
/usr/bin/time -v -o "${output}/verifier_a.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_a.strace" \
  "${verifier[@]}" --artifact "${output}/producer_a" --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
/usr/bin/time -v -o "${output}/verifier_b.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_b.strace" \
  "${verifier[@]}" --artifact "${output}/producer_b" --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
diff "${output}/verification_a.json" "${output}/verification_b.json" > "${output}/verifier_reproducibility.diff"

forbidden_hits=$(
  { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|label_vault|outcome_registry|regrade|cards_current|decision_clean)' "${output}"/*.strace* || true; } \
    | { grep -vE 'phase1/v11_decision/decision_(train|frozen|extension)_v11_b0.jsonl' || true; } \
    | wc -l
)
printf 'forbidden_scientific_path_hits=%s\n' "${forbidden_hits}" > "${output}/trace_audit.txt"
test "${forbidden_hits}" = 0

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/full_phase1_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests -q \
    > "${output}/full_phase1_tests.stdout" 2> "${output}/full_phase1_tests.stderr"
)
git -C "${worktree}" status --porcelain --untracked-files=all > "${output}/worktree_status_after.txt"
test ! -s "${output}/worktree_status_before.txt"
test ! -s "${output}/worktree_status_after.txt"

preserves_all=$("${python_bin}" -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["execution_error_only_sensitivity"]["preserves_all_original_material_gates"]).lower())' "${output}/producer_a/summary.json")
test "${preserves_all}" = true

find "${output}" -type f -printf '%P\n' | LC_ALL=C sort \
  | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
  > "${output}/credential_filename_hits.txt" || true
test ! -s "${output}/credential_filename_hits.txt"
grep -rIEl '(^|[^A-Za-z0-9])(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
  "${output}" > "${output}/credential_content_hits.txt" || true
test ! -s "${output}/credential_content_hits.txt"

printf 'STATUS_CERTIFIED_EDGE_EXPORT_FORMAL_COMPLETE\n' > "${output}/COMPLETE"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -printf '%P\0' \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${output}"
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output}/producer_a/summary.json")
edges=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["edge_count"])' "${output}/producer_a/summary.json")
execution_edges=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["execution_error_only_sensitivity"]["overall"]["validity_dominance_edges"])' "${output}/producer_a/summary.json")
printf 'STATUS_CERTIFIED_EDGE_EXPORT_RUNNER_DONE status=%s edges=%s execution_only_edges=%s output=%s\n' \
  "${status}" "${edges}" "${execution_edges}" "${output}"
