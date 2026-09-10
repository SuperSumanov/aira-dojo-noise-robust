"""Planning arithmetic only; does not submit jobs or change any RunConfig."""
import argparse
import hashlib
import json
from pathlib import Path


def structural_paths(remaining, width=4):
    """Enumerate completed paths with zero/one debug slot after each expansion."""
    if remaining == 0:
        return [(0, 0, 0)]  # generated candidates, analyzed executions, pruning decisions
    count = min(width, remaining)
    rows = []
    for debug in range(min(1, remaining - 1) + 1):
        for generated, analyzed, pruned in structural_paths(remaining - 1 - debug, width):
            rows.append((count + debug + generated, 1 + debug + analyzed, int(count > 2) + pruned))
    return rows


def plan():
    steps, width, top_k = 6, 4, 2
    counts = [min(width, steps - step) for step in range(1, steps)]
    paths = structural_paths(steps - 1, width)
    operator_tries, transport_tries = 2, 3
    known_operator_attempt_ceiling = max((g * operator_tries + a) * transport_tries for g, a, _ in paths)
    rows = []
    for block, seed in enumerate((8, 9)):
        for task_index, task in enumerate(('leaf-classification', 'spaceship-titanic')):
            arms = ('uniform_random', 'critic_topk_random')
            if (block + task_index) % 2: arms = arms[::-1]
            for arm in arms:
                rows.append({'block': block+1, 'task': task, 'seed': seed, 'arm': arm})
    minutes_per_block = 15 + 4 * 60
    return {'status': 'DRAFT_NOT_SUBMITTABLE', 'base_source_tree': 'bbd22e323d6321925a145c12bdc02445c1ad80f4',
            'selector_prototype_sha256': hashlib.sha256(Path(__file__).with_name('forets_common_priority.py').read_bytes()).hexdigest(),
            'step_limit': steps, 'width': width, 'top_k': top_k, 'choose': 1,
            'no_debug_pool_sizes': counts, 'no_debug_candidate_count': sum(counts),
            'no_debug_pruning_decisions': sum(n > top_k for n in counts),
            'execution_slots_at_most': steps-1, 'execution_timeout_seconds': 300,
            'debug_depth': 1, 'operator_tries': operator_tries, 'transport_tries': transport_tries,
            'known_operator_attempt_ceiling': known_operator_attempt_ceiling,
            'max_api_attempts_per_run': 100, 'max_output_tokens_per_attempt': 8192,
            'request_timeout_seconds': 120, 'critic_attempts_per_candidate': 1,
            'worker_wall_seconds': 3540, 'slurm_step_minutes': 60, 'solver_time_limit_secs': 3600,
            'matrix': rows, 'runs': len(rows), 'pairs': len(rows)//2, 'blocks': 2,
            'gpus_per_allocation': 2, 'cpus_per_allocation': 12, 'node_candidate': 'gpu28',
            'block_time_limit_minutes': minutes_per_block,
            'block_nominal_gpu_hours': 2 * minutes_per_block / 60,
            'all_blocks_nominal_gpu_hours': 2 * 2 * minutes_per_block / 60,
            'all_blocks_with_observed_300s_killwait_gpu_hours': 2 * 2 * (minutes_per_block + 5) / 60,
            'all_runs_api_attempt_cap': 100 * len(rows),
            'all_runs_output_token_cap': 100 * len(rows) * 8192,
            'gpu_submissions': 0, 'api_requests': 0, 'model_fits': 0,
            'unresolved': ['supported OpenCL allocation isolation',
                           'checkpoint historical instruction/head-tail template',
                           'new exact source/config package and common-priority ledger binding',
                           'fresh fixed free-route availability within explicit check budget'],
            'limitations': ['planning caps, not measured runtime or a promise all runs complete',
                            'operator ceiling covers source-visible draft/improve/debug/analyze only',
                            'global request/wall caps win over completion; no extra uncounted retries',
                            'both blocks predefined; never choose later seeds/tasks based on observed scores',
                            'pause unfinished blocks for infrastructure failures, not unfavorable results',
                            'do not merge this new protocol with 13004; exploratory, not untouched confirmation']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = plan()
    raw = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream: stream.write(raw)
    print(raw)
