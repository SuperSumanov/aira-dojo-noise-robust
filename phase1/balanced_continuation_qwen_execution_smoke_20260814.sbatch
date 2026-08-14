#!/usr/bin/env bash
#SBATCH --job-name=e1q_exec_smoke
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=00:20:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38

set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
umask 077

: "${QES_SOURCE_ROOT:?}"
: "${QES_SOURCE_COMMIT:?}"
: "${QES_RUN_ROOT:?}"
: "${SLURM_ARRAY_TASK_ID:?}"

index="${SLURM_ARRAY_TASK_ID}"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
source_run=/research/d7/spc/yzyang4/balanced-e1-real-e59a759d-a1
probe_root=/research/d7/spc/yzyang4/balanced-e1-operator-probe-1fc6031-a1
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
hf_cache=/research/d7/spc/yzyang4/scratch/hf_cache
output_root="${QES_RUN_ROOT}/outputs"
workspace_root="${QES_RUN_ROOT}/workspaces"
nvfix="${QES_RUN_ROOT}/nvfix/${index}"
log_root="${QES_RUN_ROOT}/logs"
rc_root="${QES_RUN_ROOT}/job_rc"
source_nvvm=/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4

for required in "$python_bin" "$source_run" "$probe_root" "$container" "$hf_cache" "$output_root" "$workspace_root" "$log_root" "$rc_root"; do
  if [[ ! -e "$required" ]]; then
    printf 'QES_REQUIRED_PATH_MISSING=%s\n' "$required" >&2
    exit 3
  fi
done
if [[ ! -f "$source_nvvm" || -e "$nvfix" || -L "$nvfix" ]]; then
  printf 'QES_NVVM_PATH_INVALID index=%s\n' "$index" >&2
  exit 4
fi
mkdir "$nvfix"
cp "$source_nvvm" "$nvfix/libnvidia-nvvm.so.4"
chmod 0555 "$nvfix"
chmod 0444 "$nvfix/libnvidia-nvvm.so.4"

cd "$QES_SOURCE_ROOT"
test "$(git rev-parse HEAD)" = "$QES_SOURCE_COMMIT"
test -z "$(git status --porcelain)"

stdout="${log_root}/producer_${index}.stdout"
stderr="${log_root}/producer_${index}.stderr"
set +e
"$python_bin" -m phase1.balanced_continuation_qwen_execution_smoke --source-root "$QES_SOURCE_ROOT" --source-commit "$QES_SOURCE_COMMIT" --source-run-root "$source_run" --probe-root "$probe_root" --container "$container" --hf-cache "$hf_cache" --nvfix-dir "$nvfix" --output-root "$output_root" --workspace-root "$workspace_root" --index "$index" >"$stdout" 2>"$stderr"
producer_rc=$?
set -e

safety_rc=-1
if [[ "$producer_rc" = 0 ]]; then
  filename_hits="$(find "${output_root}/index_${index}" -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
  content_hits="$(grep -RIlE --binary-files=without-match 'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' "${output_root}/index_${index}" | wc -l || true)"
  if [[ "$filename_hits" = 0 && "$content_hits" = 0 ]]; then
    safety_rc=0
  else
    safety_rc=7
  fi
fi

tmp="${rc_root}/.${index}.json.tmp-${SLURM_JOB_ID}"
printf '{"index":%s,"slurm_job_id":"%s","producer_rc":%s,"safety_rc":%s}\n' "$index" "$SLURM_JOB_ID" "$producer_rc" "$safety_rc" >"$tmp"
mv "$tmp" "${rc_root}/${index}.json"
printf 'QES_JOB_DONE index=%s producer_rc=%s safety_rc=%s\n' "$index" "$producer_rc" "$safety_rc"
if [[ "$producer_rc" != 0 ]]; then
  exit "$producer_rc"
fi
exit "$safety_rc"
