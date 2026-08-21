#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -ne 1 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_choice_benchmark_materialization_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_choice_benchmark_${short}_nosmudge
result_root=/research/d7/spc/yzyang4/source-choice-benchmark-materialization
vault_root=/research/d7/spc/yzyang4/source-choice-benchmark-vault
final=${result_root}/${short}-v2
vault_final=${vault_root}/${short}-v2
staging=${result_root}/.${short}-v2.tmp.$$
vault_staging=${vault_root}/.${short}-v2.tmp.$$
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
per_parent=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
identity=/research/d7/spc/yzyang4/source-identity-recovery-v11-3faf001-a1/producer/per_parent.jsonl
status_edges=/research/d7/spc/yzyang4/status-certified-edge-manifest/c9bfc21-v1/producer_a/edges.jsonl
status_registry=/research/d7/spc/yzyang4/source-journal-status-v11-42cb6b1-a2/producer/per_child.jsonl
construction=/research/d7/spc/yzyang4/source-hurdle-v11-c89c5bd-a2/producer/construction_per_parent.csv
answer_summary=/research/d7/spc/yzyang4/source-decision-answerability/e9f6f69-v1/producer_a/summary.json
support_summary=/research/d7/spc/yzyang4/source-choice-materialization-support/efbda54-v1/producer_a/summary.json

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

[[ -x ${python_bin} ]]
[[ ! -e ${worktree} && ! -e ${final} && ! -e ${vault_final} ]]
mkdir -p "${result_root}" "${vault_root}" "${staging}" "${vault_staging}"

cleanup() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${staging}/FAILED_RC" 2>/dev/null || true
    printf '%s\n' "${rc}" > "${vault_staging}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${staging}" "${vault_staging}" 2>/dev/null || true
    echo "formal attempt failed and was preserved at ${staging} and ${vault_staging}" >&2
  fi
  exit "${rc}"
}
trap cleanup EXIT

git -C "${repo}" fetch fork phase1-value-critic \
  > "${staging}/fetch.stdout" 2> "${staging}/fetch.stderr"
[[ $(git -C "${repo}" rev-parse fork/phase1-value-critic) == "${commit}" ]]
GIT_LFS_SKIP_SMUDGE=1 git -C "${repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${staging}/worktree.stdout" 2> "${staging}/worktree.stderr"
git -C "${worktree}" lfs pull --include=phase1/cards_current_v11.jsonl --exclude= \
  > "${staging}/lfs_pull.stdout" 2> "${staging}/lfs_pull.stderr"
[[ $(git -C "${worktree}" rev-parse HEAD) == "${commit}" ]]
git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/worktree_status_before.txt"
[[ ! -s ${staging}/worktree_status_before.txt ]]

protocol=${worktree}/phase1/source_choice_benchmark_materialization_protocol_v2.json
answer_protocol=${worktree}/phase1/source_decision_answerability_protocol_v1.json
cards=${worktree}/phase1/cards_current_v11.jsonl
pair_train=${worktree}/phase1/v11_decision/decision_train_v11_b0.jsonl
pair_frozen=${worktree}/phase1/v11_decision/decision_frozen_v11_b0.jsonl
pair_extension=${worktree}/phase1/v11_decision/decision_extension_v11_b0.jsonl
for input in "${protocol}" "${answer_protocol}" "${cards}" "${pair_train}" "${pair_frozen}" \
  "${pair_extension}" "${per_parent}" "${identity}" "${status_edges}" "${status_registry}" \
  "${construction}" "${answer_summary}" "${support_summary}"; do
  [[ -f ${input} ]]
done

[[ $(sha256sum "${cards}" | awk '{print $1}') == 6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75 ]]
[[ $(sha256sum "${per_parent}" | awk '{print $1}') == 75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03 ]]
[[ $(sha256sum "${identity}" | awk '{print $1}') == b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2 ]]
[[ $(sha256sum "${status_edges}" | awk '{print $1}') == dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d ]]
[[ $(sha256sum "${status_registry}" | awk '{print $1}') == bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2 ]]
[[ $(sha256sum "${construction}" | awk '{print $1}') == 846da509373ee0d6bbb072f7fcc9f21dbcbda0ad5ced0355dabffa5e61975f67 ]]
[[ $(sha256sum "${answer_summary}" | awk '{print $1}') == 048f18cc2769df4c9cc4836c491c2917b2e8b051a847da20bdce454dd6592326 ]]
[[ $(sha256sum "${support_summary}" | awk '{print $1}') == 5ab474bd061f7f8845a19d1cefd5023fc9e2a0e5a1b45d4d93842fb62759c303 ]]

export PYTHONPATH=${worktree}${PYTHONPATH:+:${PYTHONPATH}}
printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
git --version > "${staging}/git_version.txt"
git lfs version > "${staging}/git_lfs_version.txt" 2>&1
sha256sum "${protocol}" "${answer_protocol}" \
  "${worktree}/phase1/source_choice_benchmark_materializer.py" \
  "${worktree}/phase1/verify_source_choice_benchmark_materialization.py" \
  "${worktree}/phase1/source_choice_sealed_evaluator.py" \
  "${worktree}/phase1/source_decision_answerability.py" \
  "${worktree}/phase1/tests/test_source_choice_benchmark_materializer.py" \
  > "${staging}/control_sha256.txt"
sha256sum "${cards}" "${per_parent}" "${identity}" "${status_edges}" "${status_registry}" \
  "${construction}" "${answer_summary}" "${support_summary}" > "${staging}/input_sha256.txt"

cat > "${staging}/preflight_matrix.txt" <<'EOF'
PREFLIGHT_01_DIRECTION=0DI source-choice release materialization; no HCE TD probe or multifidelity revival
PREFLIGHT_02_QUESTION=materialize exactly the 3000 certified and code-reference-complete source groups
PREFLIGHT_03_INPUT=SHA-pinned cards graph identity status construction and 0DG/0DI summaries
PREFLIGHT_04_UNIT=source parent with 3000 groups and 8027 candidate slots retained exactly
PREFLIGHT_05_LABEL=status-aware unique winner; pair gap and numeric grade unused
PREFLIGHT_06_ORDER=ascending candidate raw-ID SHA independent of winner outcome status and generation order
PREFLIGHT_07_CODE=full UTF-8 code bytes nonempty exact SHA no truncation normalization or dedup merging
PREFLIGHT_08_JOURNAL=credential-first and only status-bound needed journal SHAs parsed
PREFLIGHT_09_ISOLATION=train label public; frozen and extension inputs label-free with separate opaque vault
PREFLIGHT_10_CONTEXT=candidate-only task run parent-hash context; parent code unused/unemitted and parent card not required
PREFLIGHT_11_REPRO=producer x2 independent verifier x2 exact commit byte comparison and manifests
PREFLIGHT_12_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0
PREFLIGHT_13_SCOPE=artifact readiness only; no complete-v11 predictor utility search novelty or prospective claim
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  "${cards}" "${per_parent}" "${identity}" "${status_edges}" "${status_registry}" \
  "${construction}" "${answer_summary}" "${support_summary}" "${pair_train}" \
  "${pair_frozen}" "${pair_extension}" > "${staging}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in ordinary formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${staging}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_choice_benchmark_materializer.py \
      phase1/tests/test_source_decision_answerability.py -q \
    > "${staging}/focused_tests.stdout" 2> "${staging}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --cards "${cards}"
  --answerability-protocol "${answer_protocol}"
  --per-parent "${per_parent}"
  --identity-registry "${identity}"
  --status-edges "${status_edges}"
  --status-registry "${status_registry}"
  --construction "${construction}"
  --answerability-summary "${answer_summary}"
  --support-summary "${support_summary}"
  --pair "train=${pair_train}"
  --pair "frozen=${pair_frozen}"
  --pair "extension=${pair_extension}"
  --root "ours=/research/d7/spc/yzyang4/aira-dojo-runs/aira-dojo"
  --root "senior_older=/research/d7/spc/yzyang4/external/senior_runs"
  --root "senior_0806=/research/d7/spc/yzyang4/external/senior_data/extract_0806"
  --root "senior_0807=/research/d7/spc/yzyang4/external/senior_data/extract_0807"
  --root "senior_0808=/research/d7/spc/yzyang4/external/senior_data/extract_0808"
  --root "senior_0809=/research/d7/spc/yzyang4/external/senior_data/extract_0809"
  --root "senior_0810=/research/d7/spc/yzyang4/external/senior_data/extract_0810_codex_20260813"
  --root "senior_0811=/research/d7/spc/yzyang4/external/senior_data/extract_0811_codex_20260813_v2"
  --source-commit "${commit}"
)
producer=("${python_bin}" -m phase1.source_choice_benchmark_materializer "${common[@]}")
verifier=("${python_bin}" -m phase1.verify_source_choice_benchmark_materialization "${common[@]}")

for replica in a b; do
  printf '%q ' "${producer[@]}" --public-output "${staging}/public_${replica}" \
    --vault-output "${vault_staging}/vault_${replica}" \
    > "${staging}/producer_${replica}.command.txt"
  printf '\n' >> "${staging}/producer_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/producer_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
    "${producer[@]}" --public-output "${staging}/public_${replica}" \
      --vault-output "${vault_staging}/vault_${replica}" \
    > "${staging}/producer_${replica}.stdout" 2> "${staging}/producer_${replica}.stderr"
done
diff -r "${staging}/public_a" "${staging}/public_b" > "${staging}/public_reproducibility.diff"
diff -r "${vault_staging}/vault_a" "${vault_staging}/vault_b" \
  > "${staging}/vault_reproducibility.diff"

for replica in a b; do
  printf '%q ' "${verifier[@]}" --public-output "${staging}/public_${replica}" \
    --vault-output "${vault_staging}/vault_${replica}" \
    --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.command.txt"
  printf '\n' >> "${staging}/verifier_${replica}.command.txt"
  /usr/bin/time -v -o "${staging}/verifier_${replica}.time.txt" \
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
    "${verifier[@]}" --public-output "${staging}/public_${replica}" \
      --vault-output "${vault_staging}/vault_${replica}" \
      --output "${staging}/verification_${replica}.json" \
    > "${staging}/verifier_${replica}.stdout" 2> "${staging}/verifier_${replica}.stderr"
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|outcome_registry|regrade|first.?960)(/|[._-])|/(candidate_scores|frozen_per_parent)\.csv' "${staging}"/*.strace* || true; } | wc -l )
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

find "${staging}" "${vault_staging}" -type f -printf '%P\n' | LC_ALL=C sort \
  > "${staging}/file_manifest.txt"
name_hits=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
printf '%s\n' "${name_hits}" > "${staging}/credential_filename_hits.txt"
content_hits=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  artifact_hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{10,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  [[ ${grep_rc} == 0 || ${grep_rc} == 1 ]]
  content_hits=$((content_hits + artifact_hits))
done < <(find "${staging}" "${vault_staging}" -type f -print0)
printf '%s\n' "${content_hits}" > "${staging}/credential_content_hits.txt"
[[ ${name_hits} == 0 && ${content_hits} == 0 ]]

printf 'SOURCE_CHOICE_BENCHMARK_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
date -u +%Y-%m-%dT%H:%M:%SZ > "${staging}/completed_at_utc.txt"
(
  cd "${staging}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
(
  cd "${vault_staging}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${staging}" "${vault_staging}"
mv "${staging}" "${final}"
mv "${vault_staging}" "${vault_final}"
trap - EXIT
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${final}/public_a/summary.json")
missing=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["missing_candidates_materialized"])' "${final}/public_a/summary.json")
printf 'SOURCE_CHOICE_BENCHMARK_RUNNER_DONE status=%s missing_candidates=%s result=%s vault=%s\n' \
  "${status}" "${missing}" "${final}" "${vault_final}"
