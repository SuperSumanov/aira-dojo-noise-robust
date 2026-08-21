#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 3 || ! $1 =~ ^[0-9a-f]{40}$ || ! $2 =~ ^[0-9a-f]{40}$ || ! $3 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_prediction_escrow_20260822.sh ESCROW_COMMIT OOF_VERIFIER_COMMIT OOF_RESULT_COMMIT' >&2
  exit 64
fi

commit=$1
activation_commit=$2
result_commit=$3
short=${commit:0:7}
activation_short=${activation_commit:0:7}
result_short=${result_commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_prediction_escrow_${short}
view=/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2/view_a
oof_result=/research/d7/spc/yzyang4/source-choice-oof-tfidf/${result_short}-v1
activation=/research/d7/spc/yzyang4/source-choice-oof-verification/${activation_short}-on-${result_short}-v1
root=/research/d7/spc/yzyang4/source-choice-prediction-escrow
final=${root}/${short}-on-${activation_short}-${result_short}-v1
staging=${root}/.${short}-on-${activation_short}-${result_short}-v1.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

[[ -x ${python_bin} && -d ${view} && -d ${oof_result} && -d ${activation} ]]
[[ -f ${oof_result}/COMPLETE && -f ${activation}/COMPLETE ]]
[[ ! -s ${oof_result}/result_reproducibility.diff ]]
[[ ! -s ${activation}/verification_reproducibility.diff ]]
[[ $(tr -d '\r\n' < "${oof_result}/control_commit.txt") == "${result_commit}" ]]
[[ $(tr -d '\r\n' < "${activation}/verifier_commit.txt") == "${activation_commit}" ]]
[[ $(tr -d '\r\n' < "${activation}/result_commit.txt") == "${result_commit}" ]]
[[ -z $(find "${oof_result}" "${activation}" -type f -perm /222 -print -quit) ]]
[[ ! -e ${worktree} && ! -e ${final} ]]
mkdir -p "${root}" "${staging}"

cleanup() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${staging}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${staging}" 2>/dev/null || true
    echo "prediction escrow attempt failed and was preserved at ${staging}" >&2
  fi
  exit "${rc}"
}
trap cleanup EXIT

git -C "${repo}" fetch fork phase1-value-critic > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_prediction_escrow_protocol_v1.json
oof_protocol=${worktree}/phase1/source_choice_oof_tfidf_protocol_v1.json
train=${view}/train_model.jsonl
frozen=${view}/frozen_model.jsonl
extension=${view}/extension_model.jsonl
cluster=${view}/cluster_manifest.jsonl
activation_verification=${activation}/verification_a.json
activation_result_commit=${activation}/result_commit.txt
[[ -f ${protocol} && -f ${oof_protocol} && -f ${train} && -f ${frozen} ]]
[[ -f ${extension} && -f ${cluster} && -f ${activation_verification} ]]
[[ $(sha256sum "${train}" | awk '{print $1}') == e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1 ]]
[[ $(sha256sum "${frozen}" | awk '{print $1}') == 2e8371c1890bee9c7a33cb04238f94aa130e5114b307a233e21ca5d1af2152df ]]
[[ $(sha256sum "${extension}" | awk '{print $1}') == 2a6d7c4bf5157e00e5fe59dd6100db23bb7771bfce32f55b93573d1b5d4fdd0b ]]
[[ $(sha256sum "${cluster}" | awk '{print $1}') == a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
printf '%s\n' "${activation_commit}" > "${staging}/activation_verifier_commit.txt"
printf '%s\n' "${result_commit}" > "${staging}/activation_result_commit.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
"${python_bin}" -c 'import numpy,scipy,sklearn; print(numpy.__version__,scipy.__version__,sklearn.__version__)' \
  > "${staging}/library_versions.txt"
sha256sum "${protocol}" "${oof_protocol}" \
  "${worktree}/phase1/source_choice_prediction_escrow.py" \
  "${worktree}/phase1/verify_source_choice_prediction_escrow.py" \
  "${worktree}/phase1/tests/test_source_choice_prediction_escrow.py" \
  "${worktree}/phase1/scripts/run_source_choice_prediction_escrow_20260822.sh" \
  "${activation_verification}" "${activation_result_commit}" \
  > "${staging}/control_sha256.txt"
sha256sum "${train}" "${frozen}" "${extension}" "${cluster}" > "${staging}/input_sha256.txt"

verdict=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "${activation_verification}")
[[ ${verdict} == GO_CROSS_TASK || ${verdict} == GO_RUN_ONLY ]]
printf '%s\n' "${verdict}" > "${staging}/activation_verdict.txt"
cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=conditional label-free source-choice prediction escrow only
PREFLIGHT_02_ACTIVATION=independently verified OOF GO and exact result commit
PREFLIGHT_03_INPUT=SHA-bound v2 train frozen extension plus public cluster manifest
PREFLIGHT_04_LABELS=frozen and extension model files contain no winners
PREFLIGHT_05_MODEL=byte-equal fixed OOF char-TFIDF pairwise LR full train refit
PREFLIGHT_06_OUTPUT=full rankings and raw model scores for frozen and extension
PREFLIGHT_07_CONTROLS=min SHA max step max code length
PREFLIGHT_08_REPRO=producer twice and independent structural verifier twice
PREFLIGHT_09_LEAK=label vault outcome and prospective score paths forbidden by strace
PREFLIGHT_10_METRIC=no frozen or extension metric and no checkpoint selection
PREFLIGHT_11_CLAIM=no new-task quality speedup utility or causal claim
PREFLIGHT_12_RESOURCES=CPU only one fit per producer GPU 0 API 0 base update 0
PREFLIGHT_13_UNBLIND=separate protocol and user decision required
EOF

(
  cd "${worktree}"
  "${python_bin}" -m pytest phase1/tests/test_source_choice_prediction_escrow.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --oof-protocol "${oof_protocol}"
  --train-model "${train}"
  --frozen-model "${frozen}"
  --extension-model "${extension}"
  --cluster-manifest "${cluster}"
  --activation-verification "${activation_verification}"
  --activation-result-commit "${activation_result_commit}"
)
for replica in a b; do
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${python_bin}" -m phase1.source_choice_prediction_escrow "${common[@]}" \
      --output "${staging}/result_${replica}" \
      > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/result_a" "${staging}/result_b" > "${staging}/result_reproducibility.diff"

verify_common=(
  --protocol "${protocol}"
  --train-model "${train}"
  --frozen-model "${frozen}"
  --extension-model "${extension}"
  --cluster-manifest "${cluster}"
  --activation-verification "${activation_verification}"
  --activation-result-commit "${activation_result_commit}"
)
for replica in a b; do
  /usr/bin/time -v -o "${staging}/verifier_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
    "${python_bin}" -m phase1.verify_source_choice_prediction_escrow "${verify_common[@]}" \
      --result "${staging}/result_${replica}" \
      --output "${staging}/verification_${replica}.json" \
      > "${staging}/verifier_${replica}.stdout" 2> "${staging}/verifier_${replica}.stderr"
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verification_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(source-choice-benchmark-vault|prospective_decision_v1|temporal_blind|score-channel|outcome_registry|regrade|first.?960)(/|[._-])|/(frozen|extension)[^/]*(label|winner|outcome)[^/]*' "${staging}"/*.strace* || true; } | wc -l )
printf 'forbidden_label_outcome_or_prospective_path_hits=%s\n' "${forbidden_hits}" > "${staging}/trace_audit.txt"
[[ ${forbidden_hits} == 0 ]]

(
  cd "${worktree}"
  "${python_bin}" -m pytest phase1/tests -q \
    > "${staging}/full_phase1_tests.stdout" 2> "${staging}/full_phase1_tests.stderr"
)
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_after.txt"
[[ ! -s ${staging}/worktree_status_after.txt ]]

find "${staging}" -type f -printf '%P\n' | LC_ALL=C sort > "${staging}/file_manifest.txt"
name_hits=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
content_hits=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  artifact_hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{10,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  [[ ${grep_rc} == 0 || ${grep_rc} == 1 ]]
  content_hits=$((content_hits + artifact_hits))
done < <(find "${staging}" -type f -print0)
printf '%s\n' "${name_hits}" > "${staging}/credential_filename_hits.txt"
printf '%s\n' "${content_hits}" > "${staging}/credential_content_hits.txt"
[[ ${name_hits} == 0 && ${content_hits} == 0 ]]

printf 'SOURCE_CHOICE_PREDICTION_ESCROW_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
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
printf 'SOURCE_CHOICE_PREDICTION_ESCROW_DONE verdict=%s result=%s\n' "${verdict}" "${final}"
