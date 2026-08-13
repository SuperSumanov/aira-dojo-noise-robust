#!/usr/bin/env bash
set -euo pipefail

repo=/research/d7/spc/yzyang4/worktrees/codex_trajectory_20260813
main=/research/d7/spc/yzyang4/aira-dojo-reproduce
ops=/research/d7/spc/yzyang4/probe_contract_ab_ops/probe_contract_ab_safety_v2
data=/research/d7/spc/yzyang4/mle-bench-data
aira_py=/research/d7/spc/yzyang4/venvs/aira/bin/python
audit_py=/research/d7/spc/yzyang4/venvs/exp/bin/python
config_dir="$ops/prereg/resolved_configs"

set +u
source "$HOME/env_setup.sh"
set -a
source "$main/.env"
set +a
set -u
cd "$repo"
export PYTHONPATH="$repo/src:$repo"
test ! -e "$config_dir"
mkdir -p "$config_dir"

rows=(
  '0|aerial-cactus-identification|original|probe_contract_ab_safety_v2_original'
  '1|aerial-cactus-identification|contract|probe_contract_ab_safety_v2_contract'
  '2|AI4Code|contract|probe_contract_ab_safety_v2_contract'
  '3|AI4Code|original|probe_contract_ab_safety_v2_original'
  '4|denoising-dirty-documents|original|probe_contract_ab_safety_v2_original'
  '5|denoising-dirty-documents|contract|probe_contract_ab_safety_v2_contract'
  '6|kuzushiji-recognition|contract|probe_contract_ab_safety_v2_contract'
  '7|kuzushiji-recognition|original|probe_contract_ab_safety_v2_original'
  '8|learning-agency-lab-automated-essay-scoring-2|original|probe_contract_ab_safety_v2_original'
  '9|learning-agency-lab-automated-essay-scoring-2|contract|probe_contract_ab_safety_v2_contract'
  '10|text-normalization-challenge-english-language|contract|probe_contract_ab_safety_v2_contract'
  '11|text-normalization-challenge-english-language|original|probe_contract_ab_safety_v2_original'
  '12|mlsp-2013-birds|original|probe_contract_ab_safety_v2_original'
  '13|mlsp-2013-birds|contract|probe_contract_ab_safety_v2_contract'
  '14|whale-categorization-playground|contract|probe_contract_ab_safety_v2_contract'
  '15|whale-categorization-playground|original|probe_contract_ab_safety_v2_original'
)

for frozen in "${rows[@]}"; do
  IFS='|' read -r index task arm issue <<< "$frozen"
  printf -v padded '%02d' "$index"
  out="$config_dir/index_${padded}_${arm}_${task}.yaml"
  if [[ "$arm" == contract ]]; then
    solver=mlebench/mcts_schema_probe
    first_valid=solver.stop_after_first_valid=true
  else
    solver=mlebench/mcts
    first_valid=+solver.stop_after_first_valid=true
  fi
  "$aira_py" -m dojo.main_run \
    task=mlebench/_default \
    "task.name=$task" \
    interpreter=jupyter \
    "solver=$solver" \
    solver/client@solver.operators.analyze.llm.client=litellm_deepseek_flash \
    solver/client@solver.operators.debug.llm.client=litellm_deepseek_flash \
    solver/client@solver.operators.draft.llm.client=litellm_deepseek_flash \
    solver/client@solver.operators.improve.llm.client=litellm_deepseek_flash \
    solver.step_limit=3 \
    solver.num_children=1 \
    solver.max_debug_depth=1 \
    "$first_valid" \
    solver.execution_timeout=600 \
    solver.time_limit_secs=1200 \
    "metadata.git_issue_id=$issue" \
    metadata.seed=887 \
    logger.use_wandb=false \
    --cfg job --resolve > "$out"
  if grep -E 'AKIA[0-9A-Z]{16}|(^|[^A-Za-z])sk-[A-Za-z0-9._-]{12,}|BEGIN [A-Z ]*PRIVATE KEY|Bearer[[:space:]]+[A-Za-z0-9._-]{12,}' "$out"; then
    echo RESOLVED_CONFIG_SECRET_LEAK >&2
    exit 1
  fi
done

"$audit_py" -m phase1.audit_probe_contract_ab_hydra \
  --version v2 \
  --config-dir "$config_dir" \
  --data-dir "$data" \
  --output "$ops/prereg/hydra_audit.json"
sha256sum "$config_dir"/*.yaml "$ops/prereg/hydra_audit.json" > "$ops/prereg/hydra_sha256.txt"
printf 'PROBE_CONTRACT_AB_V2_HYDRA_COMPOSE_PASS configs=%s\n' "${#rows[@]}"
