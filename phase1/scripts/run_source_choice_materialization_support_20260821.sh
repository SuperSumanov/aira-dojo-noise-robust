#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_materialization_support_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_materialization_${short}_nosmudge
result_root=/research/d7/spc/yzyang4/source-choice-materialization-support
final=${result_root}/${short}-v1
staging=${result_root}/.${short}-v1.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
answerability=/research/d7/spc/yzyang4/source-decision-answerability/e9f6f69-v1/producer_a/per_parent.csv
construction=/research/d7/spc/yzyang4/source-hurdle-v11-c89c5bd-a2/producer/construction_per_parent.csv
expected_answerability_sha=b2488d059ce4fafacc321e98fb4f4e82b5f0b4d4abc86a413d9e6f80da0cb4d4
expected_construction_sha=846da509373ee0d6bbb072f7fcc9f21dbcbda0ad5ced0355dabffa5e61975f67

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

[[ -x ${python_bin} ]]
[[ -f ${answerability} && -f ${construction} ]]
[[ ! -e ${worktree} && ! -e ${final} ]]
mkdir -p "${result_root}" "${staging}"

cleanup() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${staging}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${staging}" 2>/dev/null || true
    echo "formal attempt failed and was preserved at ${staging}" >&2
  fi
  exit "${rc}"
}
trap cleanup EXIT

actual_answerability_sha=$(sha256sum "${answerability}" | awk '{print $1}')
actual_construction_sha=$(sha256sum "${construction}" | awk '{print $1}')
[[ ${actual_answerability_sha} == ${expected_answerability_sha} ]]
[[ ${actual_construction_sha} == ${expected_construction_sha} ]]
printf 'answerability_per_parent=%s\nhurdle_construction=%s\n' \
  "${actual_answerability_sha}" "${actual_construction_sha}" > "${staging}/input_sha256.txt"

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  "${answerability}" "${construction}" > "${staging}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

git -C "${repo}" fetch fork phase1-value-critic \
  > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_materialization_support_protocol_v1.json
[[ -f ${protocol} ]]
export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
git --version > "${staging}/git_version.txt"
sha256sum "${protocol}" \
  "${worktree}/phase1/source_choice_materialization_support.py" \
  "${worktree}/phase1/verify_source_choice_materialization_support.py" \
  "${worktree}/phase1/tests/test_source_choice_materialization_support.py" \
  > "${staging}/control_sha256.txt"

cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=failure-aware Decision Corpus source-choice release support; no retired HCE TD probe or multifidelity route
PREFLIGHT_02_QUESTION=how many certified source winners have a complete already-audited candidate-code reference set
PREFLIGHT_03_INPUT=SHA-pinned 3252-row answerability census plus 721-row structural construction census
PREFLIGHT_04_UNIT=source parent group with all-parent and all-certified-winner denominators retained
PREFLIGHT_05_JOIN=SHA256 parent and run identity plus exact role task source-size and row-count closure
PREFLIGHT_06_GATES=2800 groups 0.85 all-parent 0.90 certified coverage role breadth arity concentration and split isolation
PREFLIGHT_07_LABEL=winner-identification boolean only; no winner candidate identity numeric grade gap score or outcome
PREFLIGHT_08_ACCESS=no raw archive journal card code bytes model result prospective outcome or first960
PREFLIGHT_09_REPRO=producer x2 independent verifier x2 exact commit immutable protocol and input hashes
PREFLIGHT_10_INFERENCE=exact frozen-corpus census without iid confidence interval
PREFLIGHT_11_RESOURCES=single-thread CPU GPU 0 API 0 base-LLM update 0
PREFLIGHT_12_FAILURE=hash schema join count or any material gate failure closes S1 with no rescue
PREFLIGHT_13_SCOPE=pass authorizes only answerability-conditioned S1 construction; no complete-v11 utility novelty or predictor claim
EOF

(
  cd "${worktree}"
  /usr/bin/time -v -o "${staging}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_choice_materialization_support.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --answerability-per-parent "${answerability}"
  --hurdle-construction "${construction}"
  --source-commit "${commit}"
)
producer=("${python_bin}" -m phase1.source_choice_materialization_support "${common[@]}")
verifier=("${python_bin}" -m phase1.verify_source_choice_materialization_support "${common[@]}")

for replica in a b; do
  printf '%q ' "${producer[@]}" --output "${staging}/producer_${replica}" \
    > "${staging}/producer_${replica}.command.txt"
  printf '\n' >> "${staging}/producer_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${producer[@]}" --output "${staging}/producer_${replica}" \
    > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/producer_a" "${staging}/producer_b" \
  > "${staging}/producer_reproducibility.diff"

for replica in a b; do
  printf '%q ' "${verifier[@]}" --artifact "${staging}/producer_${replica}" \
    --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.command.txt"
  printf '\n' >> "${staging}/verifier_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/verifier_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
    "${verifier[@]}" --artifact "${staging}/producer_${replica}" \
    --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.stdout" 2> "${staging}/verifier_${replica}.stderr"
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|label_vault|outcome_registry|regrade|first.?960|raw[-_]?archive|journals?|cards_current)(/|[._-])' "${staging}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_path_hits=%s\n' "${forbidden_hits}" > "${staging}/trace_audit.txt"
[[ ${forbidden_hits} == 0 ]]

(
  cd "${worktree}"
  /usr/bin/time -v -o "${staging}/full_phase1_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests -q \
    > "${staging}/full_phase1_tests.stdout" 2> "${staging}/full_phase1_tests.stderr"
)
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_after.txt"
[[ ! -s ${staging}/worktree_status_after.txt ]]

find "${staging}" -type f -printf '%P\n' | LC_ALL=C sort > "${staging}/file_manifest.txt"
name_hits=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
printf '%s\n' "${name_hits}" > "${staging}/credential_filename_hits.txt"
content_hits=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  artifact_hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{10,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  [[ ${grep_rc} == 0 || ${grep_rc} == 1 ]]
  content_hits=$((content_hits + artifact_hits))
done < <(find "${staging}" -type f -print0)
printf '%s\n' "${content_hits}" > "${staging}/credential_content_hits.txt"
[[ ${name_hits} == 0 && ${content_hits} == 0 ]]

status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${staging}/producer_a/summary.json")
materializable=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"]["materializable_status_winners"])' "${staging}/producer_a/summary.json")
coverage=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"]["code_complete_share_of_status_winners"])' "${staging}/producer_a/summary.json")
printf 'SOURCE_CHOICE_MATERIALIZATION_SUPPORT_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
date -u +%Y-%m-%dT%H:%M:%SZ > "${staging}/completed_at_utc.txt"
(
  cd "${staging}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${staging}"
mv "${staging}" "${final}"
trap - EXIT
printf 'SOURCE_CHOICE_MATERIALIZATION_SUPPORT_RUNNER_DONE status=%s materializable=%s coverage=%s output=%s\n' \
  "${status}" "${materializable}" "${coverage}" "${final}"
