#!/usr/bin/env bash
#SBATCH --job-name=frozen05_smoke
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --constraint=rtx3090
#SBATCH --time=00:15:00
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/frozen05_smoke_%j.out

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
out="$EXPERIMENT_ROOT/smoke/shard_0"

cd "$repo"
test "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git status --short)"
test ! -e "$out"
mkdir -p "$out"
export PYTHONHASHSEED=887
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export TRITON_CACHE_DIR="/research/d7/spc/yzyang4/scratch/triton_frozen05_${SLURM_JOB_ID}"

printf 'FROZEN_EMBED_SMOKE_START time=%s host=%s job=%s commit=%s\n' \
  "$(date --iso-8601=seconds)" "$(hostname)" "$SLURM_JOB_ID" "$EXPECTED_COMMIT"
set +e
"$py" phase1/frozen_embed_worker.py \
  --cards "$cards" \
  --manifest "$manifest" \
  --model "$model" \
  --out-dir "$out" \
  --repo-root "$repo" \
  --shard 0 --num-shards 4 \
  --max-len 8192 --head-fraction 0.25 --batch-size 2 --chunk-size 32 \
  --limit-cards 16 \
  --expect-cards-sha256 "$EXPECTED_CARDS_SHA" \
  --expect-manifest-sha256 "$EXPECTED_MANIFEST_SHA" \
  --expect-model-sha256 "$EXPECTED_MODEL_SHA" \
  --expect-commit "$EXPECTED_COMMIT"
worker_rc=$?
set -e
printf 'FROZEN_EMBED_SMOKE_RC=%s time=%s\n' "$worker_rc" "$(date --iso-8601=seconds)"
exit "$worker_rc"
