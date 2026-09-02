#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

set +u
source /uac/y24/yzyang4/env_setup.sh >/dev/null 2>&1
set -u

readonly public_commit="${RELEASE_PREPARED_TEXT_PUBLIC_COMMIT:?set RELEASE_PREPARED_TEXT_PUBLIC_COMMIT}"
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly data_root=/research/d7/spc/yzyang4/mle-bench-data
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly kaggle_bin=/research/d7/spc/yzyang4/venvs/exp/bin/kaggle
readonly contract_sha=836310cfe5855223247049eb3e02f2ce5bfcc2ce57aba04283915d5bb4a1ea25
readonly short="${public_commit:0:7}"
readonly base=/research/d7/spc/yzyang4/release-prepared-text-successor-v2
readonly worktree="${base}/worktree-${short}"
readonly root="${base}/formal-${short}-r1"
readonly private="${root}/private"
readonly public="${root}/public"
readonly log="${root}/runner.log"

fail() {
  local rc=$?
  set +e
  if [[ -d "${root}" ]]; then
    printf '%s\n' "${rc}" >"${root}/FAILED_RC"
    chmod 0400 "${root}/FAILED_RC" 2>/dev/null || true
  fi
  printf 'RELEASE_PREPARED_TEXT_SUCCESSOR_V2=FAIL rc=%s\n' "${rc}" >&2
  exit "${rc}"
}
trap fail ERR

[[ "${public_commit}" =~ ^[0-9a-f]{40}$ ]]
[[ ! -e "${root}" ]]
[[ ! -e "${worktree}" ]]
mkdir -p "${base}" "${root}" "${private}/downloads" "${private}/prepared" \
  "${private}/logs" "${private}/traces" "${public}"
chmod 0700 "${root}" "${private}" "${private}/downloads" "${private}/prepared" \
  "${private}/logs" "${private}/traces" "${public}"
: >"${log}"
chmod 0600 "${log}"
exec > >(tee -a "${log}") 2>&1

printf 'PREFLIGHT_01_OBJECTIVE=bounded_missing_prepared_text_successor\n'
git -C "${repo}" cat-file -e "${public_commit}^{commit}"
printf 'PREFLIGHT_02_EXACT_COMMIT=%s\n' "${public_commit}"
[[ -x "${python_bin}" && -x "${kaggle_bin}" ]]
"${python_bin}" -c 'import pytest'
command -v strace >/dev/null
command -v timeout >/dev/null
command -v unzip >/dev/null
printf 'PREFLIGHT_03_RUNTIME=exp-python/kaggle/pytest/strace/timeout/unzip\n'
for task in aptos2019-blindness-detection histopathologic-cancer-detection; do
  [[ ! -e "${data_root}/${task}/prepared" ]]
done
printf 'PREFLIGHT_04_ACTIVE_PREPARED_PATHS_ABSENT=true\n'
printf 'PREFLIGHT_05_REQUESTS=5_fixed_csv_files\n'
printf 'PREFLIGHT_06_FILE_LIMIT_BYTES=67108864\n'
printf 'PREFLIGHT_07_TOTAL_EXTRACTED_LIMIT_BYTES=134217728\n'
printf 'PREFLIGHT_08_TIMEOUT_PER_FILE_SECONDS=600\n'
printf 'PREFLIGHT_09_ARCHIVE_MEMBERS=exactly_one_safe_member\n'
printf 'PREFLIGHT_10_PROMOTION_DURING_RUN=false\n'
printf 'PREFLIGHT_11_PROSPECTIVE_PATHS_ALLOWED=false\n'
printf 'PREFLIGHT_12_GPU_PAID_MODEL_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'
printf 'PREFLIGHT_13_ACCESS_IS_REDISTRIBUTION_PERMISSION=false\n'

GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null -C "${repo}" \
  worktree add --detach "${worktree}" "${public_commit}"
[[ "$(git -C "${worktree}" rev-parse HEAD)" == "${public_commit}" ]]
[[ -z "$(git -C "${worktree}" status --porcelain --untracked-files=no)" ]]
cd "${worktree}"
readonly contract=phase1/release_prepared_text_successor_v2.json
readonly focused=phase1/tests/test_release_prepared_text_successor_v2.py
[[ "$(sha256sum "${contract}" | awk '{print $1}')" == "${contract_sha}" ]]
"${python_bin}" -m pytest -q "${focused}" | tee "${public}/focused_tests.txt"
"${python_bin}" -m pytest -q phase1/tests | tee "${public}/full_tests.txt"

readonly competitions=(
  aptos2019-blindness-detection
  aptos2019-blindness-detection
  aptos2019-blindness-detection
  histopathologic-cancer-detection
  histopathologic-cancer-detection
)
readonly filenames=(
  sample_submission.csv
  test.csv
  train.csv
  sample_submission.csv
  train_labels.csv
)
readonly credential_re='(^|[^A-Za-z0-9])(sk-(or-v1-|ws-)?[A-Za-z0-9._-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|authorization:[[:space:]]*bearer[[:space:]]+[A-Za-z0-9._-]{20,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{20,})'

for index in "${!competitions[@]}"; do
  competition="${competitions[$index]}"
  filename="${filenames[$index]}"
  download_dir="${private}/downloads/${index}"
  destination_dir="${private}/prepared/${competition}/prepared"
  stdout_path="${private}/logs/${index}.stdout"
  stderr_path="${private}/logs/${index}.stderr"
  mkdir -p "${download_dir}" "${destination_dir}"
  chmod 0700 "${download_dir}" "${destination_dir}"

  timeout 600s strace -ff -qq -e trace=file,network \
    -o "${private}/traces/request-${index}" \
    "${kaggle_bin}" competitions download -c "${competition}" -f "${filename}" \
      -p "${download_dir}" --force >"${stdout_path}" 2>"${stderr_path}"
  credential_hits=$(grep -Eih "${credential_re}" "${stdout_path}" "${stderr_path}" 2>/dev/null \
    | wc -l || true)
  [[ "${credential_hits}" == 0 ]]

  mapfile -t payloads < <(find "${download_dir}" -mindepth 1 -maxdepth 1 -type f -print)
  [[ "${#payloads[@]}" == 1 ]]
  payload="${payloads[0]}"
  [[ -s "${payload}" ]]
  [[ "$(stat -c '%s' "${payload}")" -le 67108864 ]]
  destination="${destination_dir}/${filename}"
  [[ ! -e "${destination}" ]]

  if unzip -tqq "${payload}" >/dev/null 2>&1; then
    mapfile -t members < <(unzip -Z1 "${payload}")
    [[ "${#members[@]}" == 1 ]]
    [[ "${members[0]}" == "${filename}" ]]
    unzip -p "${payload}" "${filename}" >"${destination}"
  else
    [[ "$(basename "${payload}")" == "${filename}" ]]
    cp -- "${payload}" "${destination}"
  fi
  chmod 0600 "${destination}"
  [[ -s "${destination}" ]]
  [[ "$(stat -c '%s' "${destination}")" -le 67108864 ]]
  printf 'REQUEST_%s=PASS competition=%s filename=%s bytes=%s\n' \
    "${index}" "${competition}" "${filename}" "$(stat -c '%s' "${destination}")"
done

readonly verify_a="${public}/verification_a.json"
readonly verify_b="${public}/verification_b.json"
"${python_bin}" -m phase1.verify_release_prepared_text_successor_v2 \
  --contract "${contract}" --contract-sha256 "${contract_sha}" \
  --prepared-root "${private}/prepared" --output "${verify_a}"
"${python_bin}" -m phase1.verify_release_prepared_text_successor_v2 \
  --contract "${contract}" --contract-sha256 "${contract_sha}" \
  --prepared-root "${private}/prepared" --output "${verify_b}"
cmp "${verify_a}" "${verify_b}"

prospective_hits=$(grep -hE '/prospective_decision_v1|target300|target522|label_vault|outcome_vault|prediction_escrow' \
  "${private}"/traces/* 2>/dev/null | wc -l || true)
public_credential_hits=$(grep -hEi "${credential_re}" "${public}"/* | wc -l || true)
public_absolute_path_hits=$(grep -hE '/research/|/home/|C:\\' "${public}"/* | wc -l || true)
[[ "${prospective_hits}" == 0 ]]
[[ "${public_credential_hits}" == 0 ]]
[[ "${public_absolute_path_hits}" == 0 ]]
for task in aptos2019-blindness-detection histopathologic-cancer-detection; do
  [[ ! -e "${data_root}/${task}/prepared" ]]
done

"${python_bin}" - "${verify_a}" "${public_commit}" "${public}/formal_summary.json" <<'PY'
import hashlib, json, pathlib, sys
verification_path, commit, output_path = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
value = json.loads(verification_path.read_text(encoding="utf-8"))
assert value["status"] == "PASS"
assert value["totals"]["competitions"] == 2
assert value["totals"]["files"] == 5
payload = {
    "protocol": "release-prepared-text-successor-v2-formal-summary",
    "status": "PASS_STAGED_NOT_PROMOTED",
    "source_commit": commit,
    "verification_sha256": hashlib.sha256(verification_path.read_bytes()).hexdigest(),
    "competitions": 2,
    "files": 5,
    "bytes": value["totals"]["bytes"],
    "rows_excluding_headers": value["totals"]["rows_excluding_headers"],
    "active_prepared_root_modified": False,
    "raw_csvs_public_or_in_git": False,
    "prospective_paths_read": False,
    "kaggle_data_api_requests": 5,
    "gpu_paid_model_api_model_fit_base_update": "0/0/0/0",
}
output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

find "${public}" -type f -exec chmod 0400 {} +
find "${private}" -type f -exec chmod 0400 {} +
find "${private}" -type d -exec chmod 0500 {} +
printf '%s\n' 'RELEASE_PREPARED_TEXT_SUCCESSOR_V2_PASS' >"${root}/COMPLETE"
chmod 0400 "${root}/COMPLETE" "${log}"
chmod 0500 "${public}" "${root}"
printf 'RELEASE_PREPARED_TEXT_SUCCESSOR_V2=PASS root=%s\n' "${root}"
