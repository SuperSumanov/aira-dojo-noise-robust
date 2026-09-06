#!/usr/bin/env bash
# Same pivot shape, isolated FA2 dependency repair, no effect-data access.
#SBATCH --job-name=critic_pivot_fa2
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=0
#SBATCH --gres=gpu:pro6000:2
#SBATCH --nodelist=projgpu39
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=00:26:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
: "${SLURM_JOB_ID:?}"
: "${ZERO3_CONTROL_ROOT:?}"
: "${ZERO3_CODE_COMMIT:?}"
: "${ZERO3_GPU_APPROVAL_RECEIPT_SHA:?}"
readonly runtime=/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5
readonly overlay=/research/d7/spc/yzyang4/flash-attn-build-20260907-r4/overlay
readonly run_root=/research/d7/spc/yzyang4/critic-pivot-shape/job-$SLURM_JOB_ID
test "$(readlink -m "$run_root")" = "$run_root"
test ! -e "$run_root"
mkdir -m 0700 "$run_root"
exec > "$run_root/worker.log" 2>&1
telemetry_pid=
finish() {
    result=$?
    if [[ -n "$telemetry_pid" ]]; then kill "$telemetry_pid" 2>/dev/null || true; wait "$telemetry_pid" 2>/dev/null || true; fi
    printf '%s\n' "$result" > "$run_root/exit_status.txt"
    exit "$result"
}
trap finish EXIT
test "$(git -C "$ZERO3_CONTROL_ROOT" rev-parse HEAD)" = "$ZERO3_CODE_COMMIT"
test -z "$(git -C "$ZERO3_CONTROL_ROOT" status --porcelain --untracked-files=all)"
export PATH="$runtime/bin:/usr/local/cuda-12.8/bin:/usr/local/bin:/usr/bin:/bin"
export VIRTUAL_ENV="$runtime" PYTHONPATH="$overlay:$ZERO3_CONTROL_ROOT" CUDA_HOME=/usr/local/cuda-12.8
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MAX_JOBS=2
export PYTHONHASHSEED=6 CUBLAS_WORKSPACE_CONFIG=:4096:8 NCCL_DEBUG=INFO
export NCCL_IB_DISABLE=1 NCCL_NET=Socket PYTHONFAULTHANDLER=1
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
scratch=$(mktemp -d /tmp/critic-pivot-fa2-$SLURM_JOB_ID-XXXXXX)
mkdir "$scratch/triton" "$scratch/extensions"
export TRITON_CACHE_DIR="$scratch/triton" TORCH_EXTENSIONS_DIR="$scratch/extensions"
export G0_VENV="$runtime" G0_BUDGET_REVISION=20260905-r5 G0_RUN_ROOT="$run_root"
"$runtime/bin/python" -B -m phase1.check_g0_r5_build_tools
"$runtime/bin/python" -B -c 'from phase1.pivot_checkpoint_space import probe; import sys; probe(sys.argv[1])' "$run_root"
timeout --kill-after=20s 120s "$runtime/bin/python" -B -m phase1.scripts.prepare_pivot_fa2_shape_20260907 kernel --commit "$ZERO3_CODE_COMMIT"
# Recheck the remaining wall clock AFTER dependency math; no shortened driver.
"$runtime/bin/python" -B -m phase1.scripts.prepare_pivot_fa2_shape_20260907 allocated --commit "$ZERO3_CODE_COMMIT"
(
    while true; do
        date -u +%Y-%m-%dT%H:%M:%SZ
        nvidia-smi -i "$CUDA_VISIBLE_DEVICES" --query-gpu=index,name,uuid,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
        sleep 10
    done
) > "$run_root/telemetry.txt" 2>&1 &
telemetry_pid=$!
/usr/bin/time -v -o "$run_root/resource_usage.txt" \
  /usr/bin/strace -f -qq -e trace=%file -o "$run_root/file_trace.log" \
  timeout --kill-after=60s 1200s "$runtime/bin/python" -B -m phase1.scripts.validate_pivot_zero3_shape_20260906 \
  --output "$run_root/trajectories" > "$run_root/driver.log" 2>&1
test -f "$run_root/trajectories/summary.json"
printf 'PIVOT_FA2_SHAPE_DRIVER_COMPLETE_PENDING_INDEPENDENT_ACCEPTANCE\n'
