#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_retention_run_cluster_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_retention_run_cluster_${short}_nosmudge
output=/research/d7/spc/yzyang4/source-retention-run-cluster/${short}-v1
input=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
protocol_rel=phase1/source_retention_run_cluster_protocol_v1.json
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

git -C "${base_repo}" fetch fork phase1-value-critic > /tmp/source_run_cluster_fetch_${short}.stdout 2> /tmp/source_run_cluster_fetch_${short}.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > /tmp/source_run_cluster_worktree_${short}.stdout 2> /tmp/source_run_cluster_worktree_${short}.stderr
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
export PYTHONPATH=${worktree}
protocol=${worktree}/${protocol_rel}
test -f "${protocol}"

mkdir -p "${output}"
cp /tmp/source_run_cluster_fetch_${short}.stdout "${output}/fetch.stdout"
cp /tmp/source_run_cluster_fetch_${short}.stderr "${output}/fetch.stderr"
cp /tmp/source_run_cluster_worktree_${short}.stdout "${output}/worktree.stdout"
cp /tmp/source_run_cluster_worktree_${short}.stderr "${output}/worktree.stderr"
printf '%s\n' "${commit}" > "${output}/control_commit.txt"
printf '%s\n' "${expected_input_sha}" > "${output}/input_sha256.txt"
git -C "${worktree}" status --porcelain --untracked-files=all > "${output}/worktree_status_before.txt"
"${python_bin}" --version > "${output}/python_version.txt" 2>&1
git --version > "${output}/git_version.txt"

cat > "${output}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=post-result cluster robustness attack on verified source-retention transport
PREFLIGHT_02_QUESTION=does the frozen 15-task profile survive run-equal weighting and task-by-run uncertainty
PREFLIGHT_03_INPUT=immutable 3252-parent table SHA ${expected_input_sha}
PREFLIGHT_04_TASKS=exact v1 eligible 15-task universe; no additions or deletions after result
PREFLIGHT_05_SUPPORT=train at least 5 runs frozen at least 3 runs and at least 10 tasks
PREFLIGHT_06_METRIC=run-equal finite retention Spearman
PREFLIGHT_07_INFERENCE=100000 task permutations and 20000 hierarchical task-by-run bootstraps
PREFLIGHT_08_LEAKAGE=no code numeric outcome orientation prediction or prospective path
PREFLIGHT_09_REPRO=producer x2 verifier x2 exact commit and immutable protocol
PREFLIGHT_10_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0
PREFLIGHT_11_FAILURE=failed robustness lowers claim; no threshold task metric or weighting rescue
PREFLIGHT_12_SCOPE=no MAR causal task effect missing quality predictor utility or first-only claim
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including full phase1 regression
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' "${input}" > "${output}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_retention_run_cluster_robustness.py -q \
    > "${output}/focused_tests.stdout" 2> "${output}/focused_tests.stderr"
)

producer=(
  "${python_bin}" -m phase1.source_retention_run_cluster_robustness
  --protocol "${protocol}" --per-parent "${input}" --source-commit "${commit}"
)
verifier=(
  "${python_bin}" -m phase1.verify_source_retention_run_cluster_robustness
  --protocol "${protocol}" --per-parent "${input}" --source-commit "${commit}"
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

printf 'SOURCE_RETENTION_RUN_CLUSTER_FORMAL_COMPLETE\n' > "${output}/COMPLETE"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -printf '%P\0' \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${output}"
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output}/producer_a/summary.json")
tasks=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["support"]["run_robust_tasks"])' "${output}/producer_a/summary.json")
rho_value=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["primary"]["spearman_rho"])' "${output}/producer_a/summary.json")
printf 'SOURCE_RETENTION_RUN_CLUSTER_RUNNER_DONE status=%s tasks=%s rho=%s output=%s\n' \
  "${status}" "${tasks}" "${rho_value}" "${output}"
