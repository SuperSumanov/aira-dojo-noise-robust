#!/usr/bin/env bash
set -Eeo pipefail
source /uac/y24/yzyang4/env_setup.sh
source /research/d7/spc/yzyang4/venvs/exp/bin/activate
set -u
umask 077

if [[ $# -ne 2 || ! $2 =~ ^[0-9a-f]{40}$ ]]; then
  echo 'usage: run_split_integrity_certificate_887_20260828.sh OUTPUT_ROOT EXPECTED_COMMIT' >&2
  exit 64
fi

readonly output=$1
readonly expected_commit=$2
readonly protocol=phase1/split_integrity_certificate_887_protocol_v1.json
readonly protocol_sha=779ac3f1f5aef522a305b22b578dace2c0a8462fe748a7cd1b30dd20037ef5da
readonly within=phase1/results/prospective_identifier_erased_clone_887_20260828_519815d
readonly historical=phase1/results/historical_train_future_identifier_erased_overlap_887_20260828_ec67d1a
readonly within_formal=/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/formal-519815d-887491a-v1
readonly within_postflight=/research/d7/spc/yzyang4/prospective-identifier-erased-clone-887/postflight-519815d-887491a-v1
readonly historical_formal=/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/formal-ec67d1a-887491a-v1
readonly historical_postflight=/research/d7/spc/yzyang4/historical-train-future-identifier-erased-overlap/postflight-ec67d1a-887491a-v1
readonly python=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly credential_pattern='(^|[^[:alnum:]_])(sk-[A-Za-z0-9._-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,})'

test "$(git rev-parse HEAD)" = "${expected_commit}"
test ! -e "${output}"
mkdir -p "${output}"
failure_receipt() {
  rc=$?
  if (( rc != 0 )); then
    printf '%s\n' "${rc}" > "${output}/FAILED_RC" 2>/dev/null || true
  fi
  exit "${rc}"
}
trap failure_receipt EXIT

test -d "${within}"
test -d "${historical}"
test "$(sha256sum "${protocol}" | awk '{print $1}')" = "${protocol_sha}"
for root in "${within_formal}" "${within_postflight}" \
  "${historical_formal}" "${historical_postflight}"; do
  test -f "${root}/COMPLETE"
  test ! -e "${root}/FAILED_RC"
  (cd "${root}" && sha256sum -c SHA256SUMS > /dev/null)
done
cmp "${within}/formal_summary.json" "${within_formal}/formal_summary.json"
cmp "${within}/independent_recheck.json" "${within_postflight}/independent_recheck.json"
cmp "${historical}/formal_summary.json" "${historical_formal}/formal_summary.json"
cmp "${historical}/independent_recheck.json" "${historical_postflight}/independent_recheck.json"
jq -e \
  --arg formal "$(sha256sum "${within_formal}/SHA256SUMS" | awk '{print $1}')" \
  --arg postflight "$(sha256sum "${within_postflight}/SHA256SUMS" | awk '{print $1}')" '
  .formal_sha256sums_file_sha256 == $formal
  and .postflight_sha256sums_file_sha256 == $postflight
' "${within}/source_bindings.json" > /dev/null
jq -e \
  --arg formal "$(sha256sum "${historical_formal}/SHA256SUMS" | awk '{print $1}')" \
  --arg postflight "$(sha256sum "${historical_postflight}/SHA256SUMS" | awk '{print $1}')" '
  .formal_sha256sums_file_sha256 == $formal
  and .postflight_sha256sums_file_sha256 == $postflight
' "${historical}/source_bindings.json" > /dev/null

cat > "${output}/preflight_13.txt" <<EOF
01_direction=Decision Corpus + Predictor Benchmark + Audit Protocol only; PASS
02_question=combine exact 435-run within-future and historical-to-future identifier-erased overlap receipts; PASS
03_population=435 future runs/11906 endpoints and 333 historical runs/5519 endpoints; PASS
04_inputs=two exact six-file safe result packages only; PASS
05_representation=python_token_identifier_erased_v1 with 17/20 primary and 19/20 sensitivity; PASS
06_classification=ZERO then LOW_WITH_EXCEPTIONS then NO_CERTIFICATE in frozen order; PASS
07_repetitions=builder A/B and non-importing independent verifier A/B,byte identity required; PASS
08_hashes=protocol,package manifests,remote formal/postflight manifests,result,source commit all bound; PASS
09_randomness=none,PYTHONHASHSEED=0,numeric threads=1; PASS
10_resources=CPU only,1800-second test/300-second build timeout,32-GiB virtual memory,GPU/API/model-fit/base-update 0/0/0/0; PASS
11_security=no corpus/archive/identity/label/outcome/prediction inputs,credential scan; PASS
12_claim_boundary=provisional until first960 plus closure,no semantic/pretraining claim; PASS
13_failure=immutable FAILED_RC,no input,threshold,representation,population or classification rescue; PASS
EOF

export PYTHONDONTWRITEBYTECODE=1
export PYTHONHASHSEED=0
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
ulimit -v 33554432

git status --porcelain=v1 > "${output}/git_status_before.txt"
test ! -s "${output}/git_status_before.txt"
timeout 1800s "${python}" -m pytest -q phase1/tests/test_split_integrity_certificate_887.py \
  > "${output}/focused_tests.txt"
timeout 1800s "${python}" -m pytest -q phase1/tests > "${output}/full_tests.txt"

builder=(
  "${python}" -m phase1.build_split_integrity_certificate_887
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
  --within-package "${within}"
  --historical-package "${historical}"
)
timeout 300s "${builder[@]}" --output "${output}/certificate_a.json" \
  > "${output}/builder_a.stdout" 2> "${output}/builder_a.stderr"
timeout 300s "${builder[@]}" --output "${output}/certificate_b.json" \
  > "${output}/builder_b.stdout" 2> "${output}/builder_b.stderr"
test ! -s "${output}/builder_a.stderr"
test ! -s "${output}/builder_b.stderr"
cmp "${output}/certificate_a.json" "${output}/certificate_b.json"
certificate_sha=$(sha256sum "${output}/certificate_a.json" | awk '{print $1}')

verifier=(
  "${python}" -m phase1.verify_split_integrity_certificate_887
  --protocol "${protocol}"
  --expect-protocol-sha256 "${protocol_sha}"
  --within-package "${within}"
  --historical-package "${historical}"
  --certificate "${output}/certificate_a.json"
  --expect-certificate-sha256 "${certificate_sha}"
)
timeout 300s "${verifier[@]}" --output "${output}/verification_a.json" \
  > "${output}/verifier_a.stdout" 2> "${output}/verifier_a.stderr"
timeout 300s "${verifier[@]}" --output "${output}/verification_b.json" \
  > "${output}/verifier_b.stdout" 2> "${output}/verifier_b.stderr"
test ! -s "${output}/verifier_a.stderr"
test ! -s "${output}/verifier_b.stderr"
cmp "${output}/verification_a.json" "${output}/verification_b.json"

jq -e \
  --arg snapshot 887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697 '
  .status == "PROVISIONAL_SPLIT_INTEGRITY_CERTIFICATE_BUILD_COMPLETE"
  and .snapshot_sha256 == $snapshot
  and (.classification == "PROVISIONAL_ZERO_LINK_SPLIT_INTEGRITY_CERTIFICATE"
       or .classification == "PROVISIONAL_LOW_OVERLAP_CERTIFICATE_WITH_EXCEPTIONS"
       or .classification == "NO_SPLIT_INTEGRITY_CERTIFICATE")
  and .future_population == {"closure":false,"endpoints":11906,"runs":435}
  and .historical_population == {"endpoints":5519,"runs":333}
  and .security.raw_corpus_or_archive_reopened == false
  and .security.task_run_card_code_or_edge_identities_read == false
  and .security.prospective_label_outcome_prediction_values_read == false
  and .security.gpu_api_model_fit_base_update == [0,0,0,0]
  and .security.randomness_used == false
' "${output}/certificate_a.json" > /dev/null
jq -e \
  --arg sha "${certificate_sha}" '
  .status == "INDEPENDENT_SPLIT_INTEGRITY_CERTIFICATE_VERIFIED"
  and .certificate_sha256 == $sha
  and .imports_builder == false
  and .raw_corpus_or_archive_reopened == false
  and .identity_values_read == false
  and .prospective_outcomes_or_prediction_values_read == false
  and .gpu_api_model_fit_base_update == [0,0,0,0]
  and .randomness_used == false
' "${output}/verification_a.json" > /dev/null

credential_files=$(grep -R -E -i -l "${credential_pattern}" "${output}" \
  --exclude=credential_scan_receipt.txt --exclude=SHA256SUMS || true)
test -z "${credential_files}"
filename_hits=$(find "${output}" -type f -printf '%f\n' \
  | grep -Eic '(\.env|api[_-]?key|token|secret)' || true)
test "${filename_hits}" = 0
cat > "${output}/access_attestation.txt" <<EOF
boundary_aware_credential_file_hits=0
credential_filename_hits=0
raw_corpus_or_archive_reopened=false
task_run_card_code_or_edge_identities_read=false
prospective_label_outcome_prediction_values_read=false
gpu_api_model_fit_base_update=0/0/0/0
EOF

git status --porcelain=v1 > "${output}/git_status_after.txt"
test ! -s "${output}/git_status_after.txt"
(
  cd "${output}"
  find . -type f ! -name SHA256SUMS ! -name COMPLETE -print0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum > SHA256SUMS
  touch COMPLETE
)
chmod -R a-w "${output}"
trap - EXIT
cat "${output}/certificate_a.json"
sha256sum "${output}/certificate_a.json" "${output}/verification_a.json" \
  "${output}/SHA256SUMS"
printf '%s\n' FORMAL_SPLIT_INTEGRITY_CERTIFICATE_887_COMPLETE
