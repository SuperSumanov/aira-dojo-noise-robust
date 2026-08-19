#!/usr/bin/env bash
#SBATCH --job-name=balanced_e2a
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=01:15:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38

set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then source "${HOME}/env_setup.sh"; fi
set -u
umask 077

credential_env=/research/d7/spc/yzyang4/aira-dojo/.env
if [[ ! -f "$credential_env" || -L "$credential_env" \
  || "$(stat -c %a "$credential_env")" != 600 ]]; then
  echo "E2A_CREDENTIAL_FILE_UNSAFE" >&2
  exit 3
fi
set -a
source "$credential_env"
set +a
if [[ -z "${PRIMARY_KEY_QWEN3_CODER_FLASH:-}" ]]; then
  echo "E2A_QWEN_CREDENTIAL_UNAVAILABLE" >&2
  exit 5
fi

: "${E2A_RUN_ROOT:?}"
: "${E2A_SOURCE_ROOT:?}"
: "${E2A_DATA_GATE_ROOT:?}"
: "${SLURM_ARRAY_TASK_ID:?}"
index="${SLURM_ARRAY_TASK_ID}"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
hf_cache=/research/d7/spc/yzyang4/scratch/hf_cache
source_nvvm=/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4
prep="${E2A_RUN_ROOT}/preparation"
assignment="${prep}/assignment"
real_contract="${prep}/real_contract.json"
code_vault="${E2A_DATA_GATE_ROOT}/e2a_inputs/code_vault.jsonl"
split_root="${E2A_DATA_GATE_ROOT}/e2a_split"
worker_root="${E2A_RUN_ROOT}/worker_outputs"
workspace_root="${E2A_RUN_ROOT}/workspaces"
sealed_root="${E2A_RUN_ROOT}/sealed"
receipt_root="${E2A_RUN_ROOT}/worker_receipts"
job_log_root="${E2A_RUN_ROOT}/job_logs"
rc_root="${E2A_RUN_ROOT}/job_rc"
nvfix="${E2A_RUN_ROOT}/nvfix/${index}"
capability="${E2A_RUN_ROOT}/capability/${index}"

for required in \
  "$python_bin" "$container" "$hf_cache" "$assignment" "$real_contract" \
  "$code_vault" "$split_root" "$worker_root" "$workspace_root" "$sealed_root" \
  "$receipt_root" "$job_log_root" "$rc_root" "${E2A_RUN_ROOT}/nvfix" \
  "${E2A_RUN_ROOT}/capability"; do
  if [[ ! -e "$required" ]]; then
    printf 'E2A_REQUIRED_PATH_MISSING=%s\n' "$required" >&2
    exit 3
  fi
done
cd "$E2A_SOURCE_ROOT"
expected_commit="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["source_commit"])' "$real_contract")"
test "$(git -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false rev-parse HEAD)" = "$expected_commit"
test -z "$(git -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false status --porcelain)"
expected_python_path="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["worker_python_path"])' "$prep/run_plan.json")"
expected_python_sha="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["worker_python_sha256"])' "$prep/run_plan.json")"
test "$python_bin" = "$expected_python_path"
test "$(sha256sum "$python_bin" | cut -d' ' -f1)" = "$expected_python_sha"
rollout_id="$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["rollout_id"])' "$assignment/assignment_manifest.jsonl" "$index")"
task="$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["task"])' "$assignment/assignment_manifest.jsonl" "$index")"
public_task="${split_root}/public/${task}"
receipt="${receipt_root}/${rollout_id}.verify.json"

capability_rc=-1
worker_rc=-1
verifier_rc=-1
safety_rc=-1
capability_stdout="${job_log_root}/capability_${index}.stdout"
capability_stderr="${job_log_root}/capability_${index}.stderr"
worker_stdout="${job_log_root}/worker_${index}.stdout"
worker_stderr="${job_log_root}/worker_${index}.stderr"
verifier_stdout="${job_log_root}/verifier_${index}.stdout"
verifier_stderr="${job_log_root}/verifier_${index}.stderr"

set +e
if [[ -e "$nvfix" || -L "$nvfix" || -e "$capability" || -L "$capability" ]]; then
  echo "E2A_CAPABILITY_ROOT_EXISTS" >"$capability_stderr"
  capability_rc=6
elif [[ ! -f "$source_nvvm" || ! -f /etc/OpenCL/vendors/nvidia.icd \
  || ! -d "$public_task" || -L "$public_task" ]]; then
  echo "E2A_CAPABILITY_INPUT_MISSING" >"$capability_stderr"
  capability_rc=7
else
  mkdir "$nvfix" "$capability"
  cp "$source_nvvm" "$nvfix/libnvidia-nvvm.so.4"
  cp "$E2A_SOURCE_ROOT/phase1/balanced_continuation_capability_probe.py" \
    "$capability/solution.py"
  chmod 0555 "$nvfix"
  chmod 0444 "$nvfix/libnvidia-nvvm.so.4"
  cap_binds="$capability:/workspace,$public_task:/workspace/data:ro,$hf_cache:/hf:ro"
  env -i PATH="$PATH" HOME=/tmp USER="$(id -un)" \
    singularity exec --containall --cleanenv --net --network none \
    --no-home --no-mount bind-paths --no-eval --nv --pwd /workspace \
    --bind "$cap_binds" \
    --bind /etc/OpenCL/vendors/nvidia.icd:/etc/OpenCL/vendors/nvidia.icd \
    --bind "$nvfix:/mnt:ro" \
    "$container" env PYTHONUNBUFFERED=1 HOME=/tmp HF_HOME=/hf HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 LD_LIBRARY_PATH=/mnt:/.singularity.d/libs \
    python solution.py >"$capability_stdout" 2>"$capability_stderr"
  capability_rc=$?
fi
set -e

if [[ "$capability_rc" = 0 ]]; then
  set +e
  "$python_bin" -m phase1.balanced_continuation_real_worker \
    --assignment-result "$assignment" --code-vault "$code_vault" \
    --real-contract "$real_contract" --split-root "$split_root" --index "$index" \
    --output-root "$worker_root" --workspace-root "$workspace_root" \
    --sealed-root "$sealed_root" --container "$container" --hf-cache "$hf_cache" \
    --nvfix-dir "$nvfix" >"$worker_stdout" 2>"$worker_stderr"
  worker_rc=$?
  set -e
fi
if [[ "$capability_rc" = 0 && "$worker_rc" = 0 ]]; then
  set +e
  "$python_bin" -m phase1.verify_balanced_continuation_real_worker \
    --artifact "$worker_root/$rollout_id" --assignment-result "$assignment" \
    --code-vault "$code_vault" --real-contract "$real_contract" \
    --split-root "$split_root" --workspace-root "$workspace_root" \
    --sealed-root "$sealed_root" --container "$container" --hf-cache "$hf_cache" \
    --nvfix-dir "$nvfix" --source-root "$E2A_SOURCE_ROOT" --index "$index" \
    --receipt "$receipt" >"$verifier_stdout" 2>"$verifier_stderr"
  verifier_rc=$?
  set -e
fi
if [[ "$capability_rc" = 0 && "$worker_rc" = 0 && "$verifier_rc" = 0 ]]; then
  filename_hits="$(find "$worker_root/$rollout_id" "$receipt" "$sealed_root/$rollout_id" \
    "$capability" "$capability_stdout" "$capability_stderr" \
    -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
  content_hits="$(grep -RIlE --binary-files=without-match \
    'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
    "$worker_root/$rollout_id" "$receipt" "$sealed_root/$rollout_id" \
    "$capability" "$capability_stdout" "$capability_stderr" | wc -l || true)"
  if [[ "$filename_hits" = 0 && "$content_hits" = 0 ]]; then safety_rc=0; else safety_rc=7; fi
fi
rc_tmp="${rc_root}/.${index}.json.tmp-${SLURM_JOB_ID}"
printf '{"index":%s,"rollout_id":"%s","task":"%s","slurm_job_id":"%s","capability_rc":%s,"worker_rc":%s,"verifier_rc":%s,"safety_rc":%s}\n' \
  "$index" "$rollout_id" "$task" "$SLURM_JOB_ID" "$capability_rc" "$worker_rc" \
  "$verifier_rc" "$safety_rc" >"$rc_tmp"
mv "$rc_tmp" "$rc_root/${index}.json"
printf 'E2A_JOB_DONE index=%s task=%s capability_rc=%s worker_rc=%s verifier_rc=%s safety_rc=%s\n' \
  "$index" "$task" "$capability_rc" "$worker_rc" "$verifier_rc" "$safety_rc"
if [[ "$capability_rc" != 0 ]]; then exit "$capability_rc"; fi
if [[ "$worker_rc" != 0 ]]; then exit "$worker_rc"; fi
if [[ "$verifier_rc" != 0 ]]; then exit "$verifier_rc"; fi
exit "$safety_rc"
