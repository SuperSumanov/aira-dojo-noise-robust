#!/usr/bin/env bash
#SBATCH --job-name=schema_jup
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --time=00:10:00
#SBATCH --nodelist=gpu39
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --output=/research/d7/spc/yzyang4/logs/schema_singularity_interpreter_smoke_%j.out

set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
set +u
source "$HOME/env_setup.sh"
set -a
source /research/d7/spc/yzyang4/aira-dojo-reproduce/.env
set +a
set -u
repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
py=/research/d7/spc/yzyang4/venvs/aira/bin/python
out=/research/d7/spc/yzyang4/schema_probe_ops/runtime_port_smoke_${SLURM_JOB_ID}
test ! -e "$out"
mkdir -p "$out"
export PYTHONPATH="$repo/src"
echo "SCHEMA_SINGULARITY_INTERPRETER_JOB_START $(date --iso-8601=seconds) job=$SLURM_JOB_ID node=$(hostname)"
set +e
"$py" "$repo/phase1/smoke_singularity_interpreter.py" \
  --workdir "$out/workdir" \
  --data-dir /research/d7/spc/yzyang4/mle-bench-data/spooky-author-identification/prepared/public \
  --out "$out/result.json"
smoke_rc=$?
set -e
echo "SCHEMA_SINGULARITY_INTERPRETER_RC=$smoke_rc $(date --iso-8601=seconds)"
if [[ "$smoke_rc" -eq 0 ]]; then cat "$out/result.json"; fi
exit "$smoke_rc"
