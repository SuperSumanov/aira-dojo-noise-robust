#!/usr/bin/env bash
#SBATCH --job-name=client_smoke
#SBATCH --partition=gpu_8h
#SBATCH --qos=gpu
#SBATCH --account=gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=6
#SBATCH --gpus-per-node=1
#SBATCH --exclude=projgpu7,projgpu8,projgpu33,gpu36,gpu38
#SBATCH --time=00:30:00
#SBATCH --signal=TERM@120
#SBATCH --output=/research/d7/spc/yzyang4/logs/balanced_client_smoke_%A_%a.out

set -eo pipefail
source "$HOME/env_setup.sh"
set -u
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf

: "${BALANCED_SOURCE_ROOT:?}"
: "${BALANCED_RUN_ROOT:?}"
: "${BALANCED_SOURCE_COMMIT:?}"
ENV_FILE=/research/d7/spc/yzyang4/aira-dojo-reproduce/.env
PYTHON=/research/d7/spc/yzyang4/venvs/aira/bin/python

test "$(git -C "$BALANCED_SOURCE_ROOT" rev-parse HEAD)" = "$BALANCED_SOURCE_COMMIT"
test -z "$(git -C "$BALANCED_SOURCE_ROOT" status --porcelain --untracked-files=all)"
test -f "$ENV_FILE"
set -a
source "$ENV_FILE"
set +a
export PYTHONPATH="$BALANCED_SOURCE_ROOT/src"
export LOGGING_DIR="$BALANCED_RUN_ROOT/outputs"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

case "${SLURM_ARRAY_TASK_ID}" in
  0)
    client=litellm_deepseek_flash
    model=deepseek-v4-flash
    base_url=https://api.deepseek.com
    ;;
  1)
    client=litellm_gen2
    model=qwen3-coder-flash
    base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
    ;;
  2)
    client=litellm_gen3
    model=glm-5
    base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
    ;;
  *)
    echo "INVALID_ARRAY_INDEX=${SLURM_ARRAY_TASK_ID}" >&2
    exit 64
    ;;
esac

issue="balanced_client_smoke_20260819_${model}"
resolved="$BALANCED_RUN_ROOT/resolved_${SLURM_ARRAY_TASK_ID}.yaml"
resolved_err="$BALANCED_RUN_ROOT/resolved_${SLURM_ARRAY_TASK_ID}.stderr"
rc_file="$BALANCED_RUN_ROOT/rc_${SLURM_ARRAY_TASK_ID}.json"

common=(
  task=mlebench/spooky-author-identification
  solver=mlebench/mcts
  interpreter=jupyter
  "solver/client@solver.operators.analyze.llm.client=$client"
  "solver/client@solver.operators.debug.llm.client=$client"
  "solver/client@solver.operators.draft.llm.client=$client"
  "solver/client@solver.operators.improve.llm.client=$client"
  solver.step_limit=2
  solver.execution_timeout=300
  solver.time_limit_secs=900
  metadata.seed=1401
  "metadata.git_issue_id=$issue"
  logger.use_wandb=false
  logger.write_env_vars=false
  logger.print_config=false
)

cd "$BALANCED_SOURCE_ROOT"
"$PYTHON" -m dojo.main_run "${common[@]}" --cfg job >"$resolved" 2>"$resolved_err"
"$PYTHON" - "$resolved" "$model" "$base_url" <<'PY'
import sys
from pathlib import Path
import yaml

payload = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
solver = payload["solver"]
if solver["step_limit"] != 2 or solver["execution_timeout"] != 300 or solver["time_limit_secs"] != 900:
    raise SystemExit("resolved budget mismatch")
operators = solver["operators"]
for name in ("analyze", "debug", "draft", "improve"):
    client = operators[name]["llm"]["client"]
    if client["model_id"] != sys.argv[2] or client["base_url"] != sys.argv[3]:
        raise SystemExit(f"resolved client mismatch: {name}")
print(f"RESOLVED_CLIENT_PASS model={sys.argv[2]} operators=4")
PY

set +e
"$PYTHON" -m dojo.main_run "${common[@]}"
run_rc=$?
set -e
printf '{"array_index":%s,"model":"%s","rc":%s,"source_commit":"%s"}\n' \
  "$SLURM_ARRAY_TASK_ID" "$model" "$run_rc" "$BALANCED_SOURCE_COMMIT" >"$rc_file.tmp"
mv "$rc_file.tmp" "$rc_file"
echo "BALANCED_CLIENT_SMOKE_WORKER_DONE model=$model rc=$run_rc"
exit "$run_rc"
