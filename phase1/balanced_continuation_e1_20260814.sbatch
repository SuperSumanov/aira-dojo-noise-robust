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
nvfix_parent="${E1_RUN_ROOT}/nvfix"
nvfix="${nvfix_parent}/${index}"
capability_parent="${E1_RUN_ROOT}/capability"
capability="${capability_parent}/${index}"
source_nvvm=/usr/lib/x86_64-linux-gnu/libnvidia-nvvm.so.4

for required in \
  "$python_bin" "$container" "$hf_cache" "$assignment" "$real_contract" \
  "$code_vault" "$split_root" "$worker_root" "$workspace_root" "$sealed_root" \
  "$receipt_root" "$job_log_root" "$rc_root" "$nvfix_parent" "$capability_parent"; do
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
capability_stdout="${job_log_root}/capability_${index}.stdout"
capability_stderr="${job_log_root}/capability_${index}.stderr"
receipt="${receipt_root}/$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["rollout_id"])' "${assignment}/assignment_manifest.jsonl" "$index").verify.json"
task="$($python_bin -c 'import json,sys;print(json.loads(open(sys.argv[1]).read().splitlines()[int(sys.argv[2])])["task"])' "${assignment}/assignment_manifest.jsonl" "$index")"
public_task="${E1_DATA_GATE_ROOT}/e1_split/public/${task}"

printf 'E1_JOB_START utc=%s host=%s slurm_job=%s index=%s commit=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)" "$SLURM_JOB_ID" "$index" "$expected_commit"
capability_rc=-1
worker_rc=-1
verifier_rc=-1
safety_rc=-1

set +e
if [[ -e "$nvfix" || -L "$nvfix" || -e "$capability" || -L "$capability" ]]; then
  printf 'E1_JOB_CAPABILITY_ROOT_ALREADY_EXISTS\n' >"$capability_stderr"
  capability_rc=6
elif [[ ! -f "$source_nvvm" || ! -f /etc/OpenCL/vendors/nvidia.icd \
  || ! -d "$public_task" || -L "$public_task" ]]; then
  printf 'E1_JOB_NODE_NVIDIA_CAPABILITY_FILE_MISSING\n' >"$capability_stderr"
  capability_rc=7
else
  mkdir "$nvfix" "$capability"
  cp "$source_nvvm" "$nvfix/libnvidia-nvvm.so.4"
  cp "$E1_SOURCE_ROOT/phase1/balanced_continuation_capability_probe.py" \
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
    python solution.py \
    >"$capability_stdout" 2>"$capability_stderr"
  capability_rc=$?
  if [[ "$capability_rc" = 0 ]]; then
    "$python_bin" - "$capability_stdout" "$nvfix/libnvidia-nvvm.so.4" \
      "$capability/receipt.json" "$index" "$task" <<'PY'
import hashlib, json, pathlib, sys
stdout = pathlib.Path(sys.argv[1])
library = pathlib.Path(sys.argv[2])
receipt = pathlib.Path(sys.argv[3])
index = int(sys.argv[4])
task = sys.argv[5]
raw_stdout = stdout.read_bytes()
lines = raw_stdout.splitlines()
if len(lines) != 1:
    raise SystemExit("capability probe stdout is not exactly one JSON line")
value = json.loads(lines[0])
required = {
    "status", "public_train_readable", "public_header_columns",
    "public_mount_write_blocked", "external_network_blocked",
    "provider_environment_variables_visible", "host_research_filesystem_visible",
    "required_package_versions",
}
if set(value) != required:
    raise SystemExit("capability probe schema differs")
if (
    value["status"] != "E1_CONTAINER_CAPABILITY_PASS"
    or value["public_train_readable"] is not True
    or not isinstance(value["public_header_columns"], int)
    or value["public_header_columns"] <= 1
    or value["public_mount_write_blocked"] is not True
    or value["external_network_blocked"] is not True
    or value["provider_environment_variables_visible"] != 0
    or value["host_research_filesystem_visible"] is not False
    or set(value["required_package_versions"])
    != {"numpy", "pandas", "sklearn", "lightgbm", "catboost"}
):
    raise SystemExit("capability probe claims differ")
raw_library = library.read_bytes()
record = {
    "status": "VERIFIED_E1_NODE_LOCAL_CAPABILITY",
    "index": index,
    "task": task,
    "probe": value,
    "probe_stdout_sha256": hashlib.sha256(raw_stdout).hexdigest(),
    "node_nvvm_sha256": hashlib.sha256(raw_library).hexdigest(),
}
receipt.write_text(
    json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
PY
    capability_rc=$?
  fi
fi
set -e

if [[ "$capability_rc" = 0 ]]; then
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
fi
if [[ "$capability_rc" = 0 && "$worker_rc" = 0 ]]; then
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
      "$capability" "$capability_stdout" "$capability_stderr" \
      -type f -printf '%f\n' | grep -icE 'env|key|token|secret' || true)"
    content_hits="$(grep -RIlE --binary-files=without-match \
      'sk-[A-Za-z0-9._-]{20,}|hf_[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[[:space:]]+[A-Za-z0-9._-]{24,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----' \
      "${worker_root}/${rollout_id}" "$receipt" "${sealed_root}/${rollout_id}" \
      "$capability" "$capability_stdout" "$capability_stderr" | wc -l || true)"
    if [[ "$filename_hits" = 0 && "$content_hits" = 0 ]]; then
      safety_rc=0
    else
      printf 'E1_JOB_SECRET_SCAN_FAILED filename=%s content=%s\n' "$filename_hits" "$content_hits" >&2
      safety_rc=7
    fi
  fi
fi

rc_tmp="${rc_root}/.${index}.json.tmp-${SLURM_JOB_ID}"
printf '{"index":%s,"slurm_job_id":"%s","capability_rc":%s,"worker_rc":%s,"verifier_rc":%s,"safety_rc":%s}\n' \
  "$index" "$SLURM_JOB_ID" "$capability_rc" "$worker_rc" "$verifier_rc" "$safety_rc" >"$rc_tmp"
mv "$rc_tmp" "${rc_root}/${index}.json"
printf 'E1_JOB_DONE utc=%s index=%s capability_rc=%s worker_rc=%s verifier_rc=%s safety_rc=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$index" "$capability_rc" "$worker_rc" "$verifier_rc" "$safety_rc"
if [[ "$capability_rc" != 0 ]]; then
  exit "$capability_rc"
fi
if [[ "$worker_rc" != 0 ]]; then
  exit "$worker_rc"
fi
if [[ "$verifier_rc" != 0 ]]; then
  exit "$verifier_rc"
fi
exit "$safety_rc"
