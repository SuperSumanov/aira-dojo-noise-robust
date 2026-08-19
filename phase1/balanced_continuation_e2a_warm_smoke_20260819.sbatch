#!/usr/bin/env bash
#SBATCH --job-name=e2a_warm_smoke
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=00:35:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38

set -eo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
if [[ -f "${HOME}/env_setup.sh" ]]; then
  source "${HOME}/env_setup.sh"
fi
set -u
umask 077

: "${E2S_RUN_ROOT:?}"
: "${E2S_SOURCE_ROOT:?}"
: "${E2S_DATA_GATE_ROOT:?}"
: "${E2S_PREPARATION:?}"
: "${SLURM_ARRAY_TASK_ID:?}"

slot="${SLURM_ARRAY_TASK_ID}"
python_bin=/research/d7/spc/yzyang4/venvs/aira/bin/python
container=/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif
hf_cache="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["hf_cache_path"])' "$E2S_PREPARATION/real_contract.json")"
source_nvvm=/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4
nvfix="${E2S_RUN_ROOT}/nvfix/${slot}"
capability="${E2S_RUN_ROOT}/capability/${slot}"
output_root="${E2S_RUN_ROOT}/outputs"
workspace_root="${E2S_RUN_ROOT}/workspaces"
receipt_root="${E2S_RUN_ROOT}/receipts"
log_root="${E2S_RUN_ROOT}/logs"
rc_root="${E2S_RUN_ROOT}/job_rc"

for required in \
  "$python_bin" "$container" "$hf_cache" "$E2S_SOURCE_ROOT" \
  "$E2S_DATA_GATE_ROOT" "$E2S_PREPARATION" "$output_root" "$workspace_root" \
  "$receipt_root" "$log_root" "$rc_root" "${E2S_RUN_ROOT}/nvfix" \
  "${E2S_RUN_ROOT}/capability"; do
  if [[ ! -e "$required" ]]; then
    printf 'E2S_REQUIRED_PATH_MISSING=%s\n' "$required" >&2
    exit 3
  fi
done
cd "$E2S_SOURCE_ROOT"
expected_commit="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["source_commit"])' "$E2S_PREPARATION/real_contract.json")"
test "$(git -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false rev-parse HEAD)" = "$expected_commit"
test -z "$(git -c filter.lfs.smudge= -c filter.lfs.process= \
  -c filter.lfs.required=false status --porcelain)"
assignment_index="$($python_bin -c 'import json,sys;print(json.load(open(sys.argv[1]))["warm_smoke_assignment_indices"][int(sys.argv[2])])' "$E2S_PREPARATION/run_plan.json" "$slot")"
task="$($python_bin -c 'import json,sys;rows=open(sys.argv[1]).read().splitlines();print(json.loads(rows[int(sys.argv[2])])["task"])' "$E2S_PREPARATION/assignment/assignment_manifest.jsonl" "$assignment_index")"
public_task="${E2S_DATA_GATE_ROOT}/e2a_split/public/${task}"

capability_rc=-1
producer_rc=-1
verifier_rc=-1
safety_rc=-1
capability_stdout="${log_root}/capability_${slot}.stdout"
capability_stderr="${log_root}/capability_${slot}.stderr"
producer_stdout="${log_root}/producer_${slot}.stdout"
producer_stderr="${log_root}/producer_${slot}.stderr"
verifier_stdout="${log_root}/verifier_${slot}.stdout"
verifier_stderr="${log_root}/verifier_${slot}.stderr"

set +e
if [[ -e "$nvfix" || -L "$nvfix" || -e "$capability" || -L "$capability" ]]; then
  printf 'E2S_CAPABILITY_ROOT_EXISTS\n' >"$capability_stderr"
  capability_rc=6
elif [[ ! -f "$source_nvvm" || ! -f /etc/OpenCL/vendors/nvidia.icd \
  || ! -d "$public_task" || -L "$public_task" ]]; then
  printf 'E2S_CAPABILITY_INPUT_MISSING\n' >"$capability_stderr"
  capability_rc=7
else
  mkdir "$nvfix" "$capability"
  cp "$source_nvvm" "$nvfix/libnvidia-nvvm.so.4"
  cp "$E2S_SOURCE_ROOT/phase1/balanced_continuation_capability_probe.py" \
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
  "$python_bin" -m phase1.balanced_continuation_e2a_warm_smoke \
    --source-root "$E2S_SOURCE_ROOT" \
    --preparation "$E2S_PREPARATION" \
    --data-gate "$E2S_DATA_GATE_ROOT" \
    --container "$container" \
    --hf-cache "$hf_cache" \
    --nvfix-dir "$nvfix" \
    --output-root "$output_root" \
    --workspace-root "$workspace_root" \
    --slot "$slot" >"$producer_stdout" 2>"$producer_stderr"
  producer_rc=$?
  set -e
fi

if [[ "$capability_rc" = 0 && "$producer_rc" = 0 ]]; then
  set +e
  "$python_bin" -m phase1.verify_balanced_continuation_e2a_warm_smoke \
    --source-root "$E2S_SOURCE_ROOT" \
    --preparation "$E2S_PREPARATION" \
    --data-gate "$E2S_DATA_GATE_ROOT" \
    --container "$container" \
    --hf-cache "$hf_cache" \
    --nvfix-dir "$nvfix" \
    --output-root "$output_root" \
    --workspace-root "$workspace_root" \
    --slot "$slot" \
    --receipt "$receipt_root/${slot}.verify.json" \
    >"$verifier_stdout" 2>"$verifier_stderr"
  verifier_rc=$?
  set -e
fi

if [[ "$capability_rc" = 0 && "$producer_rc" = 0 && "$verifier_rc" = 0 ]]; then
  filename_hits="$(find "$output_root/slot_${slot}" "$receipt_root/${slot}.verify.json" \
    "$capability" "$capability_stdout" "$capability_stderr" \
    -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
  content_hits="$(grep -RIlE --binary-files=without-match \
    'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
    "$output_root/slot_${slot}" "$receipt_root/${slot}.verify.json" \
    "$capability" "$capability_stdout" "$capability_stderr" | wc -l || true)"
  if [[ "$filename_hits" = 0 && "$content_hits" = 0 ]]; then
    safety_rc=0
  else
    safety_rc=7
  fi
fi

rc_tmp="${rc_root}/.${slot}.json.tmp-${SLURM_JOB_ID}"
printf '{"slot":%s,"assignment_index":%s,"task":"%s","slurm_job_id":"%s","capability_rc":%s,"producer_rc":%s,"verifier_rc":%s,"safety_rc":%s}\n' \
  "$slot" "$assignment_index" "$task" "$SLURM_JOB_ID" "$capability_rc" \
  "$producer_rc" "$verifier_rc" "$safety_rc" >"$rc_tmp"
mv "$rc_tmp" "$rc_root/${slot}.json"
printf 'E2A_WARM_JOB_DONE slot=%s task=%s capability_rc=%s producer_rc=%s verifier_rc=%s safety_rc=%s\n' \
  "$slot" "$task" "$capability_rc" "$producer_rc" "$verifier_rc" "$safety_rc"
if [[ "$capability_rc" != 0 ]]; then exit "$capability_rc"; fi
if [[ "$producer_rc" != 0 ]]; then exit "$producer_rc"; fi
if [[ "$verifier_rc" != 0 ]]; then exit "$verifier_rc"; fi
exit "$safety_rc"
