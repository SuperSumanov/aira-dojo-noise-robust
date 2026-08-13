#!/usr/bin/env bash
#SBATCH --job-name=frozen05_full
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=04:00:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --array=0-3%4
#SBATCH --output=/research/d7/spc/yzyang4/logs/frozen05_full_%A_%a.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -u

: "${EXPERIMENT_ROOT:?}"
: "${EXPECTED_COMMIT:?}"
: "${EXPECTED_MANIFEST_SHA:?}"
: "${EXPECTED_CARDS_SHA:?}"
: "${EXPECTED_MODEL_SHA:?}"

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
py=/research/d7/spc/yzyang4/venvs/critic/bin/python
cards="$repo/phase1/cards_current_v11.jsonl"
manifest="$EXPERIMENT_ROOT/manifest/train_endpoints.jsonl"
model=/research/d7/spc/yzyang4/external/models/qwen2.5-0.5b-instruct
out="$EXPERIMENT_ROOT/features/shard_${SLURM_ARRAY_TASK_ID}"

cd "$repo"
test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git status --short)"
mkdir -p "$out"
export PYTHONHASHSEED=887
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export TRITON_CACHE_DIR="/research/d7/spc/yzyang4/scratch/triton_frozen05_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"

printf 'FROZEN_EMBED_FULL_START time=%s host=%s array=%s shard=%s commit=%s\n' \
  "$(date --iso-8601=seconds)" "$(hostname)" "$SLURM_ARRAY_JOB_ID" \
  "$SLURM_ARRAY_TASK_ID" "$EXPECTED_COMMIT"
set +e
"$py" phase1/frozen_embed_worker.py \
  --cards "$cards" \
  --manifest "$manifest" \
  --model "$model" \
  --out-dir "$out" \
  --repo-root "$repo" \
  --shard "$SLURM_ARRAY_TASK_ID" --num-shards 4 \
  --max-len 8192 --head-fraction 0.25 --batch-size 2 --chunk-size 32 \
  --expect-cards-sha256 "$EXPECTED_CARDS_SHA" \
  --expect-manifest-sha256 "$EXPECTED_MANIFEST_SHA" \
  --expect-model-sha256 "$EXPECTED_MODEL_SHA" \
  --expect-commit "$EXPECTED_COMMIT"
worker_rc=$?
set -e
printf 'FROZEN_EMBED_FULL_RC=%s time=%s shard=%s\n' \
  "$worker_rc" "$(date --iso-8601=seconds)" "$SLURM_ARRAY_TASK_ID"
exit "$worker_rc"
