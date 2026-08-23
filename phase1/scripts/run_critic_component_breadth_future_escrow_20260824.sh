#!/usr/bin/env bash
set -eo pipefail
umask 077

if [[ $# -ne 0 ]]; then
  echo 'usage: run_critic_component_breadth_future_escrow_20260824.sh' >&2
  exit 64
fi

# Deliberately inert until a release-only follow-up commit binds the reviewed
# scientific commit.  This prevents any pre-review execution.
control_commit=e1093d8007449954c4561611c2ff381c55f7abe8
if [[ ${control_commit} == 0000000000000000000000000000000000000000 ]]; then
  echo 'runner is not release-bound to an approved scientific commit' >&2
  exit 69
fi

set +u
source "${HOME}/env_setup.sh"
set -u

base_repo=/research/d7/spc/yzyang4/aira-dojo
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
state_root=/research/d7/spc/yzyang4/prospective_decision_v1
cohort_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
closure_anchor=${cohort_root}/FIRST_CLOSED_COHORT_ANCHOR.json
cards=/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json
train=/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl
contract_sha=c52a71c36edb30a5dec965d6509387b386347acb50ac5e6a3ca789a778fd472b
cards_sha=5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb
train_sha=0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e

test -x "${python_bin}"
test -d "${base_repo}"
test -d "${state_root}"
test -d "${cohort_root}"
test -f "${closure_anchor}"
test ! -L "${closure_anchor}"

# Git fetch may need the sourced proxy, but every scientific/test Python process
# receives an allowlisted environment with no provider credential variables.
clean_python=(
  env -i
  HOME="${HOME}"
  PATH="${PATH}"
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  PYTHONDONTWRITEBYTECODE=1
  PYTHONHASHSEED=0
  OMP_NUM_THREADS=1
  OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1
  NUMEXPR_NUM_THREADS=1
  "${python_bin}"
)

mapfile -t anchor_values < <("${clean_python[@]}" - "${closure_anchor}" "${cohort_root}" <<'PY'
import hashlib
import json
import pathlib
import sys

anchor_path = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2]).resolve()
value = json.loads(anchor_path.read_text(encoding="utf-8"))
cohort = pathlib.Path(value.get("cohort_dir", ""))
sha = value.get("cohort_summary_sha256")
if (
    value.get("protocol") != "score-channel-future-closure-anchor-v1"
    or value.get("status") != "FUTURE_COHORT_FIRST_CLOSURE_ANCHORED_TRUTH_UNREAD"
    or value.get("identity_selected_before_truth") is not True
    or value.get("label_vault_opened") is not False
    or value.get("score_or_outcome_opened") is not False
    or value.get("replay_submission_authorized") is not False
    or not cohort.is_absolute()
    or cohort.is_symlink()
    or cohort.resolve().parent.parent != root
    or not isinstance(sha, str)
    or len(sha) != 64
    or any(c not in "0123456789abcdef" for c in sha)
):
    raise SystemExit("fixed first-closure anchor contract mismatch")
actual = hashlib.sha256((cohort / "summary.json").read_bytes()).hexdigest()
if actual != sha:
    raise SystemExit("anchored cohort summary changed")
print(cohort)
print(sha)
print(hashlib.sha256(anchor_path.read_bytes()).hexdigest())
PY
)
test "${#anchor_values[@]}" -eq 3
cohort_dir=${anchor_values[0]}
cohort_summary_sha=${anchor_values[1]}
closure_anchor_sha=${anchor_values[2]}

short=${control_commit:0:7}
repo=/research/d7/spc/yzyang4/worktrees/component_breadth_future_${short}_nosmudge
root=/research/d7/spc/yzyang4/critic-component-breadth-future/${short}-${cohort_summary_sha:0:12}-v1
if [[ -e ${repo} || -L ${repo} || -e ${root} || -L ${root} ]]; then
  echo 'formal worktree or output root already exists' >&2
  exit 68
fi

mkdir -p "$(dirname "${root}")"
mkdir "${root}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${root}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${root}" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

git -C "${base_repo}" fetch fork phase1-value-critic \
  > "${root}/fetch.stdout" 2> "${root}/fetch.stderr"
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" != "${control_commit}"
git -C "${base_repo}" merge-base --is-ancestor \
  "${control_commit}" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${repo}" "${control_commit}" \
  > "${root}/worktree.stdout" 2> "${root}/worktree.stderr"
test "$(git -C "${repo}" rev-parse HEAD)" = "${control_commit}"
git -C "${repo}" status --porcelain --untracked-files=all > "${root}/status_before.txt"
test ! -s "${root}/status_before.txt"

cd "${repo}"
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PYTHONHASHSEED=0

cat > "${root}/preflight_12.txt" <<EOF
01_direction=Decision Corpus plus Predictor Benchmark; revised raw-grade breadth is a supporting hypothesis
02_question=at fixed per-task pair budgets does the predeclared broad-support curation policy beat concentrated support on later physical siblings
03_origin=retrospective dev accuracy signal and raw-versus-y_norm alias audit were known; the old CI gate failed
04_inputs=locked training Cards/train plus the fixed first-closure anchor; target 300 includes complete boundary-archive overshoot
05_unit=unordered sibling pair nested in outcome-available selected parent, physical run, and task
06_matrix=broad/concentrated/random x nuisance seeds 20260823/24/25; 9 fits per implementation
07_fairness=pair budget and model are fixed; the estimand is the full curation-policy contrast, not isolated component/run causality
08_model=char_wb TF-IDF 3-5 plus symmetric LR; endpoint margin excludes intercept
09_inference=raw-grade primary; raw ties excluded, zero prediction margin gets 0.5; task bootstrap plus LOTO; normalized/log-loss/random cannot rescue
10_leakage=prediction escrow precedes truth; CLI accepts no vault path; file and network syscalls are audited
11_reproducibility=producer x2 plus non-truth-module independent source-refit verifier x2; exact release-bound commit and hashes
12_resources=single-thread CPU, 36 total fits, GPU=0 API=0 base-LLM updates=0, ETA 45-90 minutes
EOF

test "$(sha256sum phase1/critic_component_breadth_future_escrow_v1.json | awk '{print $1}')" = "${contract_sha}"
test "$(sha256sum "${cards}" | awk '{print $1}')" = "${cards_sha}"
test "$(sha256sum "${train}" | awk '{print $1}')" = "${train_sha}"
test "$(sha256sum "${cohort_dir}/summary.json" | awk '{print $1}')" = "${cohort_summary_sha}"

git diff-tree --root --no-commit-id --name-only -r "${control_commit}" \
  > "${root}/release_changed_files.txt"
tracked_name_hits=$( {
  grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
    "${root}/release_changed_files.txt" || true
} | wc -l )
tracked_content_hits=$( {
  git diff-tree --root --no-commit-id -p -r "${control_commit}" \
    | grep -E \
      '(sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
    | grep -vF 'sk-abcdefghijklmnop' || true
} | wc -l )
baseline_tracked_name_hits=$( {
  git ls-tree -r --name-only "${control_commit}" \
    | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' || true
} | wc -l )
printf '%s\n' "${tracked_name_hits}" > "${root}/scan_tracked_names_count.txt"
printf '%s\n' "${tracked_content_hits}" > "${root}/scan_tracked_content_count.txt"
printf '%s\n' "${baseline_tracked_name_hits}" \
  > "${root}/audit_baseline_broad_name_hits_not_a_release_gate.txt"
test "${tracked_name_hits}" -eq 0
test "${tracked_content_hits}" -eq 0

"${clean_python[@]}" -m pytest -p no:cacheprovider -q -rs \
  phase1/tests/test_critic_component_breadth_future_escrow.py \
  phase1/tests/test_critic_component_breadth_future_evaluation.py \
  phase1/tests/test_verify_critic_component_breadth_future_evaluation.py \
  phase1/tests/test_score_channel_future_closure_anchor.py \
  > "${root}/focused_tests.stdout" 2> "${root}/focused_tests.stderr"
"${clean_python[@]}" -m pytest -p no:cacheprovider -q -rs phase1/tests \
  > "${root}/full_phase1_tests.stdout" 2> "${root}/full_phase1_tests.stderr"

producer_args=(
  --training-cards "${cards}"
  --train-pairs "${train}"
  --cohort-dir "${cohort_dir}"
  --expect-cohort-summary-sha256 "${cohort_summary_sha}"
  --state-root "${state_root}"
  --repo-root "${repo}"
)
verifier_args=(
  --training-cards "${cards}"
  --train-pairs "${train}"
  --cohort-dir "${cohort_dir}"
  --expect-cohort-summary-sha256 "${cohort_summary_sha}"
  --state-root "${state_root}"
  --repo-root "${repo}"
)

mkdir "${root}/traces"
for replica in 1 2; do
  strace -ff -tt -yy -e trace=file,network -o "${root}/traces/producer_${replica}" \
    "${clean_python[@]}" -m phase1.critic_component_breadth_future_escrow \
      "${producer_args[@]}" --output "${root}/producer_${replica}" \
      > "${root}/producer_${replica}.stdout" 2> "${root}/producer_${replica}.stderr"
done
diff -r "${root}/producer_1" "${root}/producer_2" \
  > "${root}/producer_reproducibility.diff"
chmod -R a-w "${root}/producer_1" "${root}/producer_2"

for replica in 1 2; do
  strace -ff -tt -yy -e trace=file,network -o "${root}/traces/verifier_${replica}" \
    "${clean_python[@]}" -m phase1.verify_critic_component_breadth_future_escrow \
      "${verifier_args[@]}" --artifact "${root}/producer_1" \
      --output "${root}/verification_${replica}.json" \
      > "${root}/verifier_${replica}.stdout" 2> "${root}/verifier_${replica}.stderr"
done
cmp "${root}/verification_1.json" "${root}/verification_2.json"

forbidden_open_count=$( {
  grep -hEi \
    'open(at|at2)?\(.*(\.tar\.gz|label[_-]?vault|all_blind_views|/scores/|replay[^/]*(outcome|result)|outcome[_-]?vault)' \
    "${root}"/traces/* || true
} | wc -l )
network_syscall_count=$( {
  grep -hE '(socket|connect|sendto|recvfrom|sendmsg|recvmsg)\(' "${root}"/traces/* || true
} | wc -l )
printf '%s\n' "${forbidden_open_count}" > "${root}/scan_forbidden_open_count.txt"
printf '%s\n' "${network_syscall_count}" > "${root}/scan_network_syscall_count.txt"
test "${forbidden_open_count}" -eq 0
test "${network_syscall_count}" -eq 0

git -C "${repo}" status --porcelain --untracked-files=all > "${root}/status_after.txt"
test ! -s "${root}/status_after.txt"
"${clean_python[@]}" -VV > "${root}/python_version.txt" 2>&1
"${clean_python[@]}" -m pip freeze --all > "${root}/pip_freeze.txt"
printf '%s\n' "${control_commit}" > "${root}/control_commit.txt"
printf '%s\n' "${cohort_summary_sha}" > "${root}/cohort_summary_sha256.txt"
printf '%s\n' "${closure_anchor_sha}" > "${root}/closure_anchor_sha256.txt"

find "${root}" -type f -printf '%P\n' | LC_ALL=C sort > "${root}/artifact_file_manifest.txt"
artifact_name_hits=$(grep -icE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
  "${root}/artifact_file_manifest.txt" || true)
artifact_content_hits=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  hits=$(grep -IicE \
    '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
    "${artifact}") || grep_rc=$?
  test "${grep_rc}" -eq 0 -o "${grep_rc}" -eq 1
  artifact_content_hits=$((artifact_content_hits + hits))
done < <(find "${root}" -type f -print0)
printf '%s\n' "${artifact_name_hits}" > "${root}/scan_artifact_names_count.txt"
printf '%s\n' "${artifact_content_hits}" > "${root}/scan_artifact_content_count.txt"
test "${artifact_name_hits}" -eq 0
test "${artifact_content_hits}" -eq 0

date -u +%Y-%m-%dT%H:%M:%SZ > "${root}/completed_at_utc.txt"
printf 'FORMAL_FUTURE_COMPONENT_BREADTH_PREDICTION_ESCROW_COMPLETE_TRUTH_UNREAD\n' \
  > "${root}/COMPLETE"
(
  cd "${root}"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum \
    > SHA256SUMS
  sha256sum -c SHA256SUMS > /dev/null
)
chmod -R a-w "${root}"
trap - EXIT

printf 'result_dir=%s\n' "${root}"
tail -n 1 "${root}/focused_tests.stdout"
tail -n 1 "${root}/full_phase1_tests.stdout"
sha256sum "${root}/SHA256SUMS"
