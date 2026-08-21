#!/usr/bin/env bash
# Shared-partition G0 template. This file never self-submits.
# Scientific inputs and model settings are identical to the authorized-account template.
# projgpu39 advertises no schedulable memory, so --mem=0 is the exact viable Slurm request.
#SBATCH --job-name=critic_component_g0
#SBATCH --partition=gpu_24h
#SBATCH --qos=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=12
#SBATCH --mem=0
#SBATCH --gres=gpu:pro6000:2
#SBATCH --nodelist=projgpu39
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=02:00:00
#SBATCH --output=/tmp/slurm-critic-component-g0-%j.out
#SBATCH --error=/tmp/slurm-critic-component-g0-%j.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

: "${G0_CONTROL_ROOT:?pass a clean phase1-value-critic checkout through sbatch --export}"
export G0_SOURCE_ROOT=${G0_SOURCE_ROOT:-/research/d7/spc/yzyang4/aira-dojo-audit-9f25145}
export G0_EXPECTED_SOURCE_COMMIT=${G0_EXPECTED_SOURCE_COMMIT:-51c7f480a844364a91cf1ee4ebd9dac18f6bb832}
export G0_VENV=${G0_VENV:-/research/d7/spc/yzyang4/venvs/critic}
export G0_TRAIN_PAIRS=${G0_TRAIN_PAIRS:-/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl}
export G0_DEV_PAIRS=${G0_DEV_PAIRS:-/research/d7/spc/yzyang4/critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/dev.jsonl}
export G0_CARDS=${G0_CARDS:-/research/d7/spc/yzyang4/worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json}
export G0_MODEL_SNAPSHOT=${G0_MODEL_SNAPSHOT:-/research/d7/spc/yzyang4/cache/huggingface/hub/models--Qwen--Qwen3-1.7B-Base/snapshots/ea980cb0a6c2ae4b936e82123acc929f1cec04c1}
export G0_RUN_ROOT=${G0_RUN_ROOT:-/research/d7/spc/yzyang4/critic-component-g0/runs/job-$SLURM_JOB_ID}

exec "$G0_CONTROL_ROOT/phase1/scripts/critic_component_g0_worker_20260821.sh"
