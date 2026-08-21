#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_operator_conditioned_retention_support_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/operator_conditioned_support_${short}_nosmudge
output=/research/d7/spc/yzyang4/operator-conditioned-retention-support/${short}-v1
per_parent=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
cards=/research/d7/spc/yzyang4/aira-dojo/phase1/cards_current_v11.jsonl
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
protocol_rel=phase1/operator_conditioned_retention_support_protocol_v1.json
expected_parent_sha=75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03
expected_cards_sha=6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

test -x "${python_bin}"
test -f "${per_parent}"
test -f "${cards}"
test "$(sha256sum "${per_parent}" | awk '{print $1}')" = "${expected_parent_sha}"
test "$(sha256sum "${cards}" | awk '{print $1}')" = "${expected_cards_sha}"
test ! -e "${worktree}"
test ! -e "${output}"

git -C "${base_repo}" fetch fork phase1-value-critic \
  > /tmp/operator_conditioned_support_fetch_${short}.stdout \
  2> /tmp/operator_conditioned_support_fetch_${short}.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > /tmp/operator_conditioned_support_worktree_${short}.stdout \
  2> /tmp/operator_conditioned_support_worktree_${short}.stderr
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
export PYTHONPATH=${worktree}
protocol=${worktree}/${protocol_rel}
test -f "${protocol}"

mkdir -p "${output}"
cp /tmp/operator_conditioned_support_fetch_${short}.stdout "${output}/fetch.stdout"
cp /tmp/operator_conditioned_support_fetch_${short}.stderr "${output}/fetch.stderr"
cp /tmp/operator_conditioned_support_worktree_${short}.stdout "${output}/worktree.stdout"
cp /tmp/operator_conditioned_support_worktree_${short}.stderr "${output}/worktree.stderr"
printf '%s\n' "${commit}" > "${output}/control_commit.txt"
printf 'per_parent=%s\ncards=%s\n' "${expected_parent_sha}" "${expected_cards_sha}" \
  > "${output}/input_sha256.txt"
git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${output}/worktree_status_before.txt"
"${python_bin}" --version > "${output}/python_version.txt" 2>&1
git --version > "${output}/git_version.txt"

cat > "${output}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=noncausal operator-conditioned retention support for the current failure-censored Decision Corpus line
PREFLIGHT_02_QUESTION=are Debug and Improve each supported across disjoint train and frozen physical runs in at least eight tasks
PREFLIGHT_03_INPUT=immutable 3252-parent table SHA ${expected_parent_sha} and 16012-card v11 SHA ${expected_cards_sha}
PREFLIGHT_04_UNIT=parent support plus distinct physical runs; no child or edge iid claim
PREFLIGHT_05_SUPPORT=per task-op train parents 20 frozen parents 10 train runs 5 frozen runs 3; both target ops required
PREFLIGHT_06_GATES=at least 8 tasks 16 cells join coverage 0.90 context exact overlap zero dominant frozen share 0.25
PREFLIGHT_07_ACCESS=identity role task run parent and lineage op only; no retention value count grade orientation code or outcome use
PREFLIGHT_08_LEAKAGE=no prospective label-vault regrade score-channel or outcome-registry path
PREFLIGHT_09_REPRO=producer x2 verifier x2 exact commit immutable protocol and input hashes
PREFLIGHT_10_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0
PREFLIGHT_11_FAILURE=any support gate failure closes S1 without threshold task or operator rescue
PREFLIGHT_12_SCOPE=no randomized assignment within-parent contrast causal effect predictor utility or search-utility claim
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including full phase1 regression
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  "${per_parent}" "${cards}" > "${output}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_operator_conditioned_retention_support.py -q \
    > "${output}/focused_tests.stdout" 2> "${output}/focused_tests.stderr"
)

producer=(
  "${python_bin}" -m phase1.operator_conditioned_retention_support
  --protocol "${protocol}" --per-parent "${per_parent}" --cards "${cards}"
  --source-commit "${commit}"
)
verifier=(
  "${python_bin}" -m phase1.verify_operator_conditioned_retention_support
  --protocol "${protocol}" --per-parent "${per_parent}" --cards "${cards}"
  --source-commit "${commit}"
)

printf '%q ' "${producer[@]}" --output "${output}/producer_a" \
  > "${output}/producer_a.command.txt"
printf '\n' >> "${output}/producer_a.command.txt"
printf '%q ' "${producer[@]}" --output "${output}/producer_b" \
  > "${output}/producer_b.command.txt"
printf '\n' >> "${output}/producer_b.command.txt"
/usr/bin/time -v -o "${output}/producer_a.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_a.strace" \
  "${producer[@]}" --output "${output}/producer_a" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
/usr/bin/time -v -o "${output}/producer_b.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_b.strace" \
  "${producer[@]}" --output "${output}/producer_b" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
diff -r "${output}/producer_a" "${output}/producer_b" \
  > "${output}/producer_reproducibility.diff"

printf '%q ' "${verifier[@]}" --artifact "${output}/producer_a" \
  --output "${output}/verification_a.json" > "${output}/verifier_a.command.txt"
printf '\n' >> "${output}/verifier_a.command.txt"
printf '%q ' "${verifier[@]}" --artifact "${output}/producer_b" \
  --output "${output}/verification_b.json" > "${output}/verifier_b.command.txt"
printf '\n' >> "${output}/verifier_b.command.txt"
/usr/bin/time -v -o "${output}/verifier_a.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_a.strace" \
  "${verifier[@]}" --artifact "${output}/producer_a" \
  --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
/usr/bin/time -v -o "${output}/verifier_b.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_b.strace" \
  "${verifier[@]}" --artifact "${output}/producer_b" \
  --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
diff "${output}/verification_a.json" "${output}/verification_b.json" \
  > "${output}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|decision_frozen|label_vault|outcome_registry|regrade)' "${output}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_path_hits=%s\n' "${forbidden_hits}" \
  > "${output}/trace_audit.txt"
test "${forbidden_hits}" = 0

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/full_phase1_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests -q \
    > "${output}/full_phase1_tests.stdout" 2> "${output}/full_phase1_tests.stderr"
)
git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${output}/worktree_status_after.txt"
test ! -s "${output}/worktree_status_before.txt"
test ! -s "${output}/worktree_status_after.txt"

find "${output}" -type f -printf '%P\n' | LC_ALL=C sort \
  | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
  > "${output}/credential_filename_hits.txt" || true
test ! -s "${output}/credential_filename_hits.txt"
grep -rIEl '(^|[^A-Za-z0-9])(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
  "${output}" > "${output}/credential_content_hits.txt" || true
test ! -s "${output}/credential_content_hits.txt"

printf 'OPERATOR_CONDITIONED_RETENTION_SUPPORT_FORMAL_COMPLETE\n' > "${output}/COMPLETE"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -printf '%P\0' \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${output}"
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output}/producer_a/summary.json")
tasks=$("${python_bin}" -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["inventory"]["supported_tasks"]))' "${output}/producer_a/summary.json")
cells=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["inventory"]["supported_task_op_cells"])' "${output}/producer_a/summary.json")
printf 'OPERATOR_CONDITIONED_RETENTION_SUPPORT_RUNNER_DONE status=%s tasks=%s cells=%s output=%s\n' \
  "${status}" "${tasks}" "${cells}" "${output}"
