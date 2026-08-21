#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_oof_tfidf_20260822.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_oof_formal_${short}
view=/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2/view_a
result_root=/research/d7/spc/yzyang4/source-choice-oof-tfidf
final=${result_root}/${short}-v1
staging=${result_root}/.${short}-v1.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

[[ -x ${python_bin} && -d ${view} ]]
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

git -C "${repo}" fetch fork phase1-value-critic > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_oof_tfidf_protocol_v1.json
train=${view}/train_model.jsonl
cluster=${view}/cluster_manifest.jsonl
[[ -f ${protocol} && -f ${train} && -f ${cluster} ]]
[[ $(sha256sum "${train}" | awk '{print $1}') == e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1 ]]
[[ $(sha256sum "${cluster}" | awk '{print $1}') == a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035 ]]
[[ $(wc -l < "${train}") == 2109 && $(wc -l < "${cluster}") == 3000 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
"${python_bin}" -c 'import numpy,scipy,sklearn; print(numpy.__version__,scipy.__version__,sklearn.__version__)' \
  > "${staging}/library_versions.txt"
sha256sum "${protocol}" \
  "${worktree}/phase1/source_choice_oof_tfidf.py" \
  "${worktree}/phase1/tests/test_source_choice_oof_tfidf.py" \
  "${worktree}/phase1/scripts/run_source_choice_oof_tfidf_20260822.sh" \
  > "${staging}/control_sha256.txt"
sha256sum "${train}" "${cluster}" > "${staging}/input_sha256.txt"

cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=0DM train-only source-choice support gate no legacy revival
PREFLIGHT_02_QUESTION=fixed char-TFIDF predicts certified source winner across unseen tasks and runs
PREFLIGHT_03_INPUT=SHA-bound v2 train plus public cluster manifest only
PREFLIGHT_04_UNIT=2109 groups 5739 unique candidates 23 tasks 275 physical runs
PREFLIGHT_05_SPLIT=task-LOTO primary physical-run-grouped five-fold secondary
PREFLIGHT_06_MODEL=fixed char_wb 3-5 30000 features pairwise LR no search
PREFLIGHT_07_WEIGHT=each choice set total fit weight one with exact reverse orientation
PREFLIGHT_08_LEAK=group candidate run task and code hashes checked per fold
PREFLIGHT_09_METRIC=task macro delta primary plus task and run clustered inference
PREFLIGHT_10_GATE=plus 0.03 task CI low above zero sign p below 0.05
PREFLIGHT_11_CONTROLS=min SHA max step max code length winner oracle
PREFLIGHT_12_RESOURCES=CPU only 28 fits per producer GPU 0 API 0 expected under 120 minutes
PREFLIGHT_13_SCOPE=no frozen extension vault quality speedup or search utility claim
EOF

(
  cd "${worktree}"
  /usr/bin/time -v -o "${staging}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_choice_oof_tfidf.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --train-model "${train}"
  --cluster-manifest "${cluster}"
)
producer=("${python_bin}" -m phase1.source_choice_oof_tfidf "${common[@]}")
for replica in a b; do
  printf '%q ' "${producer[@]}" --output "${staging}/result_${replica}" \
    > "${staging}/producer_${replica}.command.txt"
  printf '\n' >> "${staging}/producer_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${producer[@]}" --output "${staging}/result_${replica}" \
    > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/result_a" "${staging}/result_b" > "${staging}/result_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(source-choice-benchmark-vault|prospective_decision_v1|temporal_blind|score-channel|outcome_registry|regrade|first.?960)(/|[._-])|/(frozen_model|extension_model)\.jsonl' "${staging}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_model_or_vault_path_hits=%s\n' "${forbidden_hits}" > "${staging}/trace_audit.txt"
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

printf 'SOURCE_CHOICE_OOF_TFIDF_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
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
verdict=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "${final}/result_a/summary.json")
printf 'SOURCE_CHOICE_OOF_TFIDF_RUNNER_DONE verdict=%s result=%s\n' "${verdict}" "${final}"
