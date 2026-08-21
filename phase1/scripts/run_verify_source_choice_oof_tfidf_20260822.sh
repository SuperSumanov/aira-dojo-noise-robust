#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 2 || ! $1 =~ ^[0-9a-f]{40}$ || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_verify_source_choice_oof_tfidf_20260822.sh VERIFIER_COMMIT RESULT_COMMIT' >&2
  exit 64
fi

verifier_commit=$1
result_commit=$2
verifier_short=${verifier_commit:0:7}
result_short=${result_commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_oof_verify_${verifier_short}
view=/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2/view_a
result=/research/d7/spc/yzyang4/source-choice-oof-tfidf/${result_short}-v1
root=/research/d7/spc/yzyang4/source-choice-oof-verification
final=${root}/${verifier_short}-on-${result_short}-v1
staging=${root}/.${verifier_short}-on-${result_short}-v1.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

[[ -x ${python_bin} && -d ${view} && -d ${result} ]]
[[ -f ${result}/COMPLETE && ! -s ${result}/result_reproducibility.diff ]]
[[ $(tr -d '\r\n' < "${result}/control_commit.txt") == "${result_commit}" ]]
[[ ! -e ${worktree} && ! -e ${final} ]]
[[ -z $(find "${result}" -type f -perm /222 -print -quit) ]]
mkdir -p "${root}" "${staging}"

cleanup() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${staging}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${staging}" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap cleanup EXIT

git -C "${repo}" fetch fork phase1-value-critic > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${verifier_commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${verifier_commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${verifier_commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_oof_tfidf_protocol_v1.json
train=${view}/train_model.jsonl
cluster=${view}/cluster_manifest.jsonl
expected_protocol_sha=$(awk '$2 ~ /source_choice_oof_tfidf_protocol_v1.json$/ {print $1}' "${result}/control_sha256.txt")
[[ -n ${expected_protocol_sha} && $(sha256sum "${protocol}" | awk '{print $1}') == "${expected_protocol_sha}" ]]
[[ $(sha256sum "${train}" | awk '{print $1}') == e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1 ]]
[[ $(sha256sum "${cluster}" | awk '{print $1}') == a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${verifier_commit}" > "${staging}/verifier_commit.txt"
printf '%s\n' "${result_commit}" > "${staging}/result_commit.txt"
(cd "${result}" && sha256sum --check SHA256SUMS) \
  > "${staging}/result_manifest_verification.txt"
sha256sum "${protocol}" "${worktree}/phase1/verify_source_choice_oof_tfidf.py" \
  "${worktree}/phase1/tests/test_source_choice_oof_tfidf.py" \
  "${result}/result_a/summary.json" "${result}/result_b/summary.json" \
  > "${staging}/control_and_result_sha256.txt"

(
  cd "${worktree}"
  "${python_bin}" -m pytest phase1/tests/test_source_choice_oof_tfidf.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --train-model "${train}"
  --cluster-manifest "${cluster}"
)
for replica in a b; do
  /usr/bin/time -v -o "${staging}/verifier_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
    "${python_bin}" -m phase1.verify_source_choice_oof_tfidf "${common[@]}" \
      --result "${result}/result_${replica}" \
      --output "${staging}/verification_${replica}.json" \
      > "${staging}/verifier_${replica}.stdout" 2> "${staging}/verifier_${replica}.stderr"
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verification_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(source-choice-benchmark-vault|prospective_decision_v1|temporal_blind|score-channel|outcome_registry|regrade|first.?960)(/|[._-])|/(frozen_model|extension_model)\.jsonl' "${staging}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_model_or_vault_path_hits=%s\n' "${forbidden_hits}" > "${staging}/trace_audit.txt"
[[ ${forbidden_hits} == 0 ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_after.txt"
[[ ! -s ${staging}/worktree_status_after.txt ]]

find "${staging}" -type f -printf '%P\n' | LC_ALL=C sort > "${staging}/file_manifest.txt"
name_hits=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
content_hits=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{10,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  [[ ${grep_rc} == 0 || ${grep_rc} == 1 ]]
  content_hits=$((content_hits + hits))
done < <(find "${staging}" -type f -print0)
printf '%s\n' "${name_hits}" > "${staging}/credential_filename_hits.txt"
printf '%s\n' "${content_hits}" > "${staging}/credential_content_hits.txt"
[[ ${name_hits} == 0 && ${content_hits} == 0 ]]

printf 'SOURCE_CHOICE_OOF_TFIDF_INDEPENDENT_VERIFICATION_COMPLETE\n' > "${staging}/COMPLETE"
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
verdict=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "${final}/verification_a.json")
printf 'SOURCE_CHOICE_OOF_TFIDF_VERIFICATION_DONE verdict=%s result=%s\n' "${verdict}" "${final}"
