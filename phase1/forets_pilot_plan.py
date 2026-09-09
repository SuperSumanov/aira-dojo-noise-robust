"""Preparation-only paired ForeTS plan; no launcher, credentials, or API calls.

The optional free route uses the senior-confirmed OpenRouter clients. Credentials,
current catalog/account readiness and the final Slurm budget are still required.
Explicit output/deadline bounds below are proposals, not approved cost.
"""
OPERATORS = ('draft', 'improve', 'debug', 'analyze')
POLICIES = ('uniform_random', 'critic_topk_random')
TASKS = ('leaf-classification', 'spaceship-titanic')
SEEDS = (6, 7)
FREE_CLIENTS = {
    'litellm_nemotron-3-ultra': 'nvidia/nemotron-3-ultra-550b-a55b:free',
    'litellm_laguna-s-2.1': 'poolside/laguna-s-2.1:free',
}


def free_route_overrides(client_name):
    """Append to the paired plan, never launch. Only public artificial inputs
    are cleared for initial endpoint checks; free providers may retain/train data.
    This selects ONE generator for BOTH arms, not a model fallback or a sweep.
    The zero price filter is an upstream request constraint, not billing evidence.
    """
    if client_name not in FREE_CLIENTS:
        raise ValueError('choose an explicitly confirmed free client')
    values = ['logger.write_env_vars=false']
    for op in OPERATORS:
        values.append('solver/client@solver.operators.' + op + '.llm.client=' + client_name)
        prefix = '++solver.operators.' + op + '.llm.generation_kwargs.'
        values.extend([
            prefix + 'structured_output_mode=tools',
            prefix + 'structured_output_retries=0',
            prefix + 'bounded_transport=true',
            prefix + 'bounded_run_budget_required=true',
            prefix + 'extra_body.provider={allow_fallbacks:false,require_parameters:true,'
                     'max_price:{prompt:0,completion:0,request:0}}',
        ])
    return values


def overrides(task, seed, policy, *, max_output_tokens, request_timeout_seconds):
    if task not in TASKS or seed not in SEEDS or policy not in POLICIES:
        raise ValueError('outside declared exploratory matrix')
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise ValueError('explicit output limit required')
    if type(request_timeout_seconds) is not int or not 0 < request_timeout_seconds <= 300:
        raise ValueError('explicit bounded request timeout required')
    values = ['+_exp=mlebench/aira_forets_dsf_mle',
        'benchmark.tasks=[' + task + ']', 'launcher=srun_pool',
        'launcher.max_parallel=1', 'launcher.gpus_per_step=1', 'launcher.cpus_per_step=6',
        'launcher.debug=false', 'launcher.max_retries=0', 'logger.use_wandb=false',
        'solver.selection_policy=' + policy, 'solver.selector_seed=' + str(seed),
        'solver.num_children=4', 'solver.critic_top_k=2', 'solver.num_children_to_choose=1',
        'solver.execution_timeout=300', 'solver.time_limit_secs=1800', 'solver.step_limit=4',
        'solver.max_debug_depth=1', 'solver.max_llm_call_retries=2', 'solver.critic_max_attempts=1',
        'metadata.git_issue_id=e2e-development-draft', 'metadata.seed=' + str(seed),
        'vars={metadata.seed:[' + str(seed) + ']}']
    for op in OPERATORS:
        prefix = '++solver.operators.' + op + '.llm.generation_kwargs.'
        values.extend([prefix + 'bounded_transport=true', prefix + 'bounded_run_budget_required=true',
                       prefix + 'max_tokens=' + str(max_output_tokens),
                       prefix + 'bounded_request_timeout_seconds=' + str(request_timeout_seconds),
                       prefix + 'structured_output_retries=0'])
    return values


def run_order():
    # Balanced first-arm order, not chosen using scores. Separate independent
    # budget databases per run with identical policy limits across arms.
    for task_index, task in enumerate(TASKS):
        for seed in SEEDS:
            policies = POLICIES if (task_index + seed) % 2 == 0 else tuple(reversed(POLICIES))
            for policy in policies:
                yield task, seed, policy


def bounded_launcher_overrides(*, max_api_attempts, max_output_tokens, step_minutes=30, worker_wall_seconds=1740,
                               termination_allowance_seconds=330):
    """Proposal only. 330 seconds reflects observed KillWait=300 plus 30 margin.

    Re-check actual cluster policy before submission. No allocation is requested.
    """
    values = (max_api_attempts, max_output_tokens, step_minutes, worker_wall_seconds, termination_allowance_seconds)
    if any(type(value) is not int or value <= 0 for value in values):
        raise ValueError('explicit positive bounded launch limits required')
    return ['++launcher.step_time_limit_minutes=' + str(step_minutes),
            '++launcher.worker_wall_seconds=' + str(worker_wall_seconds),
            '++launcher.forets_max_api_attempts=' + str(max_api_attempts),
            '++launcher.forets_max_output_tokens=' + str(max_output_tokens),
            '++launcher.step_termination_allowance_seconds=' + str(termination_allowance_seconds),
            'launcher.min_remaining_seconds_to_launch=' + str(step_minutes * 60 + termination_allowance_seconds),
            'logger.write_env_vars=false']
