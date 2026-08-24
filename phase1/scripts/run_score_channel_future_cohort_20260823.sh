#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# -lt 1 || $# -gt 2 || ! $1 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_score_channel_future_cohort_20260823.sh CONTROL_COMMIT [PREVIOUS_COHORT_DIR]' >&2
  exit 64
fi

commit=$1
previous=${2:-}
short=${commit:0:7}
expected_protocol_sha=54187f386ee18f009b57ccd04f851083160db3e607a4e8a760e070b276ac377d
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/future_identity_cohort_${short}_nosmudge
state=/research/d7/spc/yzyang4/prospective_decision_v1
source_root=/research/d7/spc/yzyang4/external/senior_data/mle
result_root=/research/d7/spc/yzyang4/score-channel-future-identity-cohort
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

test -x "${python_bin}"
test -d "${base_repo}"
test -d "${state}"
test -d "${source_root}"
test ! -e "${worktree}"
if [[ -n ${previous} ]]; then
  test -d "${previous}"
fi

mkdir -p "${result_root}"
bootstrap=${result_root}/.bootstrap-${short}.$$
mkdir "${bootstrap}"

failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${bootstrap}/FAILED_RC" 2>/dev/null || true
    chmod -R a-w "${bootstrap}" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

git -C "${base_repo}" fetch fork phase1-value-critic \
  > "${bootstrap}/fetch.stdout" 2> "${bootstrap}/fetch.stderr"
git -C "${base_repo}" merge-base --is-ancestor \
  "${commit}" fork/phase1-value-critic
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > "${bootstrap}/worktree.stdout" 2> "${bootstrap}/worktree.stderr"
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
git -C "${worktree}" status --porcelain --untracked-files=all > "${bootstrap}/status_before.txt"
test ! -s "${bootstrap}/status_before.txt"

protocol=${worktree}/phase1/score_channel_future_identifiability_protocol_v1.json
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${expected_protocol_sha}"
(
  cd "${worktree}"
  "${python_bin}" -m pytest -p no:cacheprovider \
    phase1/tests/test_score_channel_future_cohort.py \
    phase1/tests/test_score_channel_future_identifiability_protocol.py -q \
    > "${bootstrap}/focused_tests.stdout" 2> "${bootstrap}/focused_tests.stderr"
  "${python_bin}" -m pytest -p no:cacheprovider phase1/tests -q \
    > "${bootstrap}/phase1_tests.stdout" 2> "${bootstrap}/phase1_tests.stderr"
)

latest_before=$(tr -d '\r\n' < "${state}/LATEST")
observations_before=$(sha256sum "${state}/observations.json" | awk '{print $1}')
[[ ${latest_before} =~ ^[0-9a-f]{64}$ ]]
[[ ${observations_before} =~ ^[0-9a-f]{64}$ ]]
tag=${short}-${latest_before:0:12}-${observations_before:0:12}
final=${result_root}/${tag}
staging=${result_root}/.${tag}.tmp.$$
test ! -e "${final}"
test ! -e "${staging}"
mv "${bootstrap}" "${staging}"
bootstrap=${staging}

printf '%s\n' "${commit}" > "${staging}/control_commit.txt"
printf '%s\n' "${latest_before}" > "${staging}/latest_before.txt"
printf '%s\n' "${observations_before}" > "${staging}/observations_before_sha256.txt"
printf '%s\n' "${expected_protocol_sha}" > "${staging}/protocol_sha256.txt"
"${python_bin}" --version > "${staging}/python_version.txt" 2>&1
git --version > "${staging}/git_version.txt"

cat > "${staging}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=future score-channel truth-support cohort identity closure
PREFLIGHT_02_QUESTION=has the frozen temporal cohort reached 300 accepted unique physical runs without reading truth
PREFLIGHT_03_INPUT=LATEST transaction hash ${latest_before}; observations hash ${observations_before}; protocol ${expected_protocol_sha}
PREFLIGHT_04_UNIT=complete accepted archive then unique physical run; no partial archive salvage
PREFLIGHT_05_ORDER=mtime_ns then relative-path UTF-8 bytes; stop at first unresolved archive
PREFLIGHT_06_REJECTIONS=structural rejection counts zero runs and remains in settled prefix
PREFLIGHT_07_CLOSURE=include complete archive crossing 300 runs; prior output must survive as exact prefix
PREFLIGHT_08_LEAKAGE=only transaction metadata observation metadata intake summary archive manifest source provenance
PREFLIGHT_09_FORBIDDEN=raw tar payload blind code label vault score directory outcome and prediction
PREFLIGHT_10_REPRO=producer x2 independent verifier x2 byte comparison and fresh no-smudge commit
PREFLIGHT_11_FAILURE=metadata drift ordering gap duplicate run SHA mismatch or forbidden open fails closed
PREFLIGHT_12_RESOURCES=single-thread CPU; GPU=0; API=0; model-fit=0; base-LLM-update=0
PREFLIGHT_13_NEXT=PASS closure only permits frozen truth-support CPU audit; replay remains unauthorized
EOF

common=(
  --protocol "${protocol}"
  --expect-protocol-sha256 "${expected_protocol_sha}"
  --state-root "${state}"
  --source-root "${source_root}"
  --repo-root "${worktree}"
)
if [[ -n ${previous} ]]; then
  common+=(--previous-dir "${previous}")
fi

for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/producer_${replica}.strace" \
      "${python_bin}" -m phase1.score_channel_future_cohort \
        "${common[@]}" --out-dir "${staging}/producer_${replica}" \
        > "${staging}/producer_${replica}.stdout" \
        2> "${staging}/producer_${replica}.stderr"
  )
done
diff -r "${staging}/producer_a" "${staging}/producer_b" \
  > "${staging}/producer_reproducibility.diff"

for replica in a b; do
  (
    cd "${worktree}"
    strace -ff -e trace=file -o "${staging}/verifier_${replica}.strace" \
      "${python_bin}" -m phase1.verify_score_channel_future_cohort \
        "${common[@]}" --cohort-dir "${staging}/producer_a" \
        --receipt "${staging}/verification_${replica}.json" \
        > "${staging}/verifier_${replica}.stdout" \
        2> "${staging}/verifier_${replica}.stderr"
  )
done
diff "${staging}/verification_a.json" "${staging}/verification_b.json" \
  > "${staging}/verifier_reproducibility.diff"

latest_after=$(tr -d '\r\n' < "${state}/LATEST")
observations_after=$(sha256sum "${state}/observations.json" | awk '{print $1}')
printf '%s\n' "${latest_after}" > "${staging}/latest_after.txt"
printf '%s\n' "${observations_after}" > "${staging}/observations_after_sha256.txt"
"${python_bin}" -c 'import json,sys; value=json.load(open(sys.argv[1])); assert value["inputs"]["latest_sha256"] == sys.argv[2]; assert value["inputs"]["observations_sha256"] == sys.argv[3]' \
  "${staging}/producer_a/summary.json" "${latest_before}" "${observations_before}"
if [[ ${latest_after} == "${latest_before}" && ${observations_after} == "${observations_before}" ]]; then
  printf 'false\n' > "${staging}/production_state_advanced_after_verification.txt"
else
  # A later atomic monitor poll does not invalidate the already hash-bound producer/verifier
  # receipt. Producer A/B equality and both independent verifier passes establish that all
  # scientific reads used the exact pre-run LATEST and observations hashes above.
  printf 'true\n' > "${staging}/production_state_advanced_after_verification.txt"
fi

forbidden_open_count=$( {
  grep -hEi \
    'open(at|at2)?\(.*(\.tar\.gz|label_vault\.jsonl|all_blind_views\.jsonl|eligible_blind_manifest\.jsonl|/scores/)' \
    "${staging}"/*.strace* || true
} | wc -l )
printf '%s\n' "${forbidden_open_count}" > "${staging}/forbidden_open_count.txt"
test "${forbidden_open_count}" -eq 0

git -C "${worktree}" status --porcelain --untracked-files=all > "${staging}/status_after.txt"
test ! -s "${staging}/status_after.txt"
find "${staging}" -type f -printf '%P\n' | LC_ALL=C sort > "${staging}/file_manifest.txt"
filename_count=$(grep -icE 'env|key|token|secret' "${staging}/file_manifest.txt" || true)
content_count=0
while IFS= read -r -d '' artifact; do
  grep_rc=0
  hits=$(grep -IicE '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{16,}|api[_-]?key[[:space:]]*[:=]|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${artifact}") || grep_rc=$?
  test "${grep_rc}" -eq 0 -o "${grep_rc}" -eq 1
  content_count=$((content_count + hits))
done < <(find "${staging}" -type f -print0)
printf '%s\n' "${filename_count}" > "${staging}/filename_scan_count.txt"
printf '%s\n' "${content_count}" > "${staging}/content_scan_count.txt"
test "${filename_count}" -eq 0
test "${content_count}" -eq 0

date -u +%Y-%m-%dT%H:%M:%SZ > "${staging}/completed_at_utc.txt"
printf 'SCORE_CHANNEL_FUTURE_IDENTITY_COHORT_FORMAL_COMPLETE\n' > "${staging}/COMPLETE"
(
  cd "${staging}"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
)
mv "${staging}" "${final}"
staging=${final}
cohort_status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' \
  "${final}/producer_a/summary.json")
if [[ ${cohort_status} == FUTURE_COHORT_IDENTITY_CLOSED_TRUTH_UNREAD ]]; then
  (
    cd "${worktree}"
    "${python_bin}" -m phase1.score_channel_future_closure_anchor \
      --formal-result-dir "${final}" \
      --result-root "${result_root}" \
      --repo-root "${worktree}" \
      --anchor "${result_root}/FIRST_CLOSED_COHORT_ANCHOR.json" \
      > /dev/null
  )
fi
chmod -R a-w "${final}"
trap - EXIT

printf 'result_dir=%s\n' "${final}"
tail -n 1 "${final}/focused_tests.stdout"
tail -n 1 "${final}/phase1_tests.stdout"
cat "${final}/producer_a.stdout"
"${python_bin}" -c 'import json,sys; s=json.load(open(sys.argv[1])); print(json.dumps({"status":s["status"],"inventory":s["inventory"],"closure":s["closure"]},sort_keys=True))' \
  "${final}/producer_a/summary.json"
sha256sum "${final}/SHA256SUMS"
