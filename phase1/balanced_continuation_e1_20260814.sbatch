#!/usr/bin/env bash
#SBATCH --job-name=balanced_e1
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=00:40:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38

set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u

credential_env=/research/d7/spc/yzyang4/aira-dojo/.env
if [[ ! -f "$credential_env" || -L "$credential_env" || "$(stat -c %a "$credential_env")" != 600 ]]; then
  printf 'E1_JOB_CREDENTIAL_FILE_UNSAFE\n' >&2
  exit 3
fi
set -a
source "$credential_env"
set +a

: "${E1_RUN_ROOT:?}"
: "${E1_SOURCE_ROOT:?}"
: "${E1_DATA_GATE_ROOT:?}"
: "${SLURM_ARRAY_TASK_ID:?}"

index="${SLURM_ARRAY_TASK_ID}"
python_bin=/research/d7/spc/yzyang4/venvs/exp/bin/python
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
hf_cache=/research/d7/spc/yzyang4/scratch/hf_cache
prep="${E1_RUN_ROOT}/preparation"
assignment="${prep}/assignment"
real_contract="${prep}/real_contract.json"
code_vault="${E1_DATA_GATE_ROOT}/e1_inputs/code_vault.jsonl"
split_root="${E1_DATA_GATE_ROOT}/e1_split"
worker_root="${E1_RUN_ROOT}/worker_outputs"
workspace_root="${E1_RUN_ROOT}/workspaces"
sealed_root="${E1_RUN_ROOT}/sealed"
receipt_root="${E1_RUN_ROOT}/worker_receipts"
job_log_root="${E1_RUN_ROOT}/job_logs"
rc_root="${E1_RUN_ROOT}/job_rc"
nvfix="${E1_RUN_ROOT}/nvfix"

for required in \
  "$python_bin" "$container" "$hf_cache" "$assignment" "$real_contract" \
  "$code_vault" "$split_root" "$worker_root" "$workspace_root" "$sealed_root" \
  "$receipt_root" "$job_log_root" "$rc_root" "$nvfix"; do
  if [[ ! -e "$required" ]]; then
    printf 'E1_JOB_REQUIRED_PATH_MISSING=%s\n' "$required" >&2
    exit 3
  fi
done
if [[ -z "${PRIMARY_KEY_DEEPSEEK_V4_FLASH:-}" && -z "${PRIMARY_KEY:-}" ]]; then
  printf 'E1_JOB_OPERATOR_CREDENTIAL_UNAVAILABLE\n' >&2
  exit 5
fi
cd "$E1_SOURCE_ROOT"
expected_commit="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["source_commit"])' "$real_contract")"
test "$(git rev-parse HEAD)" = "$expected_commit"
test -z "$(git status --porcelain)"

worker_stdout="${job_log_root}/worker_${index}.stdout"
worker_stderr="${job_log_root}/worker_${index}.stderr"
verifier_stdout="${job_log_root}/verifier_${index}.stdout"
verifier_stderr="${job_log_root}/verifier_${index}.stderr"
receipt="${receipt_root}/$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["rollout_id"])' "${assignment}/assignment_manifest.jsonl" "$index").verify.json"

printf 'E1_JOB_START utc=%s host=%s slurm_job=%s index=%s commit=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)" "$SLURM_JOB_ID" "$index" "$expected_commit"
set +e
"$python_bin" -m phase1.balanced_continuation_real_worker \
  --assignment-result "$assignment" \
  --code-vault "$code_vault" \
  --real-contract "$real_contract" \
  --split-root "$split_root" \
  --index "$index" \
  --output-root "$worker_root" \
  --workspace-root "$workspace_root" \
  --sealed-root "$sealed_root" \
  --container "$container" \
  --hf-cache "$hf_cache" \
  --nvfix-dir "$nvfix" \
  >"$worker_stdout" 2>"$worker_stderr"
worker_rc=$?
set -e
verifier_rc=-1
safety_rc=-1
if [[ "$worker_rc" = 0 ]]; then
  rollout_id="$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["rollout_id"])' "${assignment}/assignment_manifest.jsonl" "$index")"
  set +e
  "$python_bin" -m phase1.verify_balanced_continuation_real_worker \
    --artifact "${worker_root}/${rollout_id}" \
    --assignment-result "$assignment" \
    --code-vault "$code_vault" \
    --real-contract "$real_contract" \
    --split-root "$split_root" \
    --workspace-root "$workspace_root" \
    --sealed-root "$sealed_root" \
    --container "$container" \
    --hf-cache "$hf_cache" \
    --nvfix-dir "$nvfix" \
    --source-root "$E1_SOURCE_ROOT" \
    --index "$index" \
    --receipt "$receipt" \
    >"$verifier_stdout" 2>"$verifier_stderr"
  verifier_rc=$?
  set -e
  if [[ "$verifier_rc" = 0 ]]; then
    filename_hits="$(find "${worker_root}/${rollout_id}" "$receipt" "${sealed_root}/${rollout_id}" \
      -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
    content_hits="$(grep -RIlE --binary-files=without-match \
      'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
      "${worker_root}/${rollout_id}" "$receipt" "${sealed_root}/${rollout_id}" | wc -l || true)"
    if [[ "$filename_hits" = 0 && "$content_hits" = 0 ]]; then
      safety_rc=0
    else
      printf 'E1_JOB_SECRET_SCAN_FAILED filename=%s content=%s\n' "$filename_hits" "$content_hits" >&2
      safety_rc=7
    fi
  fi
fi

rc_tmp="${rc_root}/.${index}.json.tmp-${SLURM_JOB_ID}"
printf '{"index":%s,"slurm_job_id":"%s","worker_rc":%s,"verifier_rc":%s,"safety_rc":%s}\n' \
  "$index" "$SLURM_JOB_ID" "$worker_rc" "$verifier_rc" "$safety_rc" >"$rc_tmp"
mv "$rc_tmp" "${rc_root}/${index}.json"
printf 'E1_JOB_DONE utc=%s index=%s worker_rc=%s verifier_rc=%s safety_rc=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$index" "$worker_rc" "$verifier_rc" "$safety_rc"
if [[ "$worker_rc" != 0 ]]; then
  exit "$worker_rc"
fi
if [[ "$verifier_rc" != 0 ]]; then
  exit "$verifier_rc"
fi
exit "$safety_rc"
