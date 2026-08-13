#!/usr/bin/env bash
set -euo pipefail

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
main=/research/d7/spc/yzyang4/aira-dojo-reproduce
py=/research/d7/spc/yzyang4/venvs/aira/bin/python

set +u
source "$HOME/env_setup.sh"
set -a
source "$main/.env"
set +a
set -u
cd "$repo"
export PYTHONPATH="$repo/src"

for task in spaceship-titanic tweet-sentiment-extraction; do
  out="/tmp/schema_probe_v2_hydra_${task}.yaml"
  "$py" -m dojo.main_run \
    "task=mlebench/$task" \
    interpreter=jupyter \
    solver=mlebench/mcts_schema_probe \
    'solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash' \
    'solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash' \
    'solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash' \
    'solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash' \
    solver.step_limit=3 \
    solver.num_children=1 \
    solver.max_debug_depth=1 \
    solver.stop_after_first_valid=true \
    solver.execution_timeout=600 \
    solver.time_limit_secs=1200 \
    metadata.git_issue_id=schema_probe_repair_v2 \
    metadata.seed=862 \
    logger.use_wandb=false \
    --cfg job --resolve > "$out"

  grep -q 'CRITICAL ANYTIME ARTIFACT CONTRACT' "$out"
  grep -q 'step_limit: 3' "$out"
  grep -q 'num_children: 1' "$out"
  grep -q 'max_debug_depth: 1' "$out"
  grep -q 'stop_after_first_valid: true' "$out"
  grep -q 'execution_timeout: 600' "$out"
  grep -q 'time_limit_secs: 1200' "$out"
  test "$(grep -c 'model_id: deepseek-v4-flash' "$out")" -ge 4
  grep -q "$task" "$out"
  grep -q 'seed: 862' "$out"
  if grep -E 'AKIA[0-9A-Z]{16}|(^|[^A-Za-z])sk-[A-Za-z0-9._-]{12,}|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|Bearer[[:space:]]+[A-Za-z0-9._-]{12,}' "$out"; then
    printf 'RESOLVED_CONFIG_SECRET_LEAK\n' >&2
    exit 1
  fi
  sha256sum "$out"
done
printf 'SCHEMA_PROBE_V2_HYDRA_COMPOSE_PASS\n'
