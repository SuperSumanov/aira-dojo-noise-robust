"""Preparation-only paired ForeTS plan; no launcher, credentials, or API calls.

Route/model, pricing envelope and final Slurm budget must be resolved before
launch. Explicit output/deadline bounds below are proposals, not approved cost.
"""
OPERATORS = ('draft', 'improve', 'debug', 'analyze')
POLICIES = ('uniform_random', 'critic_topk_random')
TASKS = ('leaf-classification', 'spaceship-titanic')
SEEDS = (6, 7)


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
