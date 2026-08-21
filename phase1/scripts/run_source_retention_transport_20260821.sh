#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_retention_transport_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_retention_transport_${short}_nosmudge
output=/research/d7/spc/yzyang4/source-retention-transport/${short}-v1
input=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
protocol_rel=phase1/source_retention_transport_protocol_v1.json
expected_input_sha=75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

test -x "${python_bin}"
test -f "${input}"
test "$(sha256sum "${input}" | awk '{print $1}')" = "${expected_input_sha}"
test ! -e "${worktree}"
test ! -e "${output}"

git -C "${base_repo}" fetch fork phase1-value-critic > /tmp/source_retention_fetch_${short}.stdout 2> /tmp/source_retention_fetch_${short}.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > /tmp/source_retention_worktree_${short}.stdout 2> /tmp/source_retention_worktree_${short}.stderr
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
export PYTHONPATH=${worktree}

protocol=${worktree}/${protocol_rel}
test -f "${protocol}"
test "$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["input_per_parent_sha256"])' "${protocol}")" = "${expected_input_sha}"

mkdir -p "${output}"
cp /tmp/source_retention_fetch_${short}.stdout "${output}/fetch.stdout"
cp /tmp/source_retention_fetch_${short}.stderr "${output}/fetch.stderr"
cp /tmp/source_retention_worktree_${short}.stdout "${output}/worktree.stdout"
cp /tmp/source_retention_worktree_${short}.stderr "${output}/worktree.stderr"
printf '%s\n' "${commit}" > "${output}/control_commit.txt"
printf '%s\n' "${expected_input_sha}" > "${output}/input_sha256.txt"
git -C "${worktree}" status --porcelain --untracked-files=all > "${output}/worktree_status_before.txt"
"${python_bin}" --version > "${output}/python_version.txt" 2>&1
git --version > "${output}/git_version.txt"

cat > "${output}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=Decision Corpus failure-censor measurement; no predictor tuning
PREFLIGHT_02_QUESTION=train task retention profile transports to disjoint frozen physical runs
PREFLIGHT_03_INPUT=one immutable 3252-parent metadata table SHA ${expected_input_sha}
PREFLIGHT_04_UNIT=parent then task-equal; train defines profile and frozen verifies once
PREFLIGHT_05_METRIC=finite_source_retention Spearman plus frozen task contrast
PREFLIGHT_06_INFERENCE=100000 task permutations; 20000 paired-task bootstraps; fixed seeds
PREFLIGHT_07_LEAKAGE=no code numeric outcome orientation gap prediction or prospective path
PREFLIGHT_08_CONTROLS=synthetic positive reverse negative tamper and credential tests
PREFLIGHT_09_REPRO=producer x2 verifier x2 full commit and hashes embedded
PREFLIGHT_10_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0
PREFLIGHT_11_FAILURE=no threshold task metric role or unit change after result
PREFLIGHT_12_SCOPE=no MAR causal task effect complete choice set utility or first-only claim
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including full phase1 regression
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "${input}" > "${output}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_retention_transport.py -q \
    > "${output}/focused_tests.stdout" 2> "${output}/focused_tests.stderr"
)

producer_command=(
  "${python_bin}" -m phase1.source_retention_transport
  --protocol "${protocol}"
  --per-parent "${input}"
  --source-commit "${commit}"
)
verifier_command=(
  "${python_bin}" -m phase1.verify_source_retention_transport
  --protocol "${protocol}"
  --per-parent "${input}"
  --source-commit "${commit}"
)
printf '%q ' "${producer_command[@]}" --output "${output}/producer_a" > "${output}/producer_a.command.txt"
printf '\n' >> "${output}/producer_a.command.txt"
printf '%q ' "${producer_command[@]}" --output "${output}/producer_b" > "${output}/producer_b.command.txt"
printf '\n' >> "${output}/producer_b.command.txt"

/usr/bin/time -v -o "${output}/producer_a.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_a.strace" \
  "${producer_command[@]}" --output "${output}/producer_a" \
  > "${output}/producer_a.stdout" 2> "${output}/producer_a.stderr"
/usr/bin/time -v -o "${output}/producer_b.time.txt" \
  strace -ff -e trace=file -o "${output}/producer_b.strace" \
  "${producer_command[@]}" --output "${output}/producer_b" \
  > "${output}/producer_b.stdout" 2> "${output}/producer_b.stderr"
diff -r "${output}/producer_a" "${output}/producer_b" > "${output}/producer_reproducibility.diff"

printf '%q ' "${verifier_command[@]}" --artifact "${output}/producer_a" --output "${output}/verification_a.json" > "${output}/verifier_a.command.txt"
printf '\n' >> "${output}/verifier_a.command.txt"
printf '%q ' "${verifier_command[@]}" --artifact "${output}/producer_b" --output "${output}/verification_b.json" > "${output}/verifier_b.command.txt"
printf '\n' >> "${output}/verifier_b.command.txt"

/usr/bin/time -v -o "${output}/verifier_a.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_a.strace" \
  "${verifier_command[@]}" --artifact "${output}/producer_a" --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
/usr/bin/time -v -o "${output}/verifier_b.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_b.strace" \
  "${verifier_command[@]}" --artifact "${output}/producer_b" --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
diff "${output}/verification_a.json" "${output}/verification_b.json" > "${output}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|decision_frozen|label_vault|outcome_registry|regrade)' "${output}"/*.strace* || true; } | wc -l )
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

find "${output}" -type f -printf '%P\n' | LC_ALL=C sort \
  | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
  > "${output}/credential_filename_hits.txt" || true
test ! -s "${output}/credential_filename_hits.txt"
grep -rIEl '(^|[^A-Za-z0-9])(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
  "${output}" > "${output}/credential_content_hits.txt" || true
test ! -s "${output}/credential_content_hits.txt"

printf 'SOURCE_RETENTION_TRANSPORT_FORMAL_COMPLETE\n' > "${output}/COMPLETE"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -printf '%P\0' \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${output}"

status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output}/producer_a/summary.json")
eligible=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["support"]["eligible_common_tasks"])' "${output}/producer_a/summary.json")
rho=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["primary"]["spearman_rho"])' "${output}/producer_a/summary.json")
printf 'SOURCE_RETENTION_TRANSPORT_RUNNER_DONE status=%s eligible_tasks=%s rho=%s output=%s\n' \
  "${status}" "${eligible}" "${rho}" "${output}"
