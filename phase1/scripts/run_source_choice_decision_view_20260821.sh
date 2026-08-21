#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_decision_view_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_decision_view_v2_${short}
source_root=/research/d7/spc/yzyang4/source-choice-benchmark-materialization/5d6de6e-v2
result_root=/research/d7/spc/yzyang4/source-choice-decision-view
final=${result_root}/${short}-v2
staging=${result_root}/.${short}-v2.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

[[ -x ${python_bin} && -d ${source_root} ]]
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

git -C "${repo}" fetch fork phase1-value-critic \
  > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_decision_view_protocol_v2.json
source_summary=${source_root}/public_a/summary.json
source_manifest=${source_root}/public_a/sha256_manifest.json
source_verification=${source_root}/verification_a.json
source_train=${source_root}/public_a/train_groups.jsonl
source_frozen=${source_root}/public_a/frozen_inputs.jsonl
source_extension=${source_root}/public_a/extension_inputs.jsonl
for input in "${protocol}" "${source_summary}" "${source_manifest}" "${source_verification}" \
  "${source_train}" "${source_frozen}" "${source_extension}"; do
  [[ -f ${input} ]]
done

[[ $(sha256sum "${source_summary}" | awk '{print $1}') == dc5a7af25cef3cb967b76cbe3262473b42011bd6f8758caec4e4a1a198ceec1f ]]
[[ $(sha256sum "${source_manifest}" | awk '{print $1}') == 04973efd6708593208171eac36bb40c946bd21378ae9cf3ad43c2fccec2a8a92 ]]
[[ $(sha256sum "${source_verification}" | awk '{print $1}') == a915da2d77fa7d8db9775035b0a31a02ddb6ec20451d9dd30f8adb67fda96479 ]]
[[ $(sha256sum "${source_train}" | awk '{print $1}') == 48bc52e7f05c79d504c785a6249fb727a522b4eed42945c2bad221ad6012c435 ]]
[[ $(sha256sum "${source_frozen}" | awk '{print $1}') == 1ebe8d64c7f248b9b53e37a8c5413c6a986d9c66a2552f240a997db0810c45a9 ]]
[[ $(sha256sum "${source_extension}" | awk '{print $1}') == c5c9fc83fb9dcabe010165e3ad421a7a6c66401d389d9a8db44726eb813c0811 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
git --version > "${staging}/git_version.txt"
sha256sum "${protocol}" \
  "${worktree}/phase1/source_choice_decision_view.py" \
  "${worktree}/phase1/verify_source_choice_decision_view.py" \
  "${worktree}/phase1/source_choice_decision_view_sealed_evaluator.py" \
  "${worktree}/phase1/tests/test_source_choice_decision_view.py" \
  > "${staging}/control_sha256.txt"
sha256sum "${source_summary}" "${source_manifest}" "${source_verification}" \
  "${source_train}" "${source_frozen}" "${source_extension}" \
  > "${staging}/input_sha256.txt"

cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=0DL operator-proxy correction only; no HCE TD probe or multifidelity revival
PREFLIGHT_02_QUESTION=canonicalize operator case proxy without changing 3000 groups or 8027 candidates
PREFLIGHT_03_INPUT=SHA-pinned S1v2 public materialization summary manifest verification and three role files
PREFLIGHT_04_UNIT=all groups candidates labels ordering and code bytes retained exactly
PREFLIGHT_05_LABEL=train winner copied; frozen extension vault path and labels never read
PREFLIGHT_06_MODEL_FIELDS=exact group and candidate allowlists; fixed Draft Improve enum; unknown value fails
PREFLIGHT_07_BLOCKED=provenance source_journal_sha256 absent and lowercase operator count zero
PREFLIGHT_08_METADATA=role run parent separated into exact-field cluster manifest
PREFLIGHT_09_CODE=full UTF-8 code and SHA revalidated without normalization truncation or dedup merging
PREFLIGHT_10_EVALUATOR=aggregate-only sealed evaluator rejects extra fields and uses cluster manifest closure
PREFLIGHT_11_REPRO=producer x2 independent verifier x2 byte-identical and no producer import
PREFLIGHT_12_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0 expected under 10 minutes
PREFLIGHT_13_SCOPE=input integrity only; no predictor accuracy search utility prospective or novelty claim
EOF

(
  cd "${worktree}"
  /usr/bin/time -v -o "${staging}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_choice_decision_view.py \
      phase1/tests/test_source_choice_benchmark_materializer.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --source-summary "${source_summary}"
  --source-manifest "${source_manifest}"
  --source-verification "${source_verification}"
  --source "train=${source_train}"
  --source "frozen=${source_frozen}"
  --source "extension=${source_extension}"
)
producer=("${python_bin}" -m phase1.source_choice_decision_view "${common[@]}")
verifier=("${python_bin}" -m phase1.verify_source_choice_decision_view "${common[@]}")

for replica in a b; do
  printf '%q ' "${producer[@]}" --output "${staging}/view_${replica}" \
    > "${staging}/producer_${replica}.command.txt"
  printf '\n' >> "${staging}/producer_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${producer[@]}" --output "${staging}/view_${replica}" \
    > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/view_a" "${staging}/view_b" > "${staging}/view_reproducibility.diff"

for replica in a b; do
  printf '%q ' "${verifier[@]}" --view "${staging}/view_${replica}" \
    --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.command.txt"
  printf '\n' >> "${staging}/verifier_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/verifier_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
    "${verifier[@]}" --view "${staging}/view_${replica}" \
      --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.stdout" 2> "${staging}/verifier_${replica}.stderr"
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(source-choice-benchmark-vault|prospective_decision_v1|temporal_blind|score-channel|outcome_registry|regrade|first.?960)(/|[._-])' "${staging}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_or_vault_path_hits=%s\n' "${forbidden_hits}" > "${staging}/trace_audit.txt"
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

printf 'SOURCE_CHOICE_DECISION_VIEW_V2_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
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
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${final}/view_a/summary.json")
printf 'SOURCE_CHOICE_DECISION_VIEW_V2_RUNNER_DONE status=%s result=%s\n' "${status}" "${final}"
