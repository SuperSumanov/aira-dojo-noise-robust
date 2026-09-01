#!/usr/bin/env bash
set -eo pipefail
umask 077
source "$HOME/env_setup.sh"
set -u

readonly public_commit="${GENERATOR_COMPLETION_PUBLIC_COMMIT:?set GENERATOR_COMPLETION_PUBLIC_COMMIT}"
readonly repo=/research/d7/spc/yzyang4/aira-dojo
readonly python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
readonly archived_root=/research/d7/spc/yzyang4/archived-generator-provenance-v1/formal-bfc5a70-r6
readonly archived_post=/research/d7/spc/yzyang4/archived-generator-provenance-v1/postflight-bfc5a70-r6
readonly archived_summary="${archived_root}/public/run_a/summary.json"
readonly archived_summary_sha=564ad00a7638979e7b2d7c81dba3968e4cd9a87eaa0da39fd28e070dd11d7bd9
readonly archived_verification="${archived_root}/public/run_a/verification.json"
readonly archived_verification_sha=a510cb86468d953f4cf2aa1fbebd2990363b36219b73f65b0bcc8be5e0655ab9
readonly archived_manifest="${archived_root}/SHA256SUMS"
readonly archived_manifest_sha=108b9ce8de587764759c5043b6e347f462db658abfbda4d6b2f4e83fd8aab981
readonly archived_post_receipt="${archived_post}/public/postflight_receipt.json"
readonly archived_post_receipt_sha=7ecf3708a6daf444b886eaa5867bfc8408b61964575f2d70b11a8a4677e657b6
readonly short="${public_commit:0:7}"
readonly base=/research/d7/spc/yzyang4/generator-provenance-completion-v1
readonly worktree="${base}/worktree-${short}"
readonly root="${base}/formal-${short}-r1"
readonly public="${root}/public"
readonly private="${root}/private"
readonly log="${root}/runner.log"

fail() {
  local rc="$1"
  set +e
  printf '%s\n' "${rc}" >"${root}/FAILED_RC"
  chmod 0400 "${root}/FAILED_RC" 2>/dev/null || true
  printf 'GENERATOR_PROVENANCE_COMPLETION_FORMAL=FAIL rc=%s root=%s\n' "${rc}" "${root}" >&2
  exit "${rc}"
}
trap 'fail $?' ERR

[[ "${public_commit}" =~ ^[0-9a-f]{40}$ ]]
[[ ! -e "${root}" ]]
mkdir -p "${base}" "${root}" "${public}" "${private}"
chmod 0700 "${root}" "${public}" "${private}"
: >"${log}"
chmod 0600 "${log}"
exec > >(tee -a "${log}") 2>&1

printf 'PREFLIGHT_01_OBJECTIVE=compose_exact_model_id_coverage_without_provider_inference\n'
git -C "${repo}" cat-file -e "${public_commit}^{commit}"
printf 'PREFLIGHT_02_EXACT_COMMIT=%s\n' "${public_commit}"
[[ -f "${archived_root}/COMPLETE" && ! -e "${archived_root}/FAILED_RC" ]]
[[ -f "${archived_post}/COMPLETE" ]]
[[ "$(sha256sum "${archived_summary}" | awk '{print $1}')" == "${archived_summary_sha}" ]]
[[ "$(sha256sum "${archived_verification}" | awk '{print $1}')" == "${archived_verification_sha}" ]]
[[ "$(sha256sum "${archived_manifest}" | awk '{print $1}')" == "${archived_manifest_sha}" ]]
[[ "$(sha256sum "${archived_post_receipt}" | awk '{print $1}')" == "${archived_post_receipt_sha}" ]]
printf 'PREFLIGHT_03_ARCHIVED_SOURCE=complete/postflight/hash_locked\n'
[[ -x "${python_bin}" ]]
"${python_bin}" -c 'import pytest'
command -v strace >/dev/null
command -v timeout >/dev/null
printf 'PREFLIGHT_04_RUNTIME=exp-python-with-pytest/strace/timeout\n'
printf 'PREFLIGHT_05_PROVIDER_INFERENCE_FROM_MODEL_ID_ALLOWED=false\n'
printf 'PREFLIGHT_06_VERSION_BOUNDARY_RESCUE_ALLOWED=false\n'
printf 'PREFLIGHT_07_PUBLIC_RAW_CARD_IDS_OR_ARCHIVE_VALUES_ALLOWED=false\n'
printf 'PREFLIGHT_08_PROSPECTIVE_PATHS_ALLOWED=false\n'
printf 'PREFLIGHT_09_GPU_PAID_API_MODEL_FIT_BASE_UPDATE=0/0/0/0\n'

GIT_LFS_SKIP_SMUDGE=1 git -c core.hooksPath=/dev/null -C "${repo}" worktree add --detach "${worktree}" "${public_commit}"
[[ "$(git -C "${worktree}" rev-parse HEAD)" == "${public_commit}" ]]
[[ -z "$(git -C "${worktree}" status --porcelain --untracked-files=no)" ]]
cd "${worktree}"

readonly protocol=phase1/generator_provenance_completion_protocol_v1.json
readonly protocol_sha=bbe895c5787a6a7cf583d6ff1868ee5d9c4922aa240b9a0f8146d74351fb208e
readonly composer=phase1/compose_generator_provenance_completion.py
readonly composer_sha=bb8b9228e1a434289aa980b29c24ac84d7f5136e8c55ae508bbf6114531d4f9a
readonly verifier=phase1/verify_generator_provenance_completion.py
readonly verifier_sha=e2c4d1de1c04963dc333428666901144c5fb9bff13ccf2a1e5de844f159cb63c
readonly inventory=phase1/results/release_provider_provenance_v11_20260902/inventory.json
readonly inventory_sha=88df63ed0434ba10f4eaa2c9965735c70b61a750026d290372415321834b550a
readonly inventory_verification=phase1/results/release_provider_provenance_v11_20260902/verification.json
readonly inventory_verification_sha=66459ae21415dff9a1728442334b460550604818f9b7831220d33b9f6bf62f5b
readonly focused_test=phase1/tests/test_generator_provenance_completion.py
readonly focused_test_sha=fdc85dd4ed22e54c8361606ea34e89f501ad853476118233e759063f377b9521
[[ "$(sha256sum "${protocol}" | awk '{print $1}')" == "${protocol_sha}" ]]
[[ "$(sha256sum "${composer}" | awk '{print $1}')" == "${composer_sha}" ]]
[[ "$(sha256sum "${verifier}" | awk '{print $1}')" == "${verifier_sha}" ]]
[[ "$(sha256sum "${inventory}" | awk '{print $1}')" == "${inventory_sha}" ]]
[[ "$(sha256sum "${inventory_verification}" | awk '{print $1}')" == "${inventory_verification_sha}" ]]
[[ "$(sha256sum "${focused_test}" | awk '{print $1}')" == "${focused_test_sha}" ]]
"${python_bin}" -m pytest "${focused_test}" -q | tee "${public}/focused_tests.txt"
"${python_bin}" -m pytest phase1/tests -q | tee "${public}/full_tests.txt"

readonly result_a="${public}/completion_a.json"
readonly result_b="${public}/completion_b.json"
readonly verify_a="${public}/verification_a.json"
readonly verify_b="${public}/verification_b.json"
readonly common_args=(
  --protocol "${protocol}" --protocol-sha256 "${protocol_sha}"
  --inventory "${inventory}" --inventory-sha256 "${inventory_sha}"
  --inventory-verification "${inventory_verification}" --inventory-verification-sha256 "${inventory_verification_sha}"
  --archived-summary "${archived_summary}" --archived-summary-sha256 "${archived_summary_sha}"
  --archived-verification "${archived_verification}" --archived-verification-sha256 "${archived_verification_sha}"
)

timeout 3600s strace -ff -qq -e trace=file,network -o "${private}/composer_a.strace" \
  "${python_bin}" -m phase1.compose_generator_provenance_completion "${common_args[@]}" --output "${result_a}"
timeout 3600s \
  "${python_bin}" -m phase1.compose_generator_provenance_completion "${common_args[@]}" --output "${result_b}"
cmp "${result_a}" "${result_b}"

readonly result_sha="$(sha256sum "${result_a}" | awk '{print $1}')"
timeout 3600s strace -ff -qq -e trace=file,network -o "${private}/verifier_a.strace" \
  "${python_bin}" -m phase1.verify_generator_provenance_completion "${common_args[@]}" \
    --claimed-summary "${result_a}" --claimed-summary-sha256 "${result_sha}" --output "${verify_a}"
timeout 3600s \
  "${python_bin}" -m phase1.verify_generator_provenance_completion "${common_args[@]}" \
    --claimed-summary "${result_a}" --claimed-summary-sha256 "${result_sha}" --output "${verify_b}"
cmp "${verify_a}" "${verify_b}"

prospective_hits=$(grep -hE '/prospective_decision_v1|label_vault|outcome_vault|prediction_escrow' "${private}"/*.strace* 2>/dev/null | wc -l || true)
network_hits=$(grep -hE 'socket\(|connect\(|sendto\(|recvfrom\(' "${private}"/*.strace* 2>/dev/null | wc -l || true)
credential_hits=$(grep -hEi '(^|[^A-Za-z0-9])sk-[A-Za-z0-9._-]{12,}|api[_-]?key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{12,}|authorization:[[:space:]]*bearer' "${result_a}" "${verify_a}" | wc -l || true)
absolute_path_hits=$(grep -hE '/research/|/home/|C:\\' "${result_a}" "${verify_a}" | wc -l || true)
[[ "${prospective_hits}" == 0 ]]
[[ "${network_hits}" == 0 ]]
[[ "${credential_hits}" == 0 ]]
[[ "${absolute_path_hits}" == 0 ]]

"${python_bin}" - "${result_a}" "${verify_a}" "${public_commit}" "${public}/formal_summary.json" <<'PY'
import hashlib, json, pathlib, sys
result_path, verify_path, commit, output_path = map(pathlib.Path, sys.argv[1:])
result = json.loads(result_path.read_text())
verification = json.loads(verify_path.read_text())
assert result["status"] == "COMPLETE_CONFIGURED_MODEL_ID_PROVIDER_PARTIAL_NOT_RELEASE_CLEARED"
assert verification["status"] == "PASS_EXACT_RECONSTRUCTION"
coverage = result["coverage"]
assert coverage["configured_model_id_rows"] == result["release"]["rows"]
assert coverage["provider_family_rows"] + coverage["provider_family_unresolved_rows"] == result["release"]["rows"]
assert result["interpretation_boundary"]["provider_family_coverage_changed"] is False
payload = {
    "protocol": "decision-corpus-generator-provenance-completion-formal-summary-v1",
    "status": "PASS_MODEL_ID_COMPLETE_PROVIDER_PARTIAL_NOT_RELEASE_CLEARED",
    "source_commit": str(commit),
    "completion_summary_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
    "verification_sha256": hashlib.sha256(verify_path.read_bytes()).hexdigest(),
    "release_rows": result["release"]["rows"],
    "coverage": coverage,
    "archived_recovery": result["archived_recovery"],
    "provider_or_contract_entity_inferred": False,
    "release_clearance": False,
    "prospective_paths_opened": False,
    "network_calls": 0,
    "credential_hits_public": 0,
    "gpu_paid_api_model_fit_base_update": "0/0/0/0",
}
output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

find "${public}" -type f -exec chmod 0400 {} +
find "${private}" -type f -exec chmod 0400 {} +
chmod 0500 "${public}" "${private}"
printf '%s\n' 'GENERATOR_PROVENANCE_COMPLETION_FORMAL_PASS' >"${root}/COMPLETE"
chmod 0400 "${root}/COMPLETE" "${log}"
chmod 0500 "${root}"
printf 'GENERATOR_PROVENANCE_COMPLETION_FORMAL=PASS root=%s\n' "${root}"
