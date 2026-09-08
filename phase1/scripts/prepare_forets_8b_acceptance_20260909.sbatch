#!/bin/bash
# PREPARATION ONLY. No submission is authorized by this file or its switch.
# Submit only after the independent one-GPU matrix/budget is approved.
#SBATCH --job-name=forets-8b-accept
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=projgpu39
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gres=gpu:1
#SBATCH --mem=80G
#SBATCH --time=00:20:00

set -euo pipefail
umask 077
if [[ "${FORETS_ACCEPTANCE_APPROVED:-}" != 1 ]]; then
    printf '%s\n' 'No approved execution switch; refusing model execution.' >&2
    exit 2
fi
if [[ $# != 1 || ! -d "$1" ]]; then
    printf '%s\n' 'Pass an existing private, fresh receipt-parent directory.' >&2
    exit 2
fi
receipt_parent=$(realpath -- "$1")
case "$receipt_parent" in
    /research/d7/spc/yzyang4/*) ;;
    *) printf '%s\n' 'Receipt parent is outside the declared research area.' >&2; exit 2 ;;
esac
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
export PYTHONHASHSEED=6 PYTHONDONTWRITEBYTECODE=1
prepared_root=/research/d7/spc/yzyang4/forets-bounded-worker-20260909-xobxuu
critic_source=/research/d7/spc/yzyang4/forets-e2e-dev-20260908-IMuJx6/critic-offline-v1/src/mle_critic/src/evaluation
incoming=/research/d7/spc/yzyang4/forets-critic-incoming-20260908-3lcjjcwq
acceptance_python=/research/d7/spc/yzyang4/venvs/exp/bin/python
wrapper="$prepared_root/source-v2/src/dojo/core/runners/slurm/bounded_process.py"
test -x "$acceptance_python"
test -f "$wrapper"
test -f "$prepared_root/forets_8b_acceptance.py"
# No .env sourcing or API credentials are needed for local critic acceptance.
set +e
srun --jobid="$SLURM_JOB_ID" --exclusive --nodes=1 --ntasks=1 --cpus-per-task=6 \
    --gres=gpu:1 --time=19 --kill-on-bad-exit=1 \
    "$acceptance_python" "$wrapper" --cwd "$prepared_root" --output-dir "$receipt_parent/process" \
    --wall-seconds 1050 --grace-seconds 5 -- \
    "$acceptance_python" "$prepared_root/forets_8b_acceptance.py" --execute-approved-gpu \
    --source-root "$critic_source" --checkpoint "$incoming/unpacked/Qwen3-8B_reward_seed1/checkpoint-100" \
    --base-dir "$incoming/base-metadata" --output-dir "$receipt_parent/acceptance"
acceptance_rc=$?
set -e
printf 'acceptance_rc=%s\n' "$acceptance_rc"
exit "$acceptance_rc"
