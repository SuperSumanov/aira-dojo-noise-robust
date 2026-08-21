#!/usr/bin/env bash
# Submission template for an account authorized on zliang_gpu. This file does not self-submit.
#SBATCH --job-name=critic_component_g0
#SBATCH --partition=zliang_gpu
#SBATCH --qos=zliang_gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128G
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
