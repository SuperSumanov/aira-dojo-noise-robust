#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 3 || ! $1 =~ ^[0-9a-f]{40}$ || ! $2 =~ ^[0-9a-f]{40}$ || ! $3 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_provenance_sensitivity_20260822.sh ANALYSIS_COMMIT OOF_RESULT_COMMIT OOF_VERIFIER_COMMIT' >&2
  exit 64
fi

analysis_commit=$1
result_commit=$2
verifier_commit=$3
analysis_short=${analysis_commit:0:7}
result_short=${result_commit:0:7}
verifier_short=${verifier_commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_provenance_${analysis_short}
raw=/research/d7/spc/yzyang4/source-choice-benchmark-materialization/5d6de6e-v2/public_a/train_groups.jsonl
decision=/research/d7/spc/yzyang4/source-choice-decision-view/3ceb99f-v2/view_a/train_model.jsonl
oof=/research/d7/spc/yzyang4/source-choice-oof-tfidf/${result_short}-v1
verification=/research/d7/spc/yzyang4/source-choice-oof-verification/${verifier_short}-on-${result_short}-v1
exact_audit=/research/d7/spc/yzyang4/source-choice-oof-exact-sign-audit/${analysis_short}-on-${result_short}-v1
root=/research/d7/spc/yzyang4/source-choice-provenance-sensitivity
final=${root}/${analysis_short}-on-${result_short}-v1
staging=${root}/.${analysis_short}-on-${result_short}-v1.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

[[ -x ${python_bin} && -f ${raw} && -f ${decision} && -d ${oof} && -d ${verification} && -d ${exact_audit} ]]
[[ -f ${oof}/COMPLETE && -f ${verification}/COMPLETE && -f ${exact_audit}/COMPLETE ]]
[[ $(tr -d '\r\n' < "${oof}/control_commit.txt") == "${result_commit}" ]]
[[ $(tr -d '\r\n' < "${verification}/result_commit.txt") == "${result_commit}" ]]
[[ $(tr -d '\r\n' < "${exact_audit}/result_commit.txt") == "${result_commit}" ]]
[[ $(tr -d '\r\n' < "${exact_audit}/audit_commit.txt") == "${analysis_commit}" ]]
[[ ! -e ${worktree} && ! -e ${final} ]]
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
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${analysis_commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${analysis_commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${analysis_commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_provenance_sensitivity_protocol_v1.json
[[ $(sha256sum "${raw}" | awk '{print $1}') == 48bc52e7f05c79d504c785a6249fb727a522b4eed42945c2bad221ad6012c435 ]]
[[ $(sha256sum "${decision}" | awk '{print $1}') == e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1 ]]
[[ $(wc -l < "${raw}") == 2109 && $(wc -l < "${decision}") == 2109 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${analysis_commit}" > "${staging}/analysis_commit.txt"
printf '%s\n' "${result_commit}" > "${staging}/result_commit.txt"
printf '%s\n' "${verifier_commit}" > "${staging}/verifier_commit.txt"
sha256sum "${protocol}" \
  "${worktree}/phase1/source_choice_provenance_sensitivity.py" \
  "${worktree}/phase1/tests/test_source_choice_provenance_sensitivity.py" \
  "${worktree}/phase1/scripts/run_source_choice_provenance_sensitivity_20260822.sh" \
  > "${staging}/control_sha256.txt"
sha256sum "${raw}" "${decision}" "${oof}/result_a/predictions.csv" \
  "${verification}/verification_a.json" "${exact_audit}/audit_a.json" \
  > "${staging}/input_sha256.txt"

cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=0DM conditional recovery-provenance sensitivity no legacy revival
PREFLIGHT_02_QUESTION=does frozen task-LOTO signal survive all-card-only restriction
PREFLIGHT_03_ACTIVATION=independent OOF GO and exact-sign GO required and NO cannot rescue
PREFLIGHT_04_INPUT=SHA-bound raw train decision train OOF predictions independent receipt
PREFLIGHT_05_UNIT=choice set primary all-card subset task clustering
PREFLIGHT_06_MODEL=no refit and rankings reused byte-for-byte
PREFLIGHT_07_BASELINE=exact one over observed source size
PREFLIGHT_08_METRIC=task macro delta task bootstrap exact task sign
PREFLIGHT_09_GATE=plus 0.03 task CI low above zero sign p below 0.05
PREFLIGHT_10_SECONDARY=mixed pool card-only uniform selected provenance task arity strata
PREFLIGHT_11_REPLICATES=two deterministic analysis replicas and recursive diff
PREFLIGHT_12_RESOURCES=CPU only GPU 0 API 0 expected under ten minutes
PREFLIGHT_13_SCOPE=train only no frozen extension vault search utility or causality claim
EOF

(
  cd "${worktree}"
  "${python_bin}" -m pytest phase1/tests/test_source_choice_provenance_sensitivity.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --raw-train "${raw}"
  --decision-train "${decision}"
  --oof-root "${oof}"
  --independent-verification-root "${verification}"
  --exact-sign-audit-root "${exact_audit}"
)
for replica in a b; do
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${python_bin}" -m phase1.source_choice_provenance_sensitivity "${common[@]}" \
      --output "${staging}/result_${replica}" \
      > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/result_a" "${staging}/result_b" > "${staging}/result_reproducibility.diff"

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

printf 'SOURCE_CHOICE_PROVENANCE_SENSITIVITY_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
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
printf 'SOURCE_CHOICE_PROVENANCE_SENSITIVITY_DONE verdict=%s result=%s\n' "${verdict}" "${final}"
