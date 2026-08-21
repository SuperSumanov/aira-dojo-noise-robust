#!/usr/bin/env bash
set -eo pipefail
source /uac/y24/yzyang4/env_setup.sh
set -u
umask 077

if [[ $# != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_source_decision_answerability_20260821.sh FULL_COMMIT' >&2
  exit 64
fi

commit=$1
short=${commit:0:7}
base_repo=/research/d7/spc/yzyang4/aira-dojo
worktree=/research/d7/spc/yzyang4/worktrees/source_decision_answerability_${short}_nosmudge
output=/research/d7/spc/yzyang4/source-decision-answerability/${short}-v1
per_parent=/research/d7/spc/yzyang4/raw-choice-audit-v11-6610618-a2/producer/per_parent.csv
identity=/research/d7/spc/yzyang4/source-identity-recovery-v11-3faf001-a1/producer/per_parent.jsonl
status_edges=/research/d7/spc/yzyang4/status-certified-edge-manifest/c9bfc21-v1/producer_a/edges.jsonl
pair_train=${base_repo}/phase1/v11_decision/decision_train_v11_b0.jsonl
pair_frozen=${base_repo}/phase1/v11_decision/decision_frozen_v11_b0.jsonl
pair_extension=${base_repo}/phase1/v11_decision/decision_extension_v11_b0.jsonl
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
protocol_rel=phase1/source_decision_answerability_protocol_v1.json
expected_parent_sha=75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03
expected_identity_sha=b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2
expected_status_sha=dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d
expected_train_sha=bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca
expected_frozen_sha=2717e331c9e7156bdc47a31ea1fdd13c5eecb4465c33ad249c41bfac597a8da8
expected_extension_sha=2facb5a1cb192640229395b9befe4a824bd1e5f1477a2da61eb653d3a6c1ca9c

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1

normalized_sha() {
  "${python_bin}" - "$1" <<'PY'
import hashlib
import pathlib
import sys
text = pathlib.Path(sys.argv[1]).read_bytes().decode("utf-8")
print(hashlib.sha256(text.replace("\r\n", "\n").replace("\r", "\n").encode()).hexdigest())
PY
}

for input in "${per_parent}" "${identity}" "${status_edges}" "${pair_train}" "${pair_frozen}" "${pair_extension}"; do
  test -f "${input}"
done
test -x "${python_bin}"
test "$(sha256sum "${per_parent}" | awk '{print $1}')" = "${expected_parent_sha}"
test "$(sha256sum "${identity}" | awk '{print $1}')" = "${expected_identity_sha}"
test "$(sha256sum "${status_edges}" | awk '{print $1}')" = "${expected_status_sha}"
test "$(normalized_sha "${pair_train}")" = "${expected_train_sha}"
test "$(normalized_sha "${pair_frozen}")" = "${expected_frozen_sha}"
test "$(normalized_sha "${pair_extension}")" = "${expected_extension_sha}"
test ! -e "${worktree}"
test ! -e "${output}"

git -C "${base_repo}" fetch fork phase1-value-critic \
  > /tmp/source_answerability_fetch_${short}.stdout \
  2> /tmp/source_answerability_fetch_${short}.stderr
test "$(git -C "${base_repo}" rev-parse fork/phase1-value-critic)" = "${commit}"
GIT_LFS_SKIP_SMUDGE=1 git -C "${base_repo}" worktree add --detach "${worktree}" "${commit}" \
  > /tmp/source_answerability_worktree_${short}.stdout \
  2> /tmp/source_answerability_worktree_${short}.stderr
test "$(git -C "${worktree}" rev-parse HEAD)" = "${commit}"
test -z "$(git -C "${worktree}" status --porcelain --untracked-files=all)"
export PYTHONPATH=${worktree}
protocol=${worktree}/${protocol_rel}
test -f "${protocol}"

mkdir -p "${output}"
cp /tmp/source_answerability_fetch_${short}.stdout "${output}/fetch.stdout"
cp /tmp/source_answerability_fetch_${short}.stderr "${output}/fetch.stderr"
cp /tmp/source_answerability_worktree_${short}.stdout "${output}/worktree.stdout"
cp /tmp/source_answerability_worktree_${short}.stderr "${output}/worktree.stderr"
printf '%s\n' "${commit}" > "${output}/control_commit.txt"
printf 'per_parent=%s\nidentity=%s\nstatus_edges=%s\ntrain_pair_normalized_lf=%s\nfrozen_pair_normalized_lf=%s\nextension_pair_normalized_lf=%s\n' \
  "${expected_parent_sha}" "${expected_identity_sha}" "${expected_status_sha}" \
  "${expected_train_sha}" "${expected_frozen_sha}" "${expected_extension_sha}" \
  > "${output}/input_sha256.txt"
git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${output}/worktree_status_before.txt"
"${python_bin}" --version > "${output}/python_version.txt" 2>&1
git --version > "${output}/git_version.txt"

cat > "${output}/preflight_matrix.txt" <<EOF
PREFLIGHT_01_DIRECTION=source winner answerability for the current failure-aware Decision Corpus release
PREFLIGHT_02_QUESTION=does status-certified validity recover a material number of unique source winners beyond published finite orientations
PREFLIGHT_03_INPUT=3252 parent table identity registry three b0 pair files and 2079 explicit validity edges all SHA pinned
PREFLIGHT_04_UNIT=all 3252 parents; unavailable source identity remains unanswered
PREFLIGHT_05_GRAPH=better-to-worse plus valid-to-invalid DAG; unique winner reaches every source candidate by transitive closure
PREFLIGHT_06_GATES=added winners 400 overall gain 0.10 train and frozen 0.08 status rate 0.80 task breadth and concentration
PREFLIGHT_07_SENSITIVITY=execution-error-only must independently pass every material gate
PREFLIGHT_08_ACCESS=no cards code obs grade gap regrade score-channel prospective outcome or first960
PREFLIGHT_09_REPRO=producer x2 verifier x2 exact commit immutable protocol and all input hashes
PREFLIGHT_10_RESOURCES=CPU only GPU 0 API 0 base-LLM update 0
PREFLIGHT_11_FAILURE=cycle identity endpoint context duplicate or material gate failure is fail-closed with no rescue
PREFLIGHT_12_SCOPE=no total order MAR predictor accuracy search utility algorithm novelty or first-only claim
PREFLIGHT_13_EXPECTED_WALL=under 30 minutes including full phase1 regression
EOF

if grep -IlE '(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY)' \
  "${per_parent}" "${identity}" "${status_edges}" "${pair_train}" "${pair_frozen}" "${pair_extension}" \
  > "${output}/input_credential_hits.txt"; then
  echo 'credential-shaped bytes found in formal input' >&2
  exit 2
fi

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/focused_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests/test_source_decision_answerability.py -q \
    > "${output}/focused_tests.stdout" 2> "${output}/focused_tests.stderr"
)

common=(
  --protocol "${protocol}"
  --per-parent "${per_parent}"
  --identity-registry "${identity}"
  --status-edges "${status_edges}"
  --pair "train=${pair_train}"
  --pair "frozen=${pair_frozen}"
  --pair "extension=${pair_extension}"
  --source-commit "${commit}"
)
producer=("${python_bin}" -m phase1.source_decision_answerability "${common[@]}")
verifier=("${python_bin}" -m phase1.verify_source_decision_answerability "${common[@]}")

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
diff -r "${output}/producer_a" "${output}/producer_b" \
  > "${output}/producer_reproducibility.diff"

printf '%q ' "${verifier[@]}" --artifact "${output}/producer_a" \
  --output "${output}/verification_a.json" > "${output}/verifier_a.command.txt"
printf '\n' >> "${output}/verifier_a.command.txt"
printf '%q ' "${verifier[@]}" --artifact "${output}/producer_b" \
  --output "${output}/verification_b.json" > "${output}/verifier_b.command.txt"
printf '\n' >> "${output}/verifier_b.command.txt"
/usr/bin/time -v -o "${output}/verifier_a.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_a.strace" \
  "${verifier[@]}" --artifact "${output}/producer_a" \
  --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
/usr/bin/time -v -o "${output}/verifier_b.time.txt" \
  strace -ff -e trace=file -o "${output}/verifier_b.strace" \
  "${verifier[@]}" --artifact "${output}/producer_b" \
  --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
diff "${output}/verification_a.json" "${output}/verification_b.json" \
  > "${output}/verifier_reproducibility.diff"

forbidden_hits=$( { grep -hEi '/(prospective_decision_v1|temporal_blind|score-channel|label_vault|outcome_registry|regrade|first.?960)' "${output}"/*.strace* || true; } | wc -l )
printf 'forbidden_scientific_path_hits=%s\n' "${forbidden_hits}" \
  > "${output}/trace_audit.txt"
test "${forbidden_hits}" = 0

(
  cd "${worktree}"
  /usr/bin/time -v -o "${output}/full_phase1_tests.time.txt" \
    "${python_bin}" -m pytest phase1/tests -q \
    > "${output}/full_phase1_tests.stdout" 2> "${output}/full_phase1_tests.stderr"
)
git -C "${worktree}" status --porcelain --untracked-files=all \
  > "${output}/worktree_status_after.txt"
test ! -s "${output}/worktree_status_before.txt"
test ! -s "${output}/worktree_status_after.txt"

find "${output}" -type f -printf '%P\n' | LC_ALL=C sort \
  | grep -iE '(^|/)(\.env|[^/]*(key|token|secret)[^/]*)$' \
  > "${output}/credential_filename_hits.txt" || true
test ! -s "${output}/credential_filename_hits.txt"
grep -rIEl '(^|[^A-Za-z0-9])(sk-(ws-)?[A-Za-z0-9._-]{16,}|hf_[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]{20,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)' \
  "${output}" > "${output}/credential_content_hits.txt" || true
test ! -s "${output}/credential_content_hits.txt"

printf 'SOURCE_DECISION_ANSWERABILITY_FORMAL_COMPLETE\n' > "${output}/COMPLETE"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name manifest_verification.txt -printf '%P\0' \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum --check SHA256SUMS > manifest_verification.txt
)
chmod -R a-w "${output}"
status=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output}/producer_a/summary.json")
published=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"]["published_winners"])' "${output}/producer_a/summary.json")
recovered=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"]["newly_identified_by_status"])' "${output}/producer_a/summary.json")
rate=$("${python_bin}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall"]["status_winner_rate"])' "${output}/producer_a/summary.json")
printf 'SOURCE_DECISION_ANSWERABILITY_RUNNER_DONE status=%s published=%s recovered=%s status_rate=%s output=%s\n' \
  "${status}" "${published}" "${recovered}" "${rate}" "${output}"
