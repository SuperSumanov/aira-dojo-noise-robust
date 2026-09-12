"""Undeployed execute-two control. Same generation, ranking and program budgets."""
import copy
from forets_single_proposal_control_20260913 import difference_paths


def execute_two(reference):
    cfg = copy.deepcopy(reference)
    solver = cfg['solver']
    if (solver['selection_policy'] not in ('uniform_random', 'critic_topk_random') or
        (solver['num_children'], solver['critic_top_k'], solver['num_children_to_choose'],
         solver['common_start_protocol'], solver['selection_coupling'],
         solver['time_limit_secs'], solver['execution_timeout']) !=
        (4, 2, 1, 'rf_common_v1', 'common_priority_v1', 600, 300)):
        raise ValueError('exact common-start reference required')
    solver['num_children_to_choose'] = 2
    if difference_paths(reference, cfg) != {('solver', 'num_children_to_choose')}:
        raise ValueError('unexpected multi-knob change')
    return cfg
